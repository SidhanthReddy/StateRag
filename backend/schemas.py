from pydantic import BaseModel
from typing import List

class GlobalRAGEntry(BaseModel):
    id: str
    category: str
    title: str
    content: str
    tags: List[str]
    framework: str
    styling: str
