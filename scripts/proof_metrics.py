"""Strict denominators and abstention-aware metrics for frozen quality diagnostics."""

from collections import Counter
from statistics import median


def review_metrics(rows, field="prediction"):
    n = len(rows)
    confusion = Counter((r["expected"], r.get(field, "unavailable")) for r in rows)
    same = [r for r in rows if r["expected"] == "same_claim"]
    changed = [r for r in rows if r["expected"] == "claim_changed"]
    unsure = [r for r in rows if r["expected"] == "unclear"]
    decided = [r for r in rows if r.get(field) in {"same_claim", "claim_changed"}]
    clear_changes = [r for r in rows if r.get(field) == "claim_changed"]

    def count(group, pred):
        return sum(r.get(field) == pred for r in group)

    exact = sum(r.get(field) == r["expected"] for r in rows)
    return {
        "n": n,
        "exact_correct": exact,
        "exact_accuracy": exact / n if n else None,
        "decisive_count": len(decided),
        "decisive_correct": sum(r.get(field) == r["expected"] for r in decided),
        "abstained_or_unavailable": n - len(decided),
        "known_changed": len(changed),
        "changed_correctly_flagged": count(changed, "claim_changed"),
        "change_recall": count(changed, "claim_changed") / len(changed)
        if changed
        else None,
        "change_precision": count(changed, "claim_changed") / len(clear_changes)
        if clear_changes
        else None,
        "dangerous_false_safe": count(changed, "same_claim"),
        "known_same": len(same),
        "same_cleared": count(same, "same_claim"),
        "false_change_on_same": count(same, "claim_changed"),
        "unchanged_needing_manual_review": len(same) - count(same, "same_claim"),
        "expected_unclear": len(unsure),
        "unclear_correct": count(unsure, "unclear"),
        "unsupported_decisive_on_unclear": count(unsure, "same_claim")
        + count(unsure, "claim_changed"),
        "safety_policy_manual_review_count": sum(
            r.get(field) != "same_claim" for r in rows
        ),
        "confusion": [
            {"expected": a, "predicted": b, "count": v}
            for (a, b), v in sorted(confusion.items())
        ],
    }


def latency(rows, key="seconds"):
    times = sorted(r[key] for r in rows if key in r)
    return {
        "n": len(times),
        "median_seconds": median(times) if times else None,
        "min_seconds": min(times) if times else None,
        "max_seconds": max(times) if times else None,
        "sum_seconds": sum(times),
    }
