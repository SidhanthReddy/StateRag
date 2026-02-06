from fastapi import FastAPI
from global_rag import GlobalRAG
from schemas import GlobalRAGEntry
from typing import List, Optional

app = FastAPI()
rag = GlobalRAG()

@app.post("/ingest")
def ingest(entry: GlobalRAGEntry):
    rag.ingest(entry)
    return {"status": "ok"}

@app.get("/retrieve")
def retrieve(
    query: str,
    k: int = 5,
    tags: Optional[str] = None
):
    tag_list = tags.split(",") if tags else None
    results = rag.retrieve(query, k=k, tags=tag_list)
    return results
