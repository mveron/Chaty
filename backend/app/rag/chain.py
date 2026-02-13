from collections.abc import AsyncGenerator
import logging

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from openai import AuthenticationError
from openai import APIStatusError

from app.config import settings
from app.rag.ingest import load_chunk_documents
from app.rag.retriever import get_vectorstore

logger = logging.getLogger(__name__)

RAG_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant for question answering over provided context. "
            "Use the context to answer. If context is insufficient, say you do not have enough evidence "
            "and ask for more details. Be concise and factual.",
        ),
        MessagesPlaceholder(variable_name="history"),
        (
            "human",
            "Question:\n{question}\n\n"
            "Context:\n{context}\n\n"
            "Answer in the same language used by the user.",
        ),
    ]
)


def _build_chat_model(chat_model: str | None, temperature: float) -> ChatOpenAI:
    return ChatOpenAI(
        model=chat_model or settings.openai_chat_model,
        temperature=temperature,
        openai_api_base=settings.openai_base_url,
        openai_api_key=settings.openai_api_key,
    )


def _is_embedding_auth_error(exc: Exception) -> bool:
    if isinstance(exc, AuthenticationError):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code in (401, 403)
    status_code = getattr(exc, "status_code", None)
    return status_code in (401, 403)


def _retrieve_with_bm25(question: str, k: int) -> list[tuple[Document, float]]:
    documents = load_chunk_documents()
    if not documents:
        return []
    retriever = BM25Retriever.from_documents(documents)
    retriever.k = k
    return [(document, 0.0) for document in retriever.invoke(question)]


def _retrieve_documents(question: str, k: int) -> list[tuple[Document, float]]:
    vectorstore = get_vectorstore()
    try:
        results = vectorstore.similarity_search_with_score(question, k=k)
        if results:
            return results
        return _retrieve_with_bm25(question=question, k=k)
    except Exception as exc:
        if _is_embedding_auth_error(exc):
            return _retrieve_with_bm25(question=question, k=k)
        raise


async def stream_chat_answer(
    message: str,
    history: list[BaseMessage],
    top_k: int | None = None,
    chat_model: str | None = None,
    temperature: float = 0.2,
) -> AsyncGenerator[dict, None]:
    results = _retrieve_documents(message, k=top_k or settings.rag_top_k)

    sources_payload: list[dict] = []
    context_blocks: list[str] = []
    for document, score in results:
        source = str(document.metadata.get("source", "unknown"))
        preview = document.page_content[:180].replace("\n", " ")
        sources_payload.append({"source": source, "score": float(score), "preview": preview})
        context_blocks.append(f"Source: {source}\n{document.page_content}")

    context = "\n\n".join(context_blocks) if context_blocks else "No relevant documents found."
    prompt_value = RAG_PROMPT.invoke({"history": history, "question": message, "context": context})

    full_text = ""
    requested_model = chat_model or settings.openai_chat_model
    model_candidates = [requested_model]
    if requested_model != settings.openai_chat_model:
        model_candidates.append(settings.openai_chat_model)

    emitted_tokens = False
    for index, candidate_model in enumerate(model_candidates):
        llm = _build_chat_model(chat_model=candidate_model, temperature=temperature)
        try:
            async for chunk in llm.astream(prompt_value.to_messages()):
                token = chunk.content if isinstance(chunk.content, str) else "".join(chunk.content)
                if token:
                    emitted_tokens = True
                    full_text += token
                    yield {"event": "token", "data": {"text": token}}
            if emitted_tokens:
                break
        except Exception as exc:
            is_retry_candidate = index < len(model_candidates) - 1
            if is_retry_candidate:
                logger.warning("Chat model '%s' failed. Falling back to '%s'. Error: %s", candidate_model, settings.openai_chat_model, exc)
                continue
            raise

    yield {"event": "sources", "data": {"sources": sources_payload}}
    yield {"event": "complete_text", "data": {"text": full_text}}
