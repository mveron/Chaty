from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ingest_skips_unchanged(monkeypatch) -> None:
    def fake_ingest_documents(force: bool = False):
        assert force is False
        return {
            "indexed_files": [],
            "skipped_files": ["ingest/a.txt"],
            "total_chunks_added": 0,
            "collection_name": "chaty",
            "persist_dir": "backend/data/chroma",
        }

    monkeypatch.setattr("app.main.ingest_documents", fake_ingest_documents)
    response = client.post("/ingest", json={"force": False})
    assert response.status_code == 200
    payload = response.json()
    assert payload["skipped_files"] == ["ingest/a.txt"]
    assert payload["total_chunks_added"] == 0


def test_chat_sse_contract(monkeypatch) -> None:
    async def fake_stream_chat_answer(**kwargs):
        assert kwargs["message"] == "hola"
        yield {"event": "token", "data": {"text": "ho"}}
        yield {"event": "token", "data": {"text": "la"}}
        yield {"event": "sources", "data": {"sources": [{"source": "ingest/a.txt", "score": 0.1, "preview": "x"}]}}
        yield {"event": "complete_text", "data": {"text": "hola"}}

    monkeypatch.setattr("app.main.stream_chat_answer", fake_stream_chat_answer)
    response = client.post("/chat", json={"session_id": "s1", "message": "hola"}, headers={"Accept": "text/event-stream"})
    assert response.status_code == 200
    assert "event: token" in response.text
    assert "event: sources" in response.text
    assert "event: done" in response.text


def test_ingest_upload_accepts_txt_and_pdf(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.main.settings.ingest_dir", tmp_path)

    def fake_ingest_documents(force: bool = False):
        assert force is False
        return {
            "indexed_files": ["ingest/note.txt"],
            "skipped_files": [],
            "total_chunks_added": 1,
            "collection_name": "chaty",
            "persist_dir": "backend/data/chroma",
        }

    monkeypatch.setattr("app.main.ingest_documents", fake_ingest_documents)
    response = client.post(
        "/ingest/upload",
        files=[
            ("files", ("note.txt", b"hello", "text/plain")),
            ("files", ("sample.pdf", b"%PDF-1.4", "application/pdf")),
            ("files", ("ignored.docx", b"bad", "application/octet-stream")),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["uploaded_files"] == ["ingest/note.txt", "ingest/sample.pdf"]
    assert payload["rejected_files"] == ["ignored.docx"]
    assert payload["ingest"]["indexed_files"] == ["ingest/note.txt"]
    assert (tmp_path / "note.txt").exists()
    assert (tmp_path / "sample.pdf").exists()


def test_ingest_upload_requires_valid_files(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.main.settings.ingest_dir", tmp_path)
    response = client.post(
        "/ingest/upload",
        files=[("files", ("ignored.docx", b"bad", "application/octet-stream"))],
    )

    assert response.status_code == 400
    assert "Supported extensions: .txt, .pdf" in response.json()["detail"]
