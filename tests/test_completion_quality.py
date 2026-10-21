import asyncio

import pytest

from backend import translation
from backend.claim_checks import counted_subject_mismatch, repair_citation_candidates
from backend.diagrams import compile_plan
from backend.subquestions import split_question


def test_generic_quantity_followup_keeps_referent():
    parts = split_question("Atlas包含多少种自然语言和编程语言？请分别给出数量。")
    assert len(parts) == 1 and "请分别给出数量" in parts[0]["question"]
    assert len(split_question("Atlas多大？Boreal多大？")) == 2


def test_citation_repair_is_only_a_unique_candidate_not_an_answer():
    claim = {"text": "语料为900万对，基线数据有240万张图像。", "evidence_id": "E1"}
    blocks = [
        {"text": "We collect 9 million pairs."},
        {
            "text": "We collect 9 million pairs and the baseline uses 2.4 million images."
        },
    ]
    result = repair_citation_candidates([claim], blocks)[0]
    assert result["evidence_id"] == "E2" and result["text"] == claim["text"]
    assert result["proposed_previous_evidence_id"] == "E1"
    assert "support_review" not in result
    assert (
        repair_citation_candidates([claim], blocks + [blocks[1]])[0]["evidence_id"]
        == "E1"
    )
    assert repair_citation_candidates([claim], blocks[:1])[0]["evidence_id"] == "E1"


def test_counts_must_refer_to_the_right_subject():
    assert counted_subject_mismatch(
        "每token路由到一个专家", "Routing communication is reduced."
    )
    assert not counted_subject_mismatch(
        "每token路由到一个专家", "Each token routes to a single expert."
    )
    assert counted_subject_mismatch(
        "数据来源有数百个", "We collaborated with hundreds of researchers."
    )
    assert not counted_subject_mismatch(
        "数据来源有数百个", "The data comprises hundreds of sources."
    )


def test_translation_reserves_user_markers_and_restores_in_one_pass(monkeypatch):
    monkeypatch.setattr(translation.database, "preference", lambda *a: [])

    async def complete(system, prompt, **kwargs):
        return {"translation": prompt}

    monkeypatch.setattr(translation.model, "complete", complete)
    source = "Keep literal ZXQKEEP1QXZ and ZXQKEEP0QXZ with 42 samples and $x=2$."
    assert asyncio.run(translation.translate_text(source, "en")) == source


def test_unknown_translation_marker_is_rejected(monkeypatch):
    monkeypatch.setattr(translation.database, "preference", lambda *a: [])

    async def complete(system, prompt, **kwargs):
        return {"translation": "译文 " + prompt + " ZXQKEEP999QXZ"}

    monkeypatch.setattr(translation.model, "complete", complete)
    with pytest.raises(ValueError, match="无来源"):
        asyncio.run(translation.translate_text("We train on 42 samples.", "zh"))


def branch_plan():
    return {
        "direction": "TB",
        "nodes": [
            {"id": "a", "label": "校验", "kind": "decision"},
            {"id": "b", "label": "保存", "kind": "output"},
            {"id": "c", "label": "重试"},
        ],
        "edges": [
            {"source": "a", "target": "b", "label": "通过"},
            {"source": "a", "target": "c", "label": "失败"},
            {"source": "c", "target": "a", "label": "再次校验"},
        ],
    }


def test_diagram_preserves_condition_direction_and_feedback():
    code = compile_plan(branch_plan())
    assert code.startswith("flowchart TB") and 'N0{"校验"}' in code
    assert 'N0 -->|"通过"| N1' in code and 'N2 -->|"再次校验"| N0' in code


@pytest.mark.parametrize(
    "change",
    [
        "missing_branch",
        "duplicate_label",
        "duplicate_edge",
        "missing_target",
        "markup_only",
    ],
)
def test_invalid_diagram_is_not_saved_as_valid(change):
    p = branch_plan()
    if change == "missing_branch":
        p["edges"] = p["edges"][:1]
    if change == "duplicate_label":
        p["edges"][1]["label"] = "通过"
    if change == "duplicate_edge":
        p["edges"].append(p["edges"][0].copy())
    if change == "missing_target":
        p["edges"][0]["target"] = "unknown"
    if change == "markup_only":
        p["nodes"][1]["label"] = "<>[]{}"
    with pytest.raises(ValueError):
        compile_plan(p)


def test_query_set_membership_does_not_become_every_query():
    from backend.claim_checks import query_membership_overreach

    source = "We retain texts including one of a set of 800 queries."
    assert query_membership_overreach("文本包含800个查询", source)
    assert not query_membership_overreach("文本包含800个查询中的任意一个", source)


def test_prose_with_formula_is_translated_not_mistaken_for_formula(monkeypatch):
    monkeypatch.setattr(translation.database, "preference", lambda *a: [])
    calls = []

    async def complete(system, prompt, **kwargs):
        calls.append(prompt)
        return {
            "translation": "请保留 "
            + " ".join(__import__("re").findall(r"ZXQKEEP\d+QXZ", prompt))
            + "，实现链接。"
        }

    monkeypatch.setattr(translation.model, "complete", complete)
    result = asyncio.run(
        translation.translate_text(
            "Keep `x = 2` and $y=x^2$ unchanged; the implementation is at https://example.org/method [12].",
            "zh",
        )
    )
    assert calls and "请保留" in result and "`x = 2`" in result and "$y=x^2$" in result


@pytest.mark.parametrize(
    "source",
    [
        "Keep `ZXQKEEP1QXZ = 2` and $ZXQKEEP0QXZ=4$ exactly unchanged.",
        "Keep literal ZXQKEEP1QXZ in https://example.org/ZXQKEEP2QXZ unchanged.",
    ],
)
def test_nested_user_markers_restore_without_internal_tokens(source):
    import re

    protected, originals = translation.protect(
        source, [{"source": "KEEP", "target": "保留"}]
    )
    restored = re.sub(r"ZXQKEEP(\d+)QXZ", lambda m: originals[int(m[1])], protected)
    assert restored == source.replace("Keep", "保留")
