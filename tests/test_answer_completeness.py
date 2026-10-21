import asyncio

from backend import answer_completeness


def test_absent_purpose_does_not_trigger_speculative_generation(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("No model call should guess an unstated purpose")

    monkeypatch.setattr(answer_completeness.model, "complete", forbidden)
    result = asyncio.run(
        answer_completeness.handling_use(
            "是否保留？",
            [{"evidence_id": "E1", "text": "这些样本被保留。"}],
            "[E1] We retain type-X examples with probability 0.2.",
            1,
        )
    )
    assert result == {"uses": []}


def test_existing_purpose_is_scoped_to_its_evidence_id():
    evidence = "[E1] We use retained examples to train a detector.\n\n[E2] We use retained examples for calibration."
    claims = [
        {"evidence_id": "E1", "text": "这些样本用于训练检测器。"},
        {"evidence_id": "E2", "text": "另一类样本也保留。"},
    ]
    assert answer_completeness.eligible_uses(claims, evidence) == {"E2"}


def test_use_completion_does_not_repeat_retention_or_sampling(monkeypatch):
    async def complete(*args, **kwargs):
        return {
            "uses": [
                {"evidence_id": "E1", "text": "这些样本用于训练检测器。"},
                {"evidence_id": "E1", "text": "这些样本以0.2的概率保留。"},
            ]
        }

    monkeypatch.setattr(answer_completeness.model, "complete", complete)
    result = asyncio.run(
        answer_completeness.handling_use(
            "是否保留？",
            [{"evidence_id": "E1", "text": "这些样本以0.2的概率保留。"}],
            "[E1] We retain these examples with probability 0.2 and use them to train a detector.",
            1,
        )
    )
    assert result == {
        "uses": [{"evidence_id": "E1", "text": "这些样本用于训练检测器。"}]
    }


def test_model_cannot_add_use_from_ineligible_source(monkeypatch):
    async def complete(*args, **kwargs):
        return {
            "uses": [
                {"evidence_id": "E1", "text": "用于检测。"},
                {"evidence_id": "E2", "text": "用于分类。"},
            ]
        }

    monkeypatch.setattr(answer_completeness.model, "complete", complete)
    evidence = "[E1] We use retained examples to train a detector.\n\n[E2] We retain type-Y examples with probability 0.2."
    result = asyncio.run(
        answer_completeness.handling_use(
            "是否保留？",
            [{"evidence_id": "E1", "text": "这些样本被保留。"}],
            evidence,
            2,
        )
    )
    assert result == {"uses": [{"evidence_id": "E1", "text": "用于检测。"}]}


def test_unrelated_paragraph_is_excluded_from_model_prompt(monkeypatch):
    async def complete(system, prompt, **kwargs):
        assert "transcript history" not in prompt
        assert kwargs["schema"]["properties"]["uses"]["items"]["properties"][
            "evidence_id"
        ]["enum"] == ["E1"]
        return {"uses": [{"evidence_id": "E1", "text": "这些样本用于检测。"}]}

    monkeypatch.setattr(answer_completeness.model, "complete", complete)
    evidence = "[E1] We retain type-X examples and use them to train a detector.\n\n[E2] We use transcript history to resolve ambiguous audio."
    result = asyncio.run(
        answer_completeness.handling_use(
            "X类样本是否排除？",
            [{"evidence_id": "E1", "text": "X类样本保留。"}],
            evidence,
            2,
        )
    )
    assert len(result["uses"]) == 1
