import copy
import json
import sys

import pytest

from scripts.quality_release_gate import compare_runs


def test_cli_writes_rejection_for_invalid_model_trace(monkeypatch, tmp_path):
    from scripts import quality_release_gate as gate

    output = tmp_path / "decision.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "gate",
            "--before",
            "old",
            "--after",
            "new",
            "--protocol",
            "protocol.json",
            "--output",
            str(output),
        ],
    )

    def invalid_trace(folder):
        raise ValueError("Failed inference is not an abstention: example")

    monkeypatch.setattr(gate, "read_traced_run", invalid_trace)
    with pytest.raises(SystemExit) as stopped:
        gate.main()
    assert stopped.value.code == 2
    decision = json.loads(output.read_text("utf-8"))
    assert decision["eligible"] is False
    assert "Failed inference" in decision["validation_error"]


def sample():
    protocol = {
        "qa": [
            {"id": "a", "question": "规模？", "unanswerable": False},
            {"id": "b", "question": "私人结果？", "unanswerable": True},
        ]
    }
    run = {
        "complete": True,
        "original_data_unchanged": True,
        "qa": [
            {
                "id": "a",
                "question": "规模？",
                "screen": {"source_valid": True},
                "response": {"model_answer": [{"text": "有据回答"}]},
            },
            {"id": "b", "question": "私人结果？", "response": {"model_answer": []}},
        ],
    }
    audit = {
        "cases": [
            {
                "id": "a",
                "verdict": "complete_supported",
                "claim_supported_by_full_quote": [True],
                "rationale": "有据",
            },
            {
                "id": "b",
                "verdict": "correct_abstention",
                "claim_supported_by_full_quote": [],
                "rationale": "无记录",
            },
        ]
    }
    return run, audit, protocol


def test_gate_rejects_new_fabrication_even_with_other_answer_retained():
    before, audit, protocol = sample()
    after, labels = copy.deepcopy(before), copy.deepcopy(audit)
    after["qa"][1]["response"]["model_answer"] = [{"text": "编造数值"}]
    after["qa"][1]["screen"] = {"source_valid": True}
    labels["cases"][1].update(
        verdict="unsupported_and_incomplete", claim_supported_by_full_quote=[False]
    )
    result = compare_runs(before, after, audit, labels, protocol)
    assert not result["eligible"] and any(x["id"] == "b" for x in result["regressions"])


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "question",
        "error",
        "source",
        "unknown_label",
        "trace_error",
        "api_fallback",
    ],
)
def test_gate_never_treats_incomplete_or_inconsistent_records_as_success(change):
    before, audit, protocol = sample()
    after, labels = copy.deepcopy(before), copy.deepcopy(audit)
    if change == "missing":
        labels["cases"].pop()
    if change == "question":
        after["qa"][0]["question"] = "换了题"
    if change == "error":
        after["qa"][1]["error"] = "model timeout"
    if change == "trace_error":
        after["qa"][1]["model_call_errors"] = ["TimeoutException"]
    if change == "api_fallback":
        after["qa"][1]["response"]["generation_failed"] = True
    if change == "source":
        after["qa"][0]["screen"]["source_valid"] = False
    if change == "unknown_label":
        labels["cases"][0]["verdict"] = "looks_good"
    with pytest.raises(ValueError):
        compare_runs(before, after, audit, labels, protocol)


def test_gate_accepts_real_improvement_without_erasing_failure_history():
    after, audit, protocol = sample()
    before, labels = copy.deepcopy(after), copy.deepcopy(audit)
    before["qa"][0]["response"]["model_answer"] = []
    labels["cases"][0].update(
        verdict="answerable_abstention", claim_supported_by_full_quote=[]
    )
    result = compare_runs(before, after, labels, audit, protocol)
    assert result["eligible"] and result["improvements"] == ["a"]
    assert labels["cases"][0]["verdict"] == "answerable_abstention"


def test_gate_requires_model_trace_and_preserves_swallowed_failures(tmp_path):
    import json

    from scripts.quality_release_gate import read_traced_run

    run, audit, protocol = sample()
    (tmp_path / "run.json").write_text(json.dumps(run), encoding="utf-8")
    (tmp_path / "model-calls.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="Missing model trace"):
        read_traced_run(tmp_path)
    trace = [
        {"case_id": "a", "output": {}},
        {"case_id": "b", "error": "TimeoutException"},
    ]
    (tmp_path / "model-calls.json").write_text(json.dumps(trace), encoding="utf-8")
    traced = read_traced_run(tmp_path)
    with pytest.raises(ValueError, match="Failed inference"):
        compare_runs(run, traced, audit, audit, protocol)


def test_gate_rejects_losing_a_previously_partial_answer():
    before, audit, protocol = sample()
    audit["cases"][0]["verdict"] = "partial_supported"
    after, labels = copy.deepcopy(before), copy.deepcopy(audit)
    after["qa"][0]["response"]["model_answer"] = []
    labels["cases"][0].update(
        verdict="answerable_abstention", claim_supported_by_full_quote=[]
    )
    result = compare_runs(before, after, audit, labels, protocol)
    assert not result["eligible"]
    assert any("fields were lost" in x["reason"] for x in result["regressions"])
