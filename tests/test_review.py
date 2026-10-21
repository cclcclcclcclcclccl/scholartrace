import asyncio

import httpx
import pytest

from backend.review import review_change


def run_response(value, item=None):
    item = item or {
        "status": "review_required",
        "note": {
            "note": "Implementation access",
            "quote": "We intend to make the code available soon.",
        },
        "candidate": {
            "text": "Our code is available at https://example.org/\nresearch."
        },
    }

    async def execute():
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": __import__("json").dumps(value)}}
                    ]
                },
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            return await review_change(item, client, "http://127.0.0.1/v1", "test")

    return asyncio.run(execute())


def test_semantic_review_rejects_invented_source():
    result = run_response(
        {
            "decision": "claim_changed",
            "reason": "测试",
            "old_quote": "We intend to make the code available soon.",
            "new_quote": "The code was deleted permanently.",
        }
    )
    assert result["status"] == "unavailable"


def test_semantic_review_retains_both_real_quotes():
    result = run_response(
        {
            "decision": "claim_changed",
            "reason": "从计划发布变为已发布",
            "old_quote": "make the code available soon",
            "new_quote": "Our code is available",
        }
    )
    assert result["status"] == "model_assessment"
    assert result["source_quotes_verified"] is True
    assert result["decision"] == "claim_changed"


def test_review_accepts_pdf_wrapped_url_without_changing_numbers():
    result = run_response(
        {
            "decision": "claim_changed",
            "reason": "从计划发布变为已发布",
            "old_quote": "make the code available soon",
            "new_quote": "Our code is available at https://example.org/research.",
        }
    )
    assert result["status"] == "model_assessment"
    from backend.store import normalize

    assert normalize("1 2") != normalize("12")


def test_explicit_code_release_transition_preserves_exact_evidence():
    item = {
        "status": "review_required",
        "note": {
            "note": "Code availability",
            "quote": "We intend to make our code available soon.",
        },
        "candidate": {
            "text": "Our code is now available at https://example.org/research."
        },
    }
    result = run_response({}, item)
    assert result["decision"] == "claim_changed"
    assert result["method"] == "explicit_code_release_transition"
    assert result["old_quote"] == item["note"]["quote"]
    assert result["new_quote"] == item["candidate"]["text"]


@pytest.mark.parametrize(
    "text",
    [
        "We do not plan to release the code.",
        "We will not make the code available.",
        "Our code is available now; we will extend it soon.",
        "We might release the code if funding is approved.",
        "We intend to make the code documentation available soon.",
    ],
)
def test_release_rule_does_not_turn_negation_or_unrelated_future_into_a_plan(text):
    from backend.review import planned_code_release

    assert not planned_code_release(text)


def test_sentence_indices_copy_exact_nonadjacent_evidence_and_reject_bad_index():
    item = {
        "status": "review_required",
        "note": {
            "note": "Training setup",
            "quote": "There are 12 layers. Adam is used. The batch size is 64.",
        },
        "candidate": {
            "text": "There are 24 layers. Adam is used. The batch size is 128."
        },
    }
    value = {
        "old_indices": [0, 2],
        "new_indices": [0, 2],
        "decision": "claim_changed",
        "reason": "层数和批大小变化",
    }
    result = run_response(value, item)
    assert result["source_quotes_verified"]
    assert result["old_quotes"] == ["There are 12 layers.", "The batch size is 64."]
    assert result["new_quotes"] == ["There are 24 layers.", "The batch size is 128."]
    assert run_response({**value, "new_indices": [3]}, item)["status"] == "unavailable"


@pytest.mark.parametrize(
    "updated",
    [
        "The code documentation is available at https://example.org/docs.",
        "The code is private; the documentation is available at https://example.org/docs.",
        "We do not claim that the code is available at https://example.org/research.",
    ],
)
def test_documentation_or_negation_is_not_treated_as_code_release(updated):
    item = {
        "status": "review_required",
        "note": {
            "note": "Code availability",
            "quote": "We intend to make our code available soon.",
        },
        "candidate": {"text": updated},
    }
    assert run_response({}, item).get("method") != "explicit_code_release_transition"


def test_code_release_relative_clause_in_real_transformer_sentence():
    from backend.review import planned_code_release

    assert planned_code_release(
        "We intend to make the code we used to train and evaluate our models available soon."
    )


