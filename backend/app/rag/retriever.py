from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from app.config import settings

COLLECTION_NAME = "chaty"


def build_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.openai_embed_model,
        openai_api_base=settings.openai_base_url,
        openai_api_key=settings.openai_api_key,
    )


def get_vectorstore() -> Chroma:
    settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=build_embeddings(),
        persist_directory=str(settings.chroma_persist_dir),
    )
