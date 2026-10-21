import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "proof_metrics", Path(__file__).resolve().parents[1] / "scripts/proof_metrics.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_uncertain_is_not_correct_or_removed_for_known_changes():
    rows = [
        {"expected": "claim_changed", "prediction": "unclear"},
        {"expected": "claim_changed", "prediction": "same_claim"},
        {"expected": "same_claim", "prediction": "unavailable"},
        {"expected": "same_claim", "prediction": "same_claim"},
    ]
    score = m.review_metrics(rows)
    assert (
        score["n"] == 4
        and score["exact_correct"] == 1
        and score["exact_accuracy"] == 0.25
    )
    assert score["dangerous_false_safe"] == 1 and score["change_recall"] == 0
    assert (
        score["unchanged_needing_manual_review"] == 1
        and score["safety_policy_manual_review_count"] == 2
    )
    assert score["change_precision"] is None


def test_unknown_ground_truth_does_not_become_easy_false_safe_success():
    score = m.review_metrics(
        [
            {"expected": "unclear", "prediction": "same_claim"},
            {"expected": "unclear", "prediction": "unclear"},
        ]
    )
    assert (
        score["unsupported_decisive_on_unclear"] == 1 and score["unclear_correct"] == 1
    )
    assert score["known_changed"] == 0 and score["change_recall"] is None
    assert m.review_metrics([])["exact_accuracy"] is None
