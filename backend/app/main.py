import json
import logging
import shutil
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import File
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import AuthenticationError
from openai import APIConnectionError
from openai import APIStatusError

from app.config import settings
from app.rag.chain import stream_chat_answer
from app.rag.ingest import ingest_documents
from app.schemas import ChatRequest, IngestRequest, IngestResponse, IngestUploadResponse
from app.sessions import session_store

app = FastAPI(title="Chaty RAG Backend", version="1.0.0")
logger = logging.getLogger(__name__)
SUPPORTED_UPLOAD_EXTENSIONS = {".txt", ".pdf"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_ingest() -> None:
    try:
        ingest_documents(force=False)
    except Exception as exc:  # pragma: no cover - non-fatal startup path
        logger.warning("Startup ingest skipped: %s", exc)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _run_ingest(force: bool) -> IngestResponse:
    try:
        return ingest_documents(force=force)
    except APIConnectionError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Could not reach OpenAI API. Check OPENAI_BASE_URL/OPENAI_API_KEY in .env."
            ),
        ) from exc
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=401,
            detail="OpenAI API authentication failed. Verify OPENAI_API_KEY.",
        ) from exc
    except APIStatusError as exc:
        if exc.status_code in (401, 403):
            raise HTTPException(
                status_code=exc.status_code,
                detail=(
                    "OpenAI API key is not authorized for embeddings. "
                    "The app falls back to BM25 retrieval when this happens."
                ),
            ) from exc
        raise


@app.post("/ingest", response_model=IngestResponse)
def ingest(payload: IngestRequest) -> IngestResponse:
    return _run_ingest(force=payload.force)


@app.post("/ingest/upload", response_model=IngestUploadResponse)
async def ingest_upload(files: list[UploadFile] = File(...)) -> IngestUploadResponse:
    settings.ingest_dir.mkdir(parents=True, exist_ok=True)
    uploaded_files: list[str] = []
    rejected_files: list[str] = []

    for incoming in files:
        incoming_name = incoming.filename or ""
        safe_name = Path(incoming_name).name
        file_extension = Path(safe_name).suffix.lower()
        if not safe_name or file_extension not in SUPPORTED_UPLOAD_EXTENSIONS:
            rejected_files.append(incoming_name or "<unnamed>")
            await incoming.close()
            continue

        destination = settings.ingest_dir / safe_name
        with destination.open("wb") as target_file:
            shutil.copyfileobj(incoming.file, target_file)
        uploaded_files.append(f"ingest/{safe_name}")
        await incoming.close()

    if not uploaded_files:
        raise HTTPException(
            status_code=400,
            detail="No valid files uploaded. Supported extensions: .txt, .pdf.",
        )

    ingest_result = _run_ingest(force=False)
    return IngestUploadResponse(
        uploaded_files=uploaded_files,
        rejected_files=rejected_files,
        ingest=ingest_result,
    )


def _to_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/chat")
async def chat(payload: ChatRequest) -> StreamingResponse:
    history = session_store.get_messages(payload.session_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        assistant_full_text = ""
        try:
            async for event in stream_chat_answer(
                message=payload.message,
                history=history,
                top_k=payload.top_k,
                chat_model=payload.chat_model,
                temperature=payload.temperature,
            ):
                event_type = event["event"]
                data = event["data"]
                if event_type == "complete_text":
                    assistant_full_text = data.get("text", "")
                    continue
                yield _to_sse(event_type, data)
        except AuthenticationError:
            yield _to_sse(
                "token",
                {"text": "OpenAI authentication failed. Verify OPENAI_API_KEY in backend .env."},
            )
        except ValueError as exc:
            yield _to_sse(
                "token",
                {"text": f"Chat generation failed: {exc}"},
            )
        except APIStatusError as exc:
            if exc.status_code in (401, 403):
                yield _to_sse(
                    "token",
                    {"text": "OpenAI authorization failed. Verify OPENAI_API_KEY and model permissions."},
                )
            else:
                raise

        if assistant_full_text:
            session_store.append_turn(payload.session_id, payload.message, assistant_full_text)
        yield _to_sse("done", {})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