def test_changed_decision_with_identical_quotes_is_not_presented_as_change():
    item = {
        "status": "review_required",
        "note": {
            "note": "There are 20 checkpoints.",
            "quote": "We averaged the last 20 checkpoints. [34]",
        },
        "candidate": {"text": "We averaged the last 20 checkpoints. [38]"},
    }
    value = {
        "decision": "claim_changed",
        "reason": "changed",
        "old_quote": "We averaged the last 20 checkpoints.",
        "new_quote": "We averaged the last 20 checkpoints.",
    }

    async def run():
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": __import__("json").dumps(value)}}
                    ]
                },
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            return await review_change(item, client, "http://127.0.0.1/v1", "test")

    result = asyncio.run(run())
    assert result["decision"] == "unclear"
    assert result["raw_model_decision"] == "claim_changed"


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("The batch size is 64.", "The batch size is 128."),
        ("We use 8 GPUs.", "We use 16 GPUs."),
        ("The loss is 0.001.", "The loss is 0.01."),
        ("The effect is -3.5%.", "The effect is 3.5%."),
        ("The model does converge.", "The model does not converge."),
        ("We never share training data.", "We share training data."),
    ],
)
def test_same_claim_with_explicit_conflict_requires_review(old, new):
    item = {
        "status": "review_required",
        "note": {"note": "Compare the stated condition", "quote": old},
        "candidate": {"text": new},
    }
    result = run_response(
        {
            "decision": "same_claim",
            "reason": "模型认为相同",
            "old_indices": [0],
            "new_indices": [0],
        },
        item,
    )
    assert result["decision"] == "unclear"
    assert result["raw_model_decision"] == "same_claim"
    assert result["consistency_warnings"]
    assert result["old_quote"] == old and result["new_quote"] == new


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("The rate is 0.001.", "The rate is 1e-3."),
        ("We use 1,000 samples.", "We use 1000 samples."),
        (
            "We use 8 GPUs. A new benchmark reports 9 points.",
            "We use 8 GPUs. A new benchmark reports 12 points.",
        ),
    ],
)
def test_same_claim_guard_preserves_equivalent_or_unselected_numbers(old, new):
    item = {
        "status": "review_required",
        "note": {"note": "Setup", "quote": old},
        "candidate": {"text": new},
    }
    result = run_response(
        {
            "decision": "same_claim",
            "reason": "same",
            "old_indices": [0],
            "new_indices": [0],
        },
        item,
    )
    assert result["decision"] == "same_claim"
    assert not result.get("consistency_warnings")


def test_numeric_citation_difference_without_mapping_is_not_auto_confirmed():
    item = {
        "status": "review_required",
        "note": {"note": "Evidence", "quote": "We use the method in [12]."},
        "candidate": {"text": "We use the method in [14]."},
    }
    result = run_response(
        {
            "decision": "same_claim",
            "reason": "same",
            "old_indices": [0],
            "new_indices": [0],
        },
        item,
    )
    assert result["decision"] == "unclear"


def test_audit_limit_explicitly_marks_unchecked_rows(monkeypatch):
    from backend import app as app_module

    async def checked(*args):
        return {
            "status": "model_assessment",
            "decision": "same_claim",
            "reason": "same",
        }

    monkeypatch.setattr(app_module, "document", lambda identifier: None)
    monkeypatch.setattr(
        app_module.audit,
        "audit_against",
        lambda identifier: {"results": [{"note": {"id": i}} for i in range(14)]},
    )
    monkeypatch.setattr(app_module, "review_change", checked)
    result = asyncio.run(
        app_module.audit_version(app_module.AuditTarget(target_document_id="target"))
    )
    assert (
        len(
            [
                i
                for i in result["results"]
                if i["semantic_review"]["status"] == "model_assessment"
            ]
        )
        == 12
    )
    assert all(
        i["semantic_review"]["status"] == "not_checked" for i in result["results"][12:]
    )


@pytest.mark.parametrize(("selected_old", "selected_new"), [(0, 0), (1, 1)])
def test_gpu_observation_not_changed_by_unrelated_score(selected_old, selected_new):
    item = {
        "status": "review_required",
        "note": {
            "note": "GPU 数量是否变化",
            "quote": "We use 8 GPUs. The score is 25.",
        },
        "candidate": {"text": "We use 8 GPUs. The score is 30."},
    }
    result = run_response(
        {
            "decision": "claim_changed",
            "reason": "分数变化",
            "old_indices": [selected_old],
            "new_indices": [selected_new],
        },
        item,
    )
    assert result["decision"] == "same_claim"
    assert result["method"] == "identical_scoped_numeric_sentence"


def test_focus_guard_does_not_suppress_actual_gpu_change():
    item = {
        "status": "review_required",
        "note": {"note": "GPU 数量", "quote": "We use 8 GPUs. The score is 25."},
        "candidate": {"text": "We use 16 GPUs. The score is 30."},
    }
    result = run_response(
        {
            "decision": "claim_changed",
            "reason": "GPU 变化",
            "old_indices": [0],
            "new_indices": [0],
        },
        item,
    )
    assert result["decision"] == "claim_changed"
