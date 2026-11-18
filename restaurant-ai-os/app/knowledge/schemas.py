from pydantic import BaseModel


class KnowledgeSearchIn(BaseModel):
    question: str


class KnowledgeSourceOut(BaseModel):
    document_id: int
    filename: str
    chunk_index: int
    text: str


class KnowledgeSearchOut(BaseModel):
    answer: str
    sources: list[KnowledgeSourceOut]


class KnowledgeDocumentOut(BaseModel):
    id: int
    filename: str
    status: str
    chunk_count: int
    error: str | None = None
