from typing import Callable, List, Optional
import time
import re
from state_rag_manager import StateRAGManager
from global_rag import GlobalRAG
from validator import Validator
from artifact import Artifact
from state_rag_enums import ArtifactSource
from state_rag_enums import ArtifactType
from llm_adapter import LLMAdapter
from llm_output_parser import parse_llm_output
from runtime_validator import validate_runtime
from node_registry_manager import NodeRegistryManager
from tailwind_utils import infer_tailwind_group
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
        self.project_id = project_id 
    def _build_prompt(
        self,
        active_artifacts,
        global_refs,
        user_request,
        allowed_paths
    ):
        system_section = (
            "You are an AI website builder.\n"
            "You are stateless.\n"
            "PROJECT STATE is authoritative.\n"
            "GLOBAL REFERENCES are advisory.\n"
            "Modify only explicitly allowed files.\n"
            "Output full updated files only.\n\n"
        )

        state_section = "PROJECT STATE (AUTHORITATIVE):\n"
        for a in active_artifacts:
            state_section += f"\nFILE: {a.file_path}\n{a.content}\n"

        lock_section = self._build_lock_section(allowed_paths)

        global_section = "GLOBAL REFERENCES (ADVISORY):\n"
        for ref in global_refs:
            global_section += f"\n{ref}\n"

        allowed_section = "ALLOWED FILES:\n"
        allowed_section += "\n".join(allowed_paths)

        user_section = f"\nUSER REQUEST:\n{user_request}\n"

        output_section = (
            "\nOUTPUT FORMAT:\n"
            "FILE: <file_path>\n"
            "<full file content>\n"
        )

        return (
            system_section
            + state_section
            + lock_section
            + global_section
            + allowed_section
            + user_section
            + output_section
        )

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
            file_paths=file_paths,
            user_query=user_request
        )
        print("Injected artifacts:", [a.file_path for a in active_artifacts])


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

        print("\n" + "="*80)
        print("FINAL LLM PROMPT")
        print("="*80)
        print(prompt)
        print("="*80 + "\n")

        # 4. Invoke LLM (stateless) with retry logic
        if event_callback:
            event_callback("llm_call_started", None)
        raw_output = self._llm_generate_with_retry(prompt)
        if event_callback:
            event_callback("llm_call_completed", None)
        print("RAW LLM OUTPUT:")
        print(raw_output)

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
        ##guard rail: config
        config_keywords = ["config", "package", "tailwind", "vite", "dependency", "build"]

        query_lower = user_request.lower()
        config_allowed = any(k in query_lower for k in config_keywords)

        for p in result.artifacts:
            path = p.file_path.lower()

            if path.endswith("package.json") \
            or path.endswith("vite.config.ts") \
            or path.endswith("tailwind.config.js") \
            or path.endswith("postcss.config.js"):

                if not config_allowed:
                    raise RuntimeError(
                        f"Modification of configuration file '{p.file_path}' was blocked. "
                        "Explicit configuration changes were not requested in the prompt."
                    )
        ##guard rail: folder boundary
        allowed_directories = [
            "src/pages/",
            "src/components/",
        ]

        allowed_exact_files = [
            "src/app.tsx",
            "src/app.js",
            "src/main.tsx",
            "src/main.js",
            "index.html",
            "package.json",
            "vite.config.ts",
            "tailwind.config.js",
            "postcss.config.js",
        ]
        lower = user_request.lower()

        is_rewrite = (
            "rewrite" in lower
            or "start from scratch" in lower
            or "replace entire" in lower
            or ("redesign" in lower and "complete" in lower)
            or ("rebuild" in lower and "complete" in lower)
        )

        for p in result.artifacts:
            path = p.file_path.lower()

            if (
                not any(path.startswith(d) for d in allowed_directories)
                and path not in allowed_exact_files
            ):
                raise RuntimeError(
                    f"File path '{p.file_path}' is outside allowed project structure."
                )


        for p in result.artifacts:
            old = next(
                (a for a in active_artifacts if a.file_path == p.file_path),
                None
            )

            if old:
                self._enforce_node_locks(
                    self.project_id,
                    p.file_path,
                    old.content,
                    p.content,
                    rewrite_mode=is_rewrite
                )


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
        if is_rewrite:
            registry = NodeRegistryManager(self.project_id)
            for fp in {a.file_path for a in result.artifacts}:
                registry.registry[fp] = {}
            registry._save()

        if event_callback:
            event_callback("commit_completed", {"count": len(committed)})
        return committed, active_artifacts
    



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
        Calls LLM with simple retry logic.
        """
        attempt = 0
        while attempt < max_retries:
            try:
                return self.llm.generate(prompt)
            except Exception:
                attempt += 1
                if attempt >= max_retries:
                    raise
                time.sleep(2 ** attempt)

    def _infer_type(self, file_path: str):
        path = file_path.lower()

        if "src/components/" in path:
            return ArtifactType.component

        if "src/pages/" in path:
            return ArtifactType.page

        if path.endswith("app.tsx") or path.endswith("app.js"):
            return ArtifactType.layout

        if path.endswith("main.tsx") or path.endswith("main.js"):
            return ArtifactType.layout

        if (
            path.endswith(".config.js")
            or path.endswith(".config.ts")
            or "config" in path
            or path.endswith("package.json")
            or path.endswith("vite.config.ts")
            or path.endswith("tailwind.config.js")
        ):
            return ArtifactType.config

        return ArtifactType.component
   
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
    
    def extract_node_classes(self, code: str):
        pattern = r'<[^>]*data-node-id="([^"]+)"[^>]*className="([^"]*)"'
        matches = re.findall(pattern, code)

        result = {}
        for node_id, class_str in matches:
            result[node_id] = class_str.split()

        return result

    def extract_all_node_ids(self, code: str):
        pattern = r'data-node-id="([^"]+)"'
        return re.findall(pattern, code)

    def _enforce_node_locks(self, project_id, file_path, old_content, new_content, rewrite_mode):
        # --- NODE ID INTEGRITY CHECKS ---
        if rewrite_mode:
            return
        new_node_ids = self.extract_all_node_ids(new_content)

        # 1️⃣ Missing node check (especially important for locked nodes)
        registry = NodeRegistryManager(project_id)
        file_registry = registry.registry.get(file_path, {})

        for node_id, data in file_registry.items():

            is_protected = (
                data.get("locked_groups")
                or data.get("user_modified")
            )

            if not is_protected:
                continue

            if node_id not in new_node_ids:
                raise RuntimeError(
                    f"Protected node '{node_id}' was removed from {file_path}. "
                    "Removal of protected nodes is not allowed."
                )


        # 2️⃣ Duplicate node ID check
        if len(new_node_ids) != len(set(new_node_ids)):
            raise RuntimeError(
                f"Duplicate data-node-id detected in {file_path}. "
                "Node IDs must remain unique."
            )

        # 3️⃣ Node ID mutation check

        old_nodes = self.extract_node_classes(old_content)
        new_nodes = self.extract_node_classes(new_content)

        file_registry = registry.registry.get(file_path, {})

        for node_id, old_classes in old_nodes.items():
            if node_id not in file_registry:
                continue

            locked_groups = file_registry[node_id]["locked_groups"]

            if not locked_groups:
                continue

            new_classes = new_nodes.get(node_id, [])

            for group in locked_groups:
                old_group_classes = [
                    c for c in old_classes
                    if infer_tailwind_group(c) == group
                ]

                new_group_classes = [
                    c for c in new_classes
                    if infer_tailwind_group(c) == group
                ]

                if set(old_group_classes) != set(new_group_classes):
                    raise RuntimeError(
                        f"LLM attempted to modify locked group '{group}' "
                        f"on node {node_id} in {file_path}"
                    )
   
    def _build_lock_section(self, allowed_paths: List[str]) -> str:
        registry = NodeRegistryManager(self.project_id)

        lines = []

        for file_path, nodes in registry.registry.items():

            # Only include files that are allowed in this request
            if "*" not in allowed_paths and file_path not in allowed_paths:
                continue

            file_lines = []

            for node_id, data in nodes.items():
                locked_groups = data.get("locked_groups", [])

                if locked_groups:
                    file_lines.append(
                        f"  - Node {node_id}: locked groups → {', '.join(locked_groups)}"
                    )

            if file_lines:
                lines.append(f"FILE: {file_path}")
                lines.extend(file_lines)

        if not lines:
            return ""

        header = (
            "LOCKED NODE CONSTRAINTS (STRICT ENFORCEMENT):\n"
            "The following node style groups were modified by the user.\n"
            "These groups are locked by the user.\n"
            "You MUST preserve the exact classes belonging to these groups.\n"
            "You must preserve these groups. Modify only other properties if possible.  \n\n"
        )

        return header + "\n".join(lines) + "\n\n"
