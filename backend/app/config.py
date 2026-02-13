import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_PATH), env_file_encoding="utf-8", extra="ignore")

    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_chat_model: str = Field(default="gpt-4o-mini", alias="OPENAI_CHAT_MODEL")
    openai_embed_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBED_MODEL")
    rag_top_k: int = Field(default=4, alias="RAG_TOP_K")
    chunk_size: int = Field(default=1000, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=150, alias="CHUNK_OVERLAP")
    allowed_origins: str = Field(default="http://localhost:5173", alias="ALLOWED_ORIGINS")

    root_dir: Path = Path(__file__).resolve().parents[2]
    chroma_persist_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "backend" / "data" / "chroma")
    ingest_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "ingest")
    ingest_manifest_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[2] / "backend" / "data" / "ingest_manifest.json"
    )
    chunk_store_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[2] / "backend" / "data" / "chunks.json"
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


settings = Settings()
if settings.openai_api_key:
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key
