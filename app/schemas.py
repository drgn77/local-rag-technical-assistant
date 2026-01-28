from typing import List
from pydantic import BaseModel

class IngestRequest(BaseModel):
    path: str

class IngestResponse(BaseModel):
    indexed_files: int
    indexed_chunks: int

class AskRequest(BaseModel):
    question: str
    top_k: int = 5

class Source(BaseModel):
    file_path: str
    chunk_id: int
    score: float
    excerpt: str

class AskResponse(BaseModel):
    answer: str
    confidence: float
    sources: List[Source]
    notes: List[str]

class LLMJson(BaseModel):
    answer: str
    confidence: float = 0.5
    notes: List[str] = []

class IngestRequest(BaseModel):
    path: str
    reindex: bool = False
