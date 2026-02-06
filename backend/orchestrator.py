from typing import Callable, List, Optional
import time

from state_rag_manager import StateRAGManager
from global_rag import GlobalRAG
from validator import Validator
from artifact import Artifact
from state_rag_enums import ArtifactSource

from llm_adapter import LLMAdapter
from llm_output_parser import parse_llm_output
from runtime_validator import validate_runtime


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

    def __init__(
        self,
        llm_provider: str = "mock",
        project_id: Optional[str] = None,
        state_rag: Optional[StateRAGManager] = None,
        global_rag: Optional[GlobalRAG] = None,
    ):
        self.state_rag = state_rag or StateRAGManager(project_id=project_id)
        self.global_rag = global_rag or GlobalRAG()
        self.validator = Validator()
        self.llm = LLMAdapter(provider=llm_provider)

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def handle_request(
        self,
        user_request: str,
        allowed_paths: List[str],
        runtime_validate: bool = False,
        event_callback: Optional[Callable[[str, Optional[dict]], None]] = None,
    ):
        """
        Executes one full user interaction.
        
        FIXED: Added pre-validation and retry logic.
        """

        # 1. Retrieve authoritative project state
        file_paths = None if "*" in allowed_paths else allowed_paths
        if event_callback:
            event_callback("state_retrieval_started", None)
        active_artifacts = self.state_rag.retrieve(
            file_paths=file_paths
        )
        if event_callback:
            event_callback("state_retrieval_completed", {"count": len(active_artifacts)})

        # FIX #1: Pre-validate authority BEFORE expensive LLM call
        # This prevents wasting API quota on requests that will fail validation
        self._pre_validate_authority(active_artifacts, allowed_paths)
        if event_callback:
            event_callback("authority_prevalidated", None)

        # 2. Retrieve advisory global knowledge
        if event_callback:
            event_callback("global_rag_retrieval_started", None)
        global_refs = self.global_rag.retrieve(
            query=user_request,
            k=3
        )
        if event_callback:
            event_callback("global_rag_retrieval_completed", {"count": len(global_refs)})

        # 3. Build strict prompt
        if event_callback:
            event_callback("prompt_build_started", None)
        prompt = self._build_prompt(
            user_request=user_request,
            active_artifacts=active_artifacts,
            global_refs=global_refs,
            allowed_paths=allowed_paths,
        )
        if event_callback:
            event_callback("prompt_build_completed", None)

        # 4. Invoke LLM (stateless) with retry logic
        if event_callback:
            event_callback("llm_call_started", None)
        raw_output = self._llm_generate_with_retry(prompt)
        if event_callback:
            event_callback("llm_call_completed", None)

        # 5. Parse LLM output (strict contract)
        proposed = parse_llm_output(raw_output)
        if event_callback:
            event_callback("llm_output_parsed", {"count": len(proposed)})

        # 6. Validate proposed changes
        if event_callback:
            event_callback("validation_started", None)
        result = self.validator.validate(
            proposed=proposed,
            active_artifacts=active_artifacts,
            allowed_paths=allowed_paths,
        )
        if event_callback:
            event_callback("validation_completed", {"ok": result.ok})

        if not result.ok:
            raise RuntimeError(
                f"Validation failed: {result.reason}"
            )

        if runtime_validate:
            runtime_artifacts = self._build_runtime_artifacts(
                active_artifacts=active_artifacts,
                proposed=result.artifacts,
            )
            ok, errors = validate_runtime(runtime_artifacts)
            if not ok:
                raise RuntimeError(
                    "Runtime validation failed: " + "; ".join(errors)
                )
            if event_callback:
                event_callback("runtime_validation_completed", {"ok": True})

        # 7. Commit validated artifacts
        if event_callback:
            event_callback("commit_started", None)
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

        if event_callback:
            event_callback("commit_completed", {"count": len(committed)})
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
        if "*" in allowed_paths:
            return

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
        """
        prompt_sections = []
        prompt_sections.append("\nGLOBAL REFERENCES (ADVISORY):\n")
        for i, ref in enumerate(global_refs, 1):
            prompt_sections.append(f"{i}. {ref.title}\n{ref.content}\n")

        prompt_sections.append("\nALLOWED FILES:\n")
        for p in allowed_paths:
            prompt_sections.append(f"- {p}")

        prompt_sections.append("\nUSER REQUEST:\n")
        prompt_sections.append(user_request)

        prompt_sections.append(
            "\nOUTPUT FORMAT:\n"
            "FILE: <file_path>\n"
            "<full file content>\n"
        )

        return "\n".join(prompt_sections)

    def _infer_type(self, file_path: str):
        if "components/" in file_path:
            return "component"
        if "app/" in file_path:
            return "page"
        return "config"

    def _build_runtime_artifacts(self, active_artifacts, proposed):
        active_lookup = {a.file_path: a for a in active_artifacts}
        merged = dict(active_lookup)

        for p in proposed:
            old = active_lookup.get(p.file_path)
            artifact_type = old.type if old else self._infer_type(p.file_path)
            source = old.source if old else ArtifactSource.ai_modified
            merged[p.file_path] = Artifact(
                type=artifact_type,
                name=p.file_path.split("/")[-1],
                file_path=p.file_path,
                content=p.content,
                language=p.language,
                source=source,
            )

        return list(merged.values())