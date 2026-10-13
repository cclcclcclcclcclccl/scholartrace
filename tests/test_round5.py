import asyncio

import pytest
from fastapi.testclient import TestClient

from backend import accounts, database, query_facets, research, store
from backend.app import app
from backend.claim_checks import semantic_overreach


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "library.sqlite3")
    monkeypatch.setattr(accounts, "AUTH_PATH", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(accounts, "path", lambda i: tmp_path / i / "library.sqlite3")
    database.initialize()
    with TestClient(app) as value:
        yield value


def test_historical_measurement_uses_selected_metric_and_seeds(client):
    old = {"metric": "loss", "seeds": [1, 2], "baseline": "原对照"}
    current = {"metric": "accuracy", "seeds": [11, 23], "baseline": "新对照"}
    card = research.save_artifact(
        "protocol",
        "历史版本设计",
        {
            "revision": 3,
            "protocol": current,
            "history": [
                {"revision": 1, "protocol": old},
                {"revision": 2, "protocol": {**old, "baseline": "中间版本"}},
            ],
        },
    )
    body = {
        "title": "旧实验记录",
        "csv": "method,seed,loss\nA,1,2\nA,2,4",
        "group": "method",
        "run": "seed",
        "metric": "loss",
        "protocol_id": card["id"],
        "protocol_revision": 1,
    }
    r = client.post("/api/experiments/analyze", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["protocol_snapshot"]["revision"] == 1
    assert data["protocol_snapshot"]["protocol"] == old
    assert any("历史设计" in w for w in data["warnings"])
    assert not any("种子集合不一致" in w or "指标列名" in w for w in data["warnings"])
    assert (
        client.post(
            "/api/experiments/analyze", json={**body, "protocol_revision": 4}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/experiments/analyze", json={**body, "protocol_id": None}
        ).status_code
        == 422
    )
    latest = client.post(
        "/api/experiments/analyze", json={**body, "protocol_revision": None}
    ).json()
    assert latest["protocol_snapshot"]["revision"] == 3
    assert any("未显式选择" in w for w in latest["warnings"])
    client.post(
        "/api/account/register",
        json={"name": "second-round5", "password": "test-password-876"},
    )
    assert client.post("/api/experiments/analyze", json=body).status_code == 404


@pytest.mark.parametrize(
    "claim,quote,reject",
    [
        ("方法快3倍。", "It runs up to 3× faster in these experiments.", True),
        ("方法最高快3倍。", "It runs up to 3× faster in these experiments.", False),
        ("它减少 HBM 与 SRAM 之间的访问。", "We reduce HBM accesses.", True),
        (
            "它减少GPU高带宽内存HBM和芯片内SRAM之间的访问。",
            "We reduce HBM accesses.",
            True,
        ),
        (
            "它减少 HBM 与 SRAM 之间的访问。",
            "We reduce accesses between HBM and SRAM.",
            False,
        ),
        (
            "二维嵌入没有带来显著提升。",
            "We have not observed significant gains with 2D embeddings.",
            True,
        ),
        (
            "实验中未观察到二维嵌入带来的显著提升。",
            "We have not observed significant gains with 2D embeddings.",
            False,
        ),
        (
            "二维嵌入没有带来显著提升。",
            "The method does not improve performance.",
            False,
        ),
        (
            "其运行时间随序列长度线性增长。",
            "Runtime improves proportionally as sparsity increases.",
            True,
        ),
        ("该算法最优。", "The algorithm uses fewer memory accesses.", True),
        (
            "可以直接在一次前向中混合不同任务。",
            "We switch tasks by replacing matrices.",
            True,
        ),
        (
            "可以直接在一次前向中混合不同任务。",
            "It is not straightforward to batch inputs to different tasks.",
            True,
        ),
        (
            "合并权重后，不同任务混合输入并不直接可行。",
            "It is not straightforward to batch inputs to different tasks if weights are merged.",
            False,
        ),
        (
            "合并权重后，不能直接在一次前向中混合不同任务。",
            "It is not straightforward to batch inputs to different tasks if weights are merged.",
            False,
        ),
    ],
)
def test_preserve_scope_and_distinguish_operations(claim, quote, reject):
    assert semantic_overreach(claim, quote) == reject


def test_concept_evidence_keeps_method_not_bibliography(monkeypatch):
    blocks = [
        {
            "id": "ref",
            "text": "Author. Initialization and regularization. Proceedings2020.",
        },
        {
            "id": "init",
            "text": "We use a random Gaussian initialization for one factor and zero for the other factor, before training.",
        },
    ]
    monkeypatch.setattr(store, "search", lambda q, ids, limit: blocks)
    assert [
        b["id"] for b in query_facets.concept_evidence("矩阵如何初始化", ["doc"])
    ] == ["init"]
    assert query_facets.concept_evidence("作者是谁", ["doc"]) == []


@pytest.mark.parametrize(
    "index,span,count,claim_text",
    [
        ("0", "We use random projections in this method.", 1, "该方法使用随机投影。"),
        ("0", "We use an unrelated invented algorithm.", 0, "该方法使用随机投影。"),
        ("4", "We use random projections in this method.", 0, "该方法使用随机投影。"),
        ("0", "We use random projections in this method.", 0, "该方法提升15%。"),
    ],
)
def test_grounded_requires_real_support_span(
    monkeypatch, index, span, count, claim_text
):
    block = {
        "id": "b",
        "document_id": "d",
        "title": "Paper",
        "page": 1,
        "text": "We use random projections in this method. The baseline achieves 15% improvement.",
    }
    monkeypatch.setattr(
        store, "get_document", lambda identifier: {"title": "Paper", "metadata": {}}
    )
    monkeypatch.setattr(research.retrieval, "search", lambda *args: [block])
    monkeypatch.setattr(research, "expand_neighbors", lambda blocks, limit: blocks)

    async def complete(system, prompt, **kwargs):
        if "strict evidence reviewer" in system:
            allowed = kwargs["schema"]["properties"]["decisions"]["properties"]["0"][
                "properties"
            ]["support_span"]["enum"]
            assert "We use random projections in this method." in allowed
            return {
                "decisions": {
                    index: {"verdict": "supported_relevant", "support_span": span}
                }
            }
        if "Compare EVERY" in system:
            return {"unanswered_parts": [], "claims": []}
        return {
            "claims": [{"text": claim_text, "evidence_id": "E1"}],
            "limitations": "",
        }

    monkeypatch.setattr(research.model, "complete", complete)
    result = asyncio.run(research.grounded("What method is used?", ["d"]))
    assert len(result["claims"]) == count
    if count:
        assert result["claims"][0]["support_span"] == span


def test_support_options_preserve_pdf_text_and_late_passages():
    from backend.claim_checks import support_passages

    source = "ViT-Base\n12\n768\n3072\n12\n86M"
    options = support_passages(source)
    assert store.quote_normalize(source) in options
    assert all(store.quote_in_source(p, source) for p in options)
    assert not any("Layers:" in p for p in options)
    long_source = (
        "A long source paragraph without punctuation " * 90
        + "The final condition must be retained."
    )
    options = support_passages(long_source)
    assert any("The final condition must be retained." in p for p in options)
    assert all(
        len(p) <= 1600 and store.quote_in_source(p, long_source) for p in options
    )
