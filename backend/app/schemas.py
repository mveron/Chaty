from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    force: bool = False


class IngestResponse(BaseModel):
    indexed_files: list[str]
    skipped_files: list[str]
    total_chunks_added: int
    collection_name: str
    persist_dir: str


class IngestUploadResponse(BaseModel):
    uploaded_files: list[str]
    rejected_files: list[str]
    ingest: IngestResponse


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)
    chat_model: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
