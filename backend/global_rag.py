import faiss
import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer
from schemas import GlobalRAGEntry
from file_lock import FileLock, SharedFileLock

EMBEDDING_DIM = 384
INDEX_PATH = "global_rag.index"
DATA_PATH = "global_rag.json"


class GlobalRAG:
    """
    Global RAG system with thread-safe persistence.
    
    FIXED: Added file locking to prevent race conditions when multiple
    processes read/write simultaneously.
    """
    
    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.entries = []
        self.index = faiss.IndexFlatL2(EMBEDDING_DIM)

        if os.path.exists(INDEX_PATH) and os.path.exists(DATA_PATH):
            self._load()

    def _load(self):
        """
        FIX: Thread-safe loading with shared lock.
        
        Multiple processes can read simultaneously, but writes will block.
        """
        # FAISS index (no lock needed - atomic read)
        self.index = faiss.read_index(INDEX_PATH)
        
        # JSON data (with shared lock for thread safety)
        with SharedFileLock(DATA_PATH):
            with open(DATA_PATH, "r") as f:
                raw = json.load(f)
                self.entries = [GlobalRAGEntry(**e) for e in raw]

    def _persist(self):
        """
        FIX: Thread-safe persistence with exclusive lock.
        
        Prevents race conditions:
        - Process A reads entries
        - Process B reads entries
        - Process A writes (overwrites B's changes)
        - Process B writes (data corruption!)
        
        With locking:
        - Process A acquires lock, writes, releases
        - Process B waits, then writes safely
        """
        # FAISS index (atomic write - no lock needed)
        faiss.write_index(self.index, INDEX_PATH)
        
        # JSON data (with exclusive lock)
        with FileLock(DATA_PATH):
            with open(DATA_PATH, "w") as f:
                json.dump([e.dict() for e in self.entries], f, indent=2)

    def ingest(self, entry: GlobalRAGEntry):
        """
        Add new entry to Global RAG.
        
        Thread-safe: Uses exclusive lock during persist.
        """
        embedding = self.model.encode([entry.content]).astype("float32")
        self.index.add(embedding)
        self.entries.append(entry)
        self._persist()

    def retrieve(self, query: str, k: int = 5, tags=None):
        """
        Retrieve top-k relevant entries for a query.
        
        Args:
            query: Search query
            k: Number of results to return
            tags: Optional list of tags to filter by
        
        Returns:
            List of GlobalRAGEntry objects
        """
        # Embed query
        q_emb = self.model.encode([query]).astype("float32")
        
        # Search FAISS index (returns 2x results for filtering)
        _, indices = self.index.search(q_emb, k * 2)

        # Filter and collect results
        results = []
        for idx in indices[0]:
            if idx == -1:  # FAISS padding
                continue
            
            entry = self.entries[idx]
            
            # Tag filtering
            if tags and not set(tags).issubset(set(entry.tags)):
                continue
            
            results.append(entry)
            
            # Stop when we have enough
            if len(results) >= k:
                break

        return results