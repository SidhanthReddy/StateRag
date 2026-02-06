import json
import os
from typing import List, Optional
from datetime import datetime

from artifact import Artifact
from state_rag_enums import ArtifactSource, ArtifactType

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE_DIR, "state_rag", "artifacts.json")


class StateRAGManager:
    def __init__(self):
        # ---- Core state ----
        self.artifacts: List[Artifact] = []

        # ---- FAISS (lazy) ----
        self._embedder = None
        self._faiss_index = None
        self._faiss_ids: List[str] = []

        self._load()

    # ======================
    # Persistence
    # ======================

    def _load(self):
        if not os.path.exists(STATE_PATH):
            return

        try:
            with open(STATE_PATH, "r") as f:
                content = f.read().strip()
                if not content:
                    return

                raw = json.loads(content)
                self.artifacts = [Artifact(**a) for a in raw]

        except json.JSONDecodeError:
            print("⚠️ Warning: corrupted state file. Starting fresh.")
            self.artifacts = []
        
        # FIX #1: Force FAISS rebuild after loading artifacts
        # Without this, semantic search uses stale embeddings
        if self.artifacts:
            self._embedder = None  # Reset to trigger lazy init on next semantic search

    def _persist(self):
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        with open(STATE_PATH, "w") as f:
            json.dump(
                [a.dict() for a in self.artifacts],
                f,
                indent=2,
                default=str,
            )

    # ======================
    # Cleanup (Memory Leak Fix)
    # ======================

    def cleanup_old_versions(self, keep_versions: int = 5):
        """
        FIX #2: Remove old inactive versions to prevent unbounded growth.
        Keeps all active versions + N most recent inactive versions per file.
        """
        by_path = {}
        for a in self.artifacts:
            if a.file_path not in by_path:
                by_path[a.file_path] = []
            by_path[a.file_path].append(a)
        
        to_keep = []
        for path, versions in by_path.items():
            # Sort by version descending (newest first)
            sorted_versions = sorted(versions, key=lambda x: x.version, reverse=True)
            
            # Keep all active versions + N most recent inactive
            active = [v for v in sorted_versions if v.is_active]
            inactive = [v for v in sorted_versions if not v.is_active]
            
            to_keep.extend(active)
            to_keep.extend(inactive[:keep_versions])
        
        old_count = len(self.artifacts)
        self.artifacts = to_keep
        removed = old_count - len(self.artifacts)
        
        if removed > 0:
            print(f"🧹 Cleaned up {removed} old artifact versions")
            self._persist()

    # ======================
    # Commit logic
    # ======================

    def commit(self, new_artifact: Artifact) -> Artifact:
        active_versions = [
            a for a in self.artifacts
            if a.file_path == new_artifact.file_path and a.is_active
        ]

        # Authority enforcement
        for old in active_versions:
            if (
                old.source == ArtifactSource.user_modified
                and new_artifact.source != ArtifactSource.user_modified
            ):
                raise ValueError(
                    f"Cannot override user-modified artifact: {old.file_path}"
                )

        # Versioning
        new_version = 1
        if active_versions:
            new_version = max(a.version for a in active_versions) + 1
            for old in active_versions:
                old.is_active = False
                old.updated_at = datetime.utcnow()

        new_artifact.version = new_version
        new_artifact.is_active = True
        new_artifact.updated_at = datetime.utcnow()

        self.artifacts.append(new_artifact)
        self._persist()

        # FIX #2: Cleanup old versions periodically (every 10 commits)
        if len(self.artifacts) % 10 == 0:
            self.cleanup_old_versions(keep_versions=5)

        # Rebuild FAISS index only if already initialized
        if self._embedder is not None:
            self._build_faiss_index()

        return new_artifact

    # ======================
    # Retrieval
    # ======================

    def retrieve(
        self,
        scope: Optional[List[ArtifactType]] = None,
        file_paths: Optional[List[str]] = None,
        limit: int = 10,
        user_query: Optional[str] = None,
    ) -> List[Artifact]:

        # 1. Active only
        artifacts = [a for a in self.artifacts if a.is_active]

        # 2. Scope filter
        if scope:
            artifacts = [a for a in artifacts if a.type in scope]

        # 3. File path filter
        if file_paths:
            artifacts = [a for a in artifacts if a.file_path in file_paths]

        # 4. Dependency expansion
        artifacts = self._expand_dependencies(artifacts)

        # 5. Semantic ranking (optional)
        if user_query:
            artifacts = self._rank_with_faiss(artifacts, user_query)

        # 6. Deterministic fallback order
        artifacts.sort(key=lambda a: a.file_path)

        return artifacts[:limit]

    # ======================
    # Dependency expansion (with cycle detection)
    # ======================

    def _expand_dependencies(self, artifacts: List[Artifact]) -> List[Artifact]:
        """
        FIX #3: Added cycle detection to prevent infinite loops.
        
        Example circular dependency that would cause infinite loop:
        - Component A depends on Component B
        - Component B depends on Component A
        
        Now tracks visited nodes to break cycles.
        """
        result = {a.artifact_id: a for a in artifacts}
        lookup = {
            a.artifact_id: a
            for a in self.artifacts
            if a.is_active
        }

        visited = set()  # NEW: Track all visited nodes to prevent cycles
        queue = list(artifacts)

        while queue:
            current = queue.pop(0)
            
            # NEW: Skip if already processed (prevents cycles)
            if current.artifact_id in visited:
                continue
            visited.add(current.artifact_id)
            
            for dep_id in current.dependencies:
                if dep_id in lookup and dep_id not in result:
                    dep = lookup[dep_id]
                    result[dep_id] = dep
                    queue.append(dep)

        return list(result.values())

    # ======================
    # FAISS (lazy & safe)
    # ======================

    def _ensure_faiss_ready(self):
        if self._embedder is None:
            print("⏳ Initializing semantic index (one-time)...")

            from sentence_transformers import SentenceTransformer
            import faiss

            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            self._build_faiss_index()

            print("✅ Semantic index ready")

    def _build_faiss_index(self):
        active = [a for a in self.artifacts if a.is_active]
        if not active:
            self._faiss_index = None
            self._faiss_ids = []
            return

        texts = [
            f"{a.type} {a.name} {a.file_path}"
            for a in active
        ]

        embeddings = self._embedder.encode(texts).astype("float32")

        import faiss
        dim = embeddings.shape[1]
        index = faiss.IndexFlatL2(dim)
        index.add(embeddings)

        self._faiss_index = index
        self._faiss_ids = [a.artifact_id for a in active]

    def _rank_with_faiss(self, artifacts: List[Artifact], query: str) -> List[Artifact]:
        self._ensure_faiss_ready()

        if not self._faiss_index:
            return artifacts

        query_emb = self._embedder.encode([query]).astype("float32")
        _, indices = self._faiss_index.search(query_emb, len(self._faiss_ids))

        rank_map = {
            self._faiss_ids[idx]: rank
            for rank, idx in enumerate(indices[0])
        }

        return sorted(
            artifacts,
            key=lambda a: rank_map.get(a.artifact_id, float("inf"))
        )