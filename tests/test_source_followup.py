import httpx
import pytest
import test_recall
from fastapi.testclient import TestClient

from backend import research, retrieval, store
from backend.app import app

workspace = test_recall.workspace


def payload(workspace):
    paper, note = workspace
    block = next(
        b for b in store.get_blocks(paper["id"]) if b["id"] == note["block_id"]
    )
    return {
        "question": "How many samples?",
        "document_ids": [paper["id"]],
        "source_block_id": block["id"],
        "source_quote": block["text"],
    }


def no_retrieval(*args, **kwargs):
    raise AssertionError("Selected-source mode must never retrieve outside the block")


@pytest.mark.parametrize(
    "change,status",
    [
        ({"document_ids": []}, 422),
        ({"source_block_id": "other"}, 422),
        ({"source_quote": "A stale source quotation."}, 409),
        ({"source_quote": None}, 422),
        ({"source_block_id": None}, 422),
    ],
)
def test_invalid_or_stale_source_never_runs_model(
    workspace, monkeypatch, change, status
):
    monkeypatch.setattr(research, "single_answer", no_retrieval)
    monkeypatch.setattr(retrieval, "search", no_retrieval)
    with TestClient(app) as client:
        assert (
            client.post("/api/ask", json={**payload(workspace), **change}).status_code
            == status
        )


def test_selected_source_uses_full_existing_validation_and_persists_scope(
    workspace, monkeypatch
):
    body = payload(workspace)
    monkeypatch.setattr(retrieval, "search", no_retrieval)

    async def generate(question, ids, blocks, title, evidence, **kwargs):
        assert ids == body["document_ids"] and len(blocks) == 1
        assert (
            blocks[0]["id"] == body["source_block_id"]
            and blocks[0]["text"] == body["source_quote"]
        )
        return {
            "claims": [
                {
                    "evidence_id": "E1",
                    "text": "实验使用73个样本。",
                    "quote": body["source_quote"],
                },
                {
                    "evidence_id": "E1",
                    "text": "实验使用999个样本。",
                    "quote": body["source_quote"],
                },
            ],
            "limitations": "",
        }

    async def review(*args, **kwargs):
        return {
            "decisions": {
                "0": {
                    "verdict": "supported_relevant",
                    "support_span": body["source_quote"],
                }
            }
        }

    monkeypatch.setattr(research, "single_answer", generate)
    monkeypatch.setattr(research, "support_review", review)
    with TestClient(app) as client:
        response = client.post("/api/ask", json=body)
        assert response.status_code == 200
        answer = response.json()
        assert (
            len(answer["model_answer"]) == 1
            and "999" not in answer["model_answer"][0]["text"]
        )
        assert answer["source_scope"]["block_id"] == body["source_block_id"]
        assert len(answer["source_scope"]["sha256"]) == 64
        saved = research.artifact(answer["artifact_id"])
        assert saved["content"]["sections"][0]["source_scope"] == answer["source_scope"]
        assert "只依据你选中" in research.export_markdown(saved)
        assert "1 条候选" in answer["limitations"]


def test_generation_failure_does_not_fall_back_to_full_text(workspace, monkeypatch):
    async def fail(*args, **kwargs):
        raise httpx.ReadTimeout("controlled failure")

    monkeypatch.setattr(research, "single_answer", fail)
    monkeypatch.setattr(retrieval, "search", no_retrieval)
    with TestClient(app) as client:
        body = payload(workspace)
        result = client.post("/api/ask", json=body).json()
        assert result["model_answer"] is None
        assert [b["id"] for b in result["evidence"]] == [body["source_block_id"]]
        assert "没有扩大检索范围" in result["message"]


def test_archived_source_rejected(workspace):
    body = payload(workspace)
    with store.connection() as conn:
        conn.execute(
            "UPDATE documents SET archived=1 WHERE id=?", (body["document_ids"][0],)
        )
    with TestClient(app) as client:
        assert client.post("/api/ask", json=body).status_code == 409
