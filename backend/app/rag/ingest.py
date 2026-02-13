import hashlib
import json
import logging
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import AuthenticationError
from openai import APIStatusError
from pypdf import PdfReader

from app.config import settings
from app.rag.retriever import COLLECTION_NAME, get_vectorstore
from app.schemas import IngestResponse

logger = logging.getLogger(__name__)
SUPPORTED_INGEST_EXTENSIONS = {".txt", ".pdf"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest() -> dict:
    settings.ingest_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if not settings.ingest_manifest_path.exists():
        return {"files": {}}
    with settings.ingest_manifest_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_manifest(manifest: dict) -> None:
    settings.ingest_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with settings.ingest_manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2)


def _load_chunk_store() -> dict[str, list[dict]]:
    settings.chunk_store_path.parent.mkdir(parents=True, exist_ok=True)
    if not settings.chunk_store_path.exists():
        return {}
    with settings.chunk_store_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_chunk_store(store: dict[str, list[dict]]) -> None:
    settings.chunk_store_path.parent.mkdir(parents=True, exist_ok=True)
    with settings.chunk_store_path.open("w", encoding="utf-8") as file:
        json.dump(store, file, indent=2)


def load_chunk_documents() -> list[Document]:
    store = _load_chunk_store()
    documents: list[Document] = []
    for source, chunks in store.items():
        for chunk in chunks:
            metadata = {
                "source": source,
                "file_sha256": chunk.get("file_sha256"),
                "chunk_index": chunk.get("chunk_index"),
            }
            documents.append(Document(page_content=chunk.get("page_content", ""), metadata=metadata))
    return documents


def _is_embedding_auth_error(exc: Exception) -> bool:
    if isinstance(exc, AuthenticationError):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code in (401, 403)
    status_code = getattr(exc, "status_code", None)
    return status_code in (401, 403)


def _has_persisted_vectors(vectorstore, doc_ids: list[str]) -> bool:
    if not doc_ids:
        return False
    sample_ids = doc_ids[: min(3, len(doc_ids))]
    try:
        stored = vectorstore.get(ids=sample_ids)
    except Exception:
        return False
    persisted_ids = stored.get("ids", []) if isinstance(stored, dict) else []
    return bool(persisted_ids)


def _iter_ingest_files() -> list[Path]:
    files = [
        path
        for path in settings.ingest_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_INGEST_EXTENSIONS
    ]
    return sorted(files)


def _extract_file_text(file_path: Path) -> str:
    file_extension = file_path.suffix.lower()
    if file_extension == ".txt":
        return file_path.read_text(encoding="utf-8", errors="ignore")
    if file_extension == ".pdf":
        reader = PdfReader(str(file_path))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:
                raise ValueError("encrypted PDF is not supported") from exc
        pages_text = [(page.extract_text() or "").strip() for page in reader.pages]
        return "\n\n".join([page for page in pages_text if page])
    raise ValueError(f"unsupported file type: {file_extension}")


def ingest_documents(force: bool = False) -> IngestResponse:
    settings.ingest_dir.mkdir(parents=True, exist_ok=True)
    vectorstore = get_vectorstore()
    splitter = RecursiveCharacterTextSplitter(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
    manifest = _load_manifest()
    tracked_files: dict = manifest.get("files", {})
    chunk_store = _load_chunk_store()

    indexed_files: list[str] = []
    skipped_files: list[str] = []
    total_chunks_added = 0
    discovered_rel_paths: set[str] = set()
    can_use_remote_embeddings = True

    for file_path in _iter_ingest_files():
        rel_path = file_path.relative_to(settings.root_dir).as_posix()
        discovered_rel_paths.add(rel_path)
        file_hash = _sha256_file(file_path)
        previous = tracked_files.get(rel_path, {})
        previous_ids: list[str] = previous.get("doc_ids", [])
        has_vector_index = _has_persisted_vectors(vectorstore, previous_ids)

        if not force and previous.get("sha256") == file_hash and has_vector_index:
            skipped_files.append(rel_path)
            continue

        try:
            text = _extract_file_text(file_path)
        except Exception as exc:
            logger.warning("Skipping '%s': %s", rel_path, exc)
            skipped_files.append(rel_path)
            tracked_files[rel_path] = {"sha256": file_hash, "doc_ids": previous_ids}
            continue

        if not text.strip():
            skipped_files.append(rel_path)
            tracked_files[rel_path] = {"sha256": file_hash, "doc_ids": []}
            chunk_store[rel_path] = []
            continue

        chunks = splitter.split_text(text)
        docs: list[Document] = []
        doc_ids: list[str] = []
        for index, chunk in enumerate(chunks):
            doc_id = f"{rel_path}:{file_hash}:{index}"
            doc_ids.append(doc_id)
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "source": rel_path,
                        "file_sha256": file_hash,
                        "chunk_index": index,
                    },
                )
            )

        chunk_store[rel_path] = [
            {
                "page_content": document.page_content,
                "file_sha256": document.metadata.get("file_sha256"),
                "chunk_index": document.metadata.get("chunk_index"),
            }
            for document in docs
        ]

        persisted_ids = previous_ids
        if docs and can_use_remote_embeddings:
            try:
                if previous_ids:
                    vectorstore.delete(ids=previous_ids)
                vectorstore.add_documents(documents=docs, ids=doc_ids)
                persisted_ids = doc_ids
            except Exception as exc:
                if _is_embedding_auth_error(exc):
                    can_use_remote_embeddings = False
                    persisted_ids = previous_ids
                    logger.warning(
                        "OpenAI embeddings unauthorized for current API key. "
                        "Falling back to BM25 retrieval from local chunks."
                    )
                else:
                    raise

        tracked_files[rel_path] = {"sha256": file_hash, "doc_ids": persisted_ids}
        indexed_files.append(rel_path)
        total_chunks_added += len(docs)

    missing_paths = [path for path in tracked_files if path not in discovered_rel_paths]
    for stale_path in missing_paths:
        stale_ids = tracked_files[stale_path].get("doc_ids", [])
        if stale_ids and can_use_remote_embeddings:
            try:
                vectorstore.delete(ids=stale_ids)
            except Exception:
                pass
        del tracked_files[stale_path]
        chunk_store.pop(stale_path, None)

    _save_manifest({"files": tracked_files})
    _save_chunk_store(chunk_store)

    return IngestResponse(
        indexed_files=indexed_files,
        skipped_files=skipped_files,
        total_chunks_added=total_chunks_added,
        collection_name=COLLECTION_NAME,
        persist_dir=str(settings.chroma_persist_dir),
    )
