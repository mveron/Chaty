# Chaty RAG Application

RAG chatbot with:
- Frontend: React 18 + Vite 5
- Backend: FastAPI + LangChain v1
- LLM/embeddings: OpenAI-compatible API
- Ingestion source folder: `ingest/` (`.txt` and `.pdf` files)

The UI was generated with Google Stitch MCP as a web desktop workspace and implemented in React from that design:
- Stitch project: `projects/14033143330943928384`
- Implemented screen: `projects/14033143330943928384/screens/7248071b1a944f978dcc6bb0e796c753`
- Desktop layout: left settings panel, center chat workspace, right sources panel

## Versions

### Backend (`backend/requirements.txt`)
- `fastapi==0.129.0`
- `uvicorn[standard]==0.40.0`
- `python-dotenv==1.2.1`
- `pydantic==2.12.5`
- `pydantic-settings==2.12.0`
- `langchain==1.2.10`
- `langchain-community==0.4.1`
- `langchain-chroma==1.1.0`
- `langchain-openai==1.1.9`
- `langchain-text-splitters==1.1.0`
- `chromadb==1.5.0`
- `rank-bm25==0.2.2`
- `openai==2.20.0`
- `httpx==0.28.1`
- `pytest==9.0.2`

### Frontend (`frontend/package.json`)
- `react==18.2.0`
- `react-dom==18.2.0`
- `vite==5.4.11`
- `@vitejs/plugin-react==4.3.1`
- `typescript==5.5.4`
- `@microsoft/fetch-event-source==2.0.1`
- `tailwindcss==3.4.17`
- `postcss==8.4.38`
- `autoprefixer==10.4.20`

## Project Structure

- `ingest/`: drop `.txt` and `.pdf` files to index
- `backend/`: FastAPI + RAG logic
- `frontend/`: React chatbot UI

## Setup

1. Copy env defaults:
```powershell
Copy-Item .env.example .env
```

2. Start backend:
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

3. Start frontend:
```powershell
cd frontend
npm install
npm run dev
```

4. Open:
- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8000/health`

## API Contract

### `GET /health`
```json
{ "status": "ok" }
```

### `POST /ingest`
Request:
```json
{ "force": false }
```

### `POST /ingest/upload` (multipart/form-data)
Form field:
- `files`: one or more `.txt` / `.pdf` files

### `POST /chat` (SSE)
Request:
```json
{
  "session_id": "session-1",
  "message": "What does the document say about pricing?",
  "top_k": 4,
  "chat_model": "gpt-4o-mini",
  "temperature": 0.2
}
```

SSE events:
- `token`
- `sources`
- `done`

## Ingestion Behavior

- Scans `ingest/**/*.txt` and `ingest/**/*.pdf`
- Auto-ingests at backend startup (non-fatal if API is unavailable)
- UI upload button (`+`) sends files to backend and triggers ingest automatically
- Manual ingest via `POST /ingest`
- Uses SHA256 manifest (`backend/data/ingest_manifest.json`) to skip unchanged files
- Removes vectors for files deleted from `ingest/`

## OpenAI Notes

Default models:
- Chat: `gpt-4o-mini`
- Embeddings: `text-embedding-3-small`

Set:
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_CHAT_MODEL`
- `OPENAI_EMBED_MODEL`

Example:
- `OPENAI_BASE_URL=https://api.openai.com/v1`

## Embeddings Permission Note

With some OpenAI-compatible keys, embeddings may return `401/403` even when chat works.
This app handles that automatically:
- keeps using OpenAI chat generation
- falls back to BM25 retrieval over locally ingested chunks for RAG
