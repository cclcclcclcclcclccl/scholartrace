"""Source preservation, conflict handling and useful research workflow boundaries."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import (
    accounts,
    charts,
    database,
    discovery,
    model,
    research,
    store,
    translation,
)
from backend.app import app
from backend.claim_checks import duplicate_claim, semantic_overreach
from backend.workspace_tools import evidence_matrix


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "main.sqlite3")
    monkeypatch.setattr(accounts, "AUTH_PATH", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(
        accounts, "path", lambda identifier: tmp_path / identifier / "library.sqlite3"
    )
    database.initialize()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def paper(client):
    return store.import_pdf(store.ROOT / "data/competition/pdf/1706.03762v1.pdf")


def test_reader_search_bookmark_and_metadata_preservation(client, paper):
    identifier = paper["id"]
    original = store.get_document(identifier)["metadata"]
    prefix = f"/api/documents/{identifier}"
    result = client.get(prefix + "/find", params={"q": "P100"}).json()
    assert result["total"] > 0
    hit = result["hits"][0]
    assert hit["document_id"] == identifier and len(hit["bbox"]) == 4
    assert "P100" in hit["text"]
    assert client.post(prefix + "/bookmarks", json={"page": 999}).status_code == 422
    assert client.post(
        prefix + "/bookmarks", json={"page": 7, "label": "训练条件"}
    ).json() == [{"page": 7, "label": "训练条件"}]
    assert (
        client.patch(
            prefix + "/organization",
            json={
                "tags": ["基线", "基线"],
                "collection": "复现",
                "reading_status": "reproduce",
            },
        ).status_code
        == 200
    )
    changed = store.get_document(identifier)["metadata"]
    assert all(changed[k] == v for k, v in original.items())
    assert changed["tags"] == ["基线"]
    assert (
        client.get("/api/library/organization?tag=基线").json()[0]["id"] == identifier
    )
    client.delete(prefix + "/bookmarks/7")
    assert client.get(prefix + "/bookmarks").json() == []


def test_translation_history_stale_write_and_original_untouched(client, paper):
    block = store.get_blocks(paper["id"])[0]
    with store.connection() as c:
        c.execute(
            "INSERT INTO translations VALUES(?,?,?,?)",
            (block["id"], "zh", "旧译文", "test-model"),
        )
    url = "/api/translations/" + block["id"]
    assert (
        client.patch(url, json={"previous": "旧译文", "text": "校正译文"}).status_code
        == 200
    )
    assert (
        client.patch(url, json={"previous": "旧译文", "text": "覆盖"}).status_code
        == 409
    )
    history = client.get(url + "/history").json()
    assert history[0]["text"] == "旧译文" and history[0]["model"] == "test-model"
    assert store.get_blocks(paper["id"])[0]["text"] == block["text"]


def test_glossary_is_account_local(client):
    assert (
        client.put(
            "/api/translation/glossary",
            json={"terms": [{"source": "attention", "target": "注意力"}]},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/account/register",
            json={"name": "workspace-owner", "password": "workspace-pass-123"},
        ).status_code
        == 200
    )
    assert client.get("/api/translation/glossary").json() == []


def test_glossary_keeps_code_formulas_urls_and_signed_numbers():
    source = "attention uses -3.5 and `attention(x)` with $attention=2$ and https://example.org/attention"
    protected, originals = translation.protect(
        source, [{"source": "attention", "target": "注意力"}]
    )
    for i, value in enumerate(originals):
        protected = protected.replace(f"ZXQKEEP{i}QXZ", value)
    assert protected == source.replace("attention uses", "注意力 uses")
    assert "-3.5" in originals
    assert translation.quality_signals("This may not converge.", "它收敛。", "zh")[
        "warnings"
    ]


def test_chart_scatter_and_log_guards():
    spec = {
        "csv": "step,loss\n1,0.5\n10,0.1",
        "x": "step",
        "ys": ["loss"],
        "kind": "scatter",
        "xscale": "log",
        "yscale": "log",
    }
    assert charts.prepare(spec)[0] == ["1", "10"]
    with pytest.raises(ValueError, match="大于 0"):
        charts.prepare({**spec, "csv": "step,loss\n1,0"})
    with pytest.raises(ValueError, match="数值横轴"):
        charts.prepare({**spec, "csv": "step,loss\na,0.5"})
    with pytest.raises(ValueError, match="对数刻度"):
        charts.prepare({**spec, "kind": "table", "xscale": "linear"})


def test_chart_intent_rejects_invented_columns(client, monkeypatch):
    async def fake(*args, **kwargs):
        return {"x": "invented", "ys": ["loss"], "kind": "scatter"}

    monkeypatch.setattr(model, "complete", fake)
    response = client.post(
        "/api/charts/plan", json={"csv": "step,loss\n1,0.5", "intent": "用散点图比较"}
    )
    assert response.status_code == 422


def test_matrix_preserves_missing_evidence_and_exports_followups(
    client, paper, monkeypatch
):
    class Context:
        def check(self):
            pass

        def progress(self, *args):
            pass

    async def absent(question, ids, ctx):
        return {"claims": [], "evidence": [], "limitations": "未找到证据"}

    monkeypatch.setattr(research, "grounded", absent)
    result = asyncio.run(
        evidence_matrix(
            Context(), {"document_ids": [paper["id"]], "fields": ["训练时长？"]}
        )
    )
    assert result["matrix"][0]["cells"][0]["status"] == "未找到可核验答案"
    assert len(result["missing_items"]) == 1
    exported = research.export_markdown(research.artifact(result["id"]))
    assert "复现前待补清单" in exported and "不代表论文没有报告" in exported


def test_discovery_cache_marks_stale_and_separates_queries(client, monkeypatch):
    calls = []

    async def live(**kwargs):
        calls.append(kwargs)
        return [{"id": "arxiv:1706.03762", "title": "real source"}]

    monkeypatch.setattr(discovery, "search", live)

    async def run():
        first = await discovery.search_cached("attention", year_from=2020)
        assert first[0]["retrieval_status"] == "live"
        second = await discovery.search_cached("attention", year_from=2020)
        assert second[0]["retrieval_status"] == "cache" and len(calls) == 1
        await discovery.search_cached("attention", year_from=2021)
        assert len(calls) == 2

        async def unavailable(**kwargs):
            raise httpx.ConnectError("offline")

        monkeypatch.setattr(discovery, "search", unavailable)
        stale = await discovery.search_cached("attention", year_from=2020, force=True)
        assert stale[0]["retrieval_status"] == "stale_after_error"
        with pytest.raises(httpx.ConnectError):
            await discovery.search_cached("different query")

    asyncio.run(run())
    assert (
        client.post(
            "/api/discover/search",
            json={"query": "x", "year_from": 2026, "year_to": 2020},
        ).status_code
        == 422
    )


def test_training_length_not_context_window_and_distinct_claims_retained():
    quote = "We train for 100 epochs on minibatches of 64 randomly sampled, contiguous sequences of 512 tokens."
    assert semantic_overreach("模型上下文窗口为 512 tokens。", quote)
    assert not semantic_overreach("训练序列长度为 512 tokens。", quote)
    assert not semantic_overreach(
        "上下文窗口为 2048。", "All models use a context window of 2048 tokens."
    )
    old = [{"block_id": "b", "text": "模型隐藏维度为 768。"}]
    assert duplicate_claim("模型隐藏维度为768。", "b", old)
    assert not duplicate_claim("模型隐藏维度为 1024。", "b", old)


def test_writing_versions_conflict_and_evidence_unchanged(client):
    original = {"sections": [{"title": "证据", "claims": [], "evidence": []}]}
    item = research.save_artifact("writing", "写作试验", original)
    url = "/api/artifacts/" + item["id"] + "/draft"
    assert (
        client.patch(url, json={"text": "研究设想", "revision": 0}).json()["revision"]
        == 1
    )
    assert (
        client.patch(url, json={"text": "过期覆盖", "revision": 0}).status_code == 409
    )
    assert (
        client.patch(url, json={"text": "修改后的研究设想", "revision": 1}).json()[
            "revision"
        ]
        == 2
    )
    saved = research.artifact(item["id"])
    assert saved["content"]["sections"] == original["sections"]
    assert saved["content"]["draft_history"][0]["text"] == "研究设想"
    assert "人工编辑稿（尚未逐句核验）" in research.export_markdown(saved)


def test_reranked_definition_recovers_adjacent_specification(client):
    from backend.evidence_context import expand_neighbors

    paper = store.import_pdf(store.ROOT / "data/competition/pdf/N19-1423.pdf")
    definition = next(
        b
        for b in store.get_blocks(paper["id"])
        if b["id"] == "0c663f20fa030f1fe93e071c"
    )
    expanded = expand_neighbors([{**definition, "title": paper["title"]}], limit=10)
    assert any(b["id"] == "e4c514e7679fdb7e75544966" for b in expanded)


def test_matrix_enters_version_impact_without_duplicating_cells(
    client, paper, monkeypatch
):
    from backend import impact

    new = store.import_pdf(store.ROOT / "data/competition/pdf/1706.03762v7.pdf")
    block = next(b for b in store.get_blocks(paper["id"]) if "P100" in b["text"])
    claim = {
        **block,
        "block_id": block["id"],
        "quote": block["text"],
        "text": "论文报告了训练硬件。",
    }
    saved = research.save_artifact(
        "matrix",
        "复现硬件矩阵",
        {
            "matrix": [{"cells": [{"claims": [claim]}]}],
            "sections": [{"claims": [claim]}],
            "draft": {"text": "尚未核验的人工草稿", "revision": 1},
        },
    )

    async def fake_review(*args):
        return {"status": "test", "decision": "same_claim", "reason": "test double"}

    monkeypatch.setattr(impact, "review_change", fake_review)

    class Context:
        def progress(self, *args):
            pass

    result = asyncio.run(impact.impact(Context(), {"document_id": new["id"]}))
    assert result["total_dependencies"] == 1
    assert result["impact"][0]["artifact_id"] == saved["id"]
    assert (
        research.artifact(saved["id"])["content"]["draft"]["text"]
        == "尚未核验的人工草稿"
    )


def test_writing_background_is_only_verified_work(client, monkeypatch):
    async def related(*args):
        return {"claims": [], "evidence": []}

    async def proposed(*args, **kwargs):
        return {
            "method_plan": "拟议设置：固定训练条件，改变单个变量。",
            "evaluation": {
                k: "待确定；先核对数据、测量资源，再冻结实验方案。"
                for k in [
                    "待验证假设",
                    "基线与消融",
                    "数据及训练测试划分",
                    "指标与判定标准",
                    "资源与可行性",
                    "失败条件",
                ]
            },
            "introduction": "模型捏造的已有研究结论",
        }

    monkeypatch.setattr(research, "grounded", related)
    monkeypatch.setattr(model, "complete", proposed)

    class Context:
        def progress(self, *args):
            pass

    result = asyncio.run(research.writing(Context(), {"topic": "研究想法"}))
    assert "捏造" not in result["proposal"]["introduction"]
    assert "未找到可核验" in result["proposal"]["introduction"]
    assert "失败条件：\n" in result["proposal"]["evaluation_plan"]


def test_proposal_checks_flag_metric_mismatch_and_missing_timing():
    from backend.proposal_checks import assess_plan

    issues = assess_plan(
        {
            "method_plan": "候选 WikiText-2 或 GLUE，待选择。",
            "evaluation_plan": "小数据集按比例划分，评价 BLEU 和推理耗时，显著提升。",
        }
    )
    assert any("语言建模" in x for x in issues)
    assert any("GLUE" in x for x in issues)
    assert any("预热" in x for x in issues)
    assert any("划分" in x for x in issues)
    assert any("统计检验" in x for x in issues)


def test_writing_does_not_turn_recommendation_into_cited_fact(
    client, paper, monkeypatch
):
    block = store.get_blocks(paper["id"])[0]

    async def related(*args):
        return {
            "claims": [
                {
                    "text": "零预算可以完成所有实验。",
                    "quote": block["text"],
                    "block_id": block["id"],
                    "document_id": paper["id"],
                    "page": block["page"],
                }
            ],
            "evidence": [block],
        }

    async def proposed(*args, **kwargs):
        return {
            "method_plan": "拟议设置：先实测资源，再选择可行实验。",
            "evaluation": {
                k: "待确定；冻结数据与训练条件。"
                for k in [
                    "待验证假设",
                    "基线与消融",
                    "数据及训练测试划分",
                    "指标与判定标准",
                    "资源与可行性",
                    "失败条件",
                ]
            },
        }

    monkeypatch.setattr(research, "grounded", related)
    monkeypatch.setattr(model, "complete", proposed)

    class Context:
        def progress(self, *args):
            pass

    result = asyncio.run(research.writing(Context(), {"topic": "零预算实验"}))
    assert "完成所有实验" not in result["proposal"]["introduction"]
    assert result["sections"][0]["claims"][0]["text"] == "原文摘录：" + block["text"]


def test_attention_plan_dimension_and_checkpoint_risks(client):
    fields = {
        "method_plan": "选择预训练模型，调整注意力头数量；保持 dmodel、dk、dv 不变。",
        "evaluation_plan": "按模型和任务需求进行划分。",
    }
    saved = research.save_artifact("writing", "维度检查", {"proposal": fields})
    checked = research.artifact(saved["id"])
    assert any("d_model = h" in x for x in checked["content"]["plan_checks"])
    assert any("权重" in x for x in checked["content"]["plan_checks"])
    assert checked["content"]["proposal"] == fields
    assert any("划分" in x for x in checked["content"]["plan_checks"])


def test_performance_percentage_does_not_satisfy_data_split():
    from backend.proposal_checks import assess_plan

    checks = assess_plan(
        {
            "evaluation_plan": "数据及训练测试划分：\n按任务需求划分。\n\n指标与判定标准：\n耗时增幅不超过 10%。"
        }
    )
    assert any("明确训练" in x for x in checks)
