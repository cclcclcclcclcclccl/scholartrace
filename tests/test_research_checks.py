import asyncio
import copy

from backend.answer_contract import checklist
from backend.comparison_readiness import audit


def test_question_requirements_are_distinct_and_do_not_claim_completeness():
    claims = [{"text": "训练1个epoch。", "block_id": "a", "document_id": "paper"}]
    original = copy.deepcopy(claims)
    result = checklist("训练多少epoch，学习率与batch size是多少？请保留限制。", claims)
    items = {item["id"]: item for item in result["items"]}
    assert items["epochs"]["status"] == "candidate"
    assert items["learning_rate"]["status"] == "unlocated"
    assert items["batch"]["status"] == "unlocated"
    assert items["limits"]["status"] == "unlocated"
    assert "不代表已答全" in result["notice"]
    assert claims == original


def test_empty_and_unrecognized_requests_do_not_invent_coverage():
    assert checklist("你好", [])["items"] == []
    item = checklist("为什么？", [])["items"][0]
    assert item["status"] == "unlocated" and item["related"] == []
    assert "原问题：为什么？" in item["followup"]
    assert (
        checklist("What is the learning rate?", [])["items"][0]["id"] == "learning_rate"
    )


def test_related_statements_preserve_paper_and_source_identity():
    claims = [
        {"text": "因为结构不同。", "block_id": "a", "document_id": "one"},
        {"text": "因为数据不同。", "block_id": "b", "document_id": "two"},
    ]
    related = checklist("为什么？", claims)["items"][0]["related"]
    assert [r["document_id"] for r in related] == ["one", "two"]
    assert [r["block_id"] for r in related] == ["a", "b"]


def test_grounding_wrapper_preserves_output_and_export(monkeypatch):
    from backend import research

    result = {"claims": [], "evidence": [], "limitations": "未检索到可用原文。"}

    async def original(*args):
        return copy.deepcopy(result)

    monkeypatch.setattr(research, "_grounded", original)
    response = asyncio.run(research.grounded("为什么？", ["p"]))
    assert {k: response[k] for k in result} == result
    exported = research.export_markdown(
        {
            "title": "test",
            "kind": "answer",
            "content": {"sections": [{"title": "回答", **response}]},
        }
    )
    assert "回答核对清单" in exported and "未定位到对应表述" in exported


def content(a, b):
    return {
        "fields": {
            "object": "研究对象",
            "metric": "指标与结果",
            "conditions": "实验条件",
        },
        "papers": [
            {"document_id": "one", "title": "A", "cells": a},
            {"document_id": "two", "title": "B", "cells": b},
        ],
    }


def test_comparison_audit_uses_quotes_not_user_invented_units():
    value = content(
        {
            "metric": {"value": "99 GB", "quote": "Accuracy is 90 percent."},
            "conditions": {"quote": "We pre-train the model."},
        },
        {
            "metric": {"quote": "Latency is 10 milliseconds."},
            "conditions": {"quote": "During inference."},
        },
    )
    before = copy.deepcopy(value)
    result = audit(value)
    assert result["missing_cells"] == 2 and len(result["hints"]) == 2
    assert result["papers"][0]["units"] == ["%"]
    assert result["papers"][1]["units"] == ["ms"]
    assert value == before


def test_matching_units_and_filled_cells_never_certify_comparability():
    cells = {
        "object": {"quote": "Model"},
        "metric": {"quote": "Score 50 percent."},
        "conditions": {"quote": "During inference."},
    }
    result = audit(content(cells, cells))
    assert result["missing_cells"] == 0 and not result["hints"]
    assert "相同单位不证明可比" in result["notice"]
    assert "comparable" not in result


def test_empty_cells_and_unknown_units_are_not_reported_as_same_units():
    result = audit(content({}, {"metric": {"quote": "Metric is described elsewhere."}}))
    assert result["missing_cells"] == 5
    assert all(not p["units"] for p in result["papers"])
    assert not result["hints"]


def test_millisecond_and_second_symbols_are_distinguished():
    result = audit(
        content(
            {"metric": {"quote": "10ms / 20毫秒 and 2s"}},
            {"metric": {"quote": "The model's microseconds are not measured here."}},
        )
    )
    assert result["papers"][0]["units"] == ["ms", "s"]
    assert result["papers"][1]["units"] == []
