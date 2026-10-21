import asyncio

from backend import evidence_review
from backend.claim_checks import semantic_overreach, staged_precision_mismatch


def test_bit_widths_cannot_be_exchanged_between_explicit_stages():
    source = "We use 16-bit weights during training and 8-bit weights during inference."
    assert staged_precision_mismatch("训练时使用8位权重，推理时使用16位权重。", source)
    assert not staged_precision_mismatch(
        "训练时使用16位权重，推理时使用8位权重。", source
    )
    assert not staged_precision_mismatch(
        "训练时使用8位权重。", "Training uses 8-bit or 16-bit weights."
    )
    assert not staged_precision_mismatch(
        "训练时使用16位权重。", "Training uses 8-bit or 16-bit weights."
    )


def test_precision_matching_does_not_invent_unspecified_stage():
    assert not staged_precision_mismatch(
        "训练时使用8位权重。", "We quantize weights to 16-bit."
    )
    assert staged_precision_mismatch(
        "Training uses 8-bit weights.", "Training uses 16-bit weights."
    )


def test_span_selection_rejects_invented_and_noncontiguous_ids():
    passages = {
        "P0": "First source sentence.",
        "P1": "Important exception.",
        "P2": "Last source sentence.",
    }
    assert evidence_review.resolve({"support_ids": ["P0", "P2"]}, passages) == ""
    assert evidence_review.resolve({"support_ids": ["P99"]}, passages) == ""
    assert (
        evidence_review.resolve({"support_ids": ["P1", "P0"]}, passages)
        == "First source sentence. Important exception."
    )


def test_selected_true_clause_cannot_support_added_speed():
    source = "Model-A does not use additional text. Model-B uses additional text."
    assert semantic_overreach("Model-A不使用额外文本，而且比Model-B更快。", source)
    assert not semantic_overreach("Model-A更快。", "Model-A is faster on task X.")
    assert not semantic_overreach("Model-A不使用额外文本。", source)


def test_recovery_requires_verifier_and_keeps_complete_context(monkeypatch):
    source = "Model-A is faster on task X. Model-A is slower on task Y."
    calls = []

    async def complete(system, prompt, **kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            return {"support_ids": ["P0"], "verdict": "supported_relevant"}
        assert "slower on task Y" in prompt
        return {
            "decisions": {"0": {"verdict": "changed_conditions", "support_span": ""}}
        }

    monkeypatch.setattr(evidence_review.model, "complete", complete)
    claim = {"text": "Model-A在所有任务上都更快。", "quote": source}
    assert (
        asyncio.run(evidence_review.recover_support(claim, "速度如何？", "Model-A"))
        is None
    )
    assert len(calls) == 2


def test_recovery_rechecks_numeric_support_after_verifier(monkeypatch):
    calls = []

    async def complete(system, prompt, **kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            return {"support_ids": ["P0"], "verdict": "supported_relevant"}
        return {
            "decisions": {
                "0": {
                    "verdict": "supported_relevant",
                    "support_span": "We release the code.",
                }
            }
        }

    monkeypatch.setattr(evidence_review.model, "complete", complete)
    claim = {
        "text": "训练使用200个样本。",
        "quote": "Training uses 200 examples. We release the code.",
    }
    assert (
        asyncio.run(evidence_review.recover_support(claim, "多少样本？", "Test"))
        is None
    )


def test_valid_recovery_returns_exact_source_only(monkeypatch):
    source = "Training uses 200 examples. We release the code."
    calls = []

    async def complete(system, prompt, **kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            return {"support_ids": ["P0"], "verdict": "supported_relevant"}
        return {
            "decisions": {
                "0": {
                    "verdict": "supported_relevant",
                    "support_span": "Training uses 200 examples.",
                }
            }
        }

    monkeypatch.setattr(evidence_review.model, "complete", complete)
    result = asyncio.run(
        evidence_review.recover_support(
            {"text": "训练使用200个样本。", "quote": source}, "多少样本？", "Test"
        )
    )
    assert result["support_span"] == "Training uses 200 examples."
