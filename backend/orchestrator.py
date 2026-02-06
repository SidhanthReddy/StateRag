from typing import List
import time

from state_rag_manager import StateRAGManager
from global_rag import GlobalRAG
from validator import Validator
from artifact import Artifact
from state_rag_enums import ArtifactSource

from llm_adapter import LLMAdapter
from llm_output_parser import parse_llm_output


class Orchestrator:
    """
    Central execution controller.

    Responsibilities:
    - Retrieve authoritative state (State RAG)
    - Retrieve advisory knowledge (Global RAG)
    - Build strict prompt
    - Invoke LLM (stateless)
    - Parse LLM output
    - Validate proposed changes
    - Commit validated artifacts
    
    FIXED:
    - Pre-validation to avoid wasting LLM quota
    - Retry logic for transient LLM failures
    """

    def __init__(self, llm_provider: str = "mock"):
        self.state_rag = StateRAGManager()
        self.global_rag = GlobalRAG()
        self.validator = Validator()
        self.llm = LLMAdapter(provider=llm_provider)

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def handle_request(
        self,
        user_request: str,
        allowed_paths: List[str],
    ):
        """
        Executes one full user interaction.
        
        FIXED: Added pre-validation and retry logic.
        """

        # 1. Retrieve authoritative project state
        active_artifacts = self.state_rag.retrieve(
            file_paths=allowed_paths
        )

        # FIX #1: Pre-validate authority BEFORE expensive LLM call
        # This prevents wasting API quota on requests that will fail validation
        self._pre_validate_authority(active_artifacts, allowed_paths)

        # 2. Retrieve advisory global knowledge
        global_refs = self.global_rag.retrieve(
            query=user_request,
            k=3
        )

        # 3. Build strict prompt
        prompt = self._build_prompt(
            user_request=user_request,
            active_artifacts=active_artifacts,
            global_refs=global_refs,
            allowed_paths=allowed_paths,
        )

        # 4. Invoke LLM (stateless) with retry logic
        raw_output = self._llm_generate_with_retry(prompt)

        # 5. Parse LLM output (strict contract)
        proposed = parse_llm_output(raw_output)

        # 6. Validate proposed changes
        result = self.validator.validate(
            proposed=proposed,
            active_artifacts=active_artifacts,
            allowed_paths=allowed_paths,
        )

        if not result.ok:
            raise RuntimeError(
                f"Validation failed: {result.reason}"
            )

        # 7. Commit validated artifacts
        committed = []

        for p in result.artifacts:
            old = next(
                (a for a in active_artifacts if a.file_path == p.file_path),
                None
            )

            # Preserve user authority if user explicitly allowed the edit
            if old and old.source == ArtifactSource.user_modified:
                source = ArtifactSource.user_modified
            else:
                source = ArtifactSource.ai_modified

            artifact = Artifact(
                type=self._infer_type(p.file_path),
                name=p.file_path.split("/")[-1],
                file_path=p.file_path,
                content=p.content,
                language=p.language,
                source=source,
            )

            committed.append(
                self.state_rag.commit(artifact)
            )

        return committed

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    def _pre_validate_authority(
        self,
        active_artifacts: List[Artifact],
        allowed_paths: List[str],
    ):
        """
        FIX #1: Pre-validation to catch authority violations BEFORE LLM call.
        
        Scenario that this prevents:
        1. User has file A marked as user_modified
        2. AI tries to modify file A (not in allowed_paths)
        3. Without this: Expensive LLM call → parse → FAIL validation
        4. With this: FAIL immediately → save API quota
        
        Args:
            active_artifacts: Currently active artifacts from State RAG
            allowed_paths: Files the user explicitly allowed for modification
        
        Raises:
            ValueError: If user-modified files exist that aren't in allowed_paths
        """
        user_protected = [
            a for a in active_artifacts 
            if a.source == ArtifactSource.user_modified 
            and a.file_path not in allowed_paths
        ]
        
        if user_protected:
            protected_files = [a.file_path for a in user_protected]
            raise ValueError(
                f"Cannot modify user-protected files. "
                f"These files are marked as user_modified but not in allowed_paths: "
                f"{protected_files}. "
                f"Add them to allowed_paths to enable AI modification."
            )

    def _llm_generate_with_retry(
        self,
        prompt: str,
        max_retries: int = 3,
    ) -> str:
        """
        FIX #2: LLM call with exponential backoff for transient errors.
        
        Retries on:
        - Rate limits (429)
        - Timeouts
        - Server errors (500, 503)
        
        Does NOT retry on:
        - Invalid API key (401)
        - Bad request (400)
        - Other permanent errors
        
        Args:
            prompt: Prompt to send to LLM
            max_retries: Maximum number of retry attempts
        
        Returns:
            LLM response text
        
        Raises:
            Exception: If non-transient error or max retries exceeded
        """
        for attempt in range(max_retries):
            try:
                return self.llm.generate(prompt)
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check if error is transient (should retry)
                transient_keywords = [
                    'timeout',
                    'rate limit',
                    '429',  # Too Many Requests
                    '503',  # Service Unavailable
                    '500',  # Internal Server Error
                    'connection',
                    'temporary',
                ]
                
                is_transient = any(
                    keyword in error_msg 
                    for keyword in transient_keywords
                )
                
                if is_transient and attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2 ** attempt
                    print(
                        f"⚠️  LLM error (attempt {attempt + 1}/{max_retries}): {e}\n"
                        f"    Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue
                
                # Non-transient error or max retries exceeded
                if is_transient:
                    raise RuntimeError(
                        f"LLM failed after {max_retries} retries. "
                        f"Last error: {e}"
                    )
                else:
                    # Don't retry non-transient errors
                    raise

        # Should never reach here, but just in case
        raise RuntimeError(f"Unexpected retry loop exit after {max_retries} attempts")

    def _build_prompt(
        self,
        user_request: str,
        active_artifacts,
        global_refs,
        allowed_paths,
    ) -> str:
        """
        Constructs a strict, authority-aware prompt for the LLM.
        """

        parts = []

        parts.append(
            "SYSTEM:\n"
            "You are an AI website builder.\n"
            "You are stateless.\n"
            "PROJECT STATE is authoritative.\n"
            "GLOBAL REFERENCES are advisory.\n"
            "Modify only explicitly allowed files.\n"
            "Output full updated files only.\n"
        )

        parts.append("\nPROJECT STATE (AUTHORITATIVE):\n")
        for a in active_artifacts:
            parts.append(f"--- {a.file_path} ---\n{a.content}\n")

        parts.append("\nGLOBAL REFERENCES (ADVISORY):\n")
        for i, ref in enumerate(global_refs, 1):
            parts.append(f"{i}. {ref.title}\n{ref.content}\n")

        parts.append("\nALLOWED FILES:\n")
        for p in allowed_paths:
            parts.append(f"- {p}")

        parts.append("\nUSER REQUEST:\n")
        parts.append(user_request)

        parts.append(
            "\nOUTPUT FORMAT:\n"
            "FILE: <file_path>\n"
            "<full file content>\n"
        )

        return "\n".join(parts)

    def _infer_type(self, file_path: str):
        if "components/" in file_path:
            return "component"
        if "app/" in file_path:
            return "page"
        return "config"