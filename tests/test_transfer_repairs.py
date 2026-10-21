import asyncio

import pytest

from backend import research, source_scope, subquestions
from backend.claim_checks import (
    retain_stage_heading,
    semantic_overreach,
    support_passages,
)
from backend.evidence_review import supported_span


@pytest.mark.parametrize("ending", ["请分别回答。", "逐项作答。", "请依次说明。"])
def test_format_request_does_not_create_an_answerable_question(ending):
    parts = subquestions.split_question("样本多少？训练需要多久？" + ending)
    assert len(parts) == 2
    assert ending in parts[-1]["question"]
    # A substantive new request must still get its own coverage item.
    assert (
        len(subquestions.split_question("样本多少？请分别回答训练与推理的内存占用。"))
        == 2
    )


def test_stage_heading_is_literal_contiguous_context_not_numeric_whitelist():
    quote = "Stage 1: Feature alignment. We use 2 GPUs. The encoder stays frozen and only the projection is trained."
    sentence = "The encoder stays frozen and only the projection is trained."
    span = retain_stage_heading(sentence, quote)
    assert span == quote
    assert sentence not in support_passages(quote)
    assert supported_span(
        {"text": "Stage 1 冻结编码器，仅训练投影层。", "quote": quote}, span
    )
    # The digit 2 occurs in the quote but is hardware count, not stage identity.
    assert semantic_overreach("Stage 2 冻结编码器。", span)
    assert not supported_span({"text": "Stage 2 冻结编码器。", "quote": quote}, span)
    assert not supported_span({"text": "Stage 1 使用8个GPU。", "quote": quote}, span)


def test_heading_never_crosses_another_stage_or_invents_a_source():
    text = "Stage 1: Frozen. Stage 2: Unfrozen. We update all weights."
    assert (
        retain_stage_heading("We update all weights.", text) == "We update all weights."
    )
    assert (
        retain_stage_heading("Invented sentence.", "Stage 1: Frozen.")
        == "Invented sentence."
    )
    assert (
        retain_stage_heading(
            "End sentence.", "Stage 1: " + "x" * 1700 + " End sentence."
        )
        == "End sentence."
    )


@pytest.mark.parametrize(
    "generated", [[], [{"text": "编码器固定。", "evidence_id": "E1"}]]
)
def test_empty_selector_gets_one_bounded_extraction_without_asserting_support(
    monkeypatch, generated
):
    b = {
        "id": "b",
        "document_id": "doc",
        "page": 1,
        "title": "Paper",
        "text": "The encoder remains fixed during training.",
    }
    monkeypatch.setattr(subquestions.retrieval, "search", lambda *args: [b])
    monkeypatch.setattr(subquestions, "concept_evidence", lambda *args: [])
    monkeypatch.setattr(source_scope, "explicit_scope_evidence", lambda *args: [])
    monkeypatch.setattr(subquestions, "expand_neighbors", lambda blocks, limit: blocks)
    monkeypatch.setattr(subquestions, "attach_table_headers", lambda blocks: blocks)
    calls = []

    async def select(*args, **kwargs):
        return {"selected": []}

    async def answer(*args, **kwargs):
        calls.append(args)
        assert kwargs["reasoning"] is False
        return {"claims": generated}

    monkeypatch.setattr(subquestions.model, "complete", select)
    monkeypatch.setattr(research, "single_answer", answer)
    result, _, records = asyncio.run(
        subquestions.answer_parts(
            subquestions.split_question("是否固定编码器？"), ["doc"], [b], "Paper"
        )
    )
    assert len(calls) == 1
    assert records[0]["selection_fallback"]
    assert "selected_evidence_ids" not in records[0]
    assert len(result["claims"]) == len(generated)
    assert all("support_review" not in claim for claim in result["claims"])
