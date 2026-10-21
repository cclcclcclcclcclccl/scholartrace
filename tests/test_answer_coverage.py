from backend.answer_coverage import (
    answer_limitations,
    duplicate_candidate,
)


def test_title_only_citation_cannot_prove_a_paper_did_not_explain_something():
    from backend.research import valid_claims

    b = {
        **block("title", "On Layer Normalization in the Transformer"),
        "title": "Paper",
        "page": 1,
    }
    for phrase in ["未明确说明", "没有具体讨论", "未详细解释"]:
        assert (
            valid_claims(
                {
                    "claims": [
                        {
                            "evidence_id": "E1",
                            "quote": b["text"],
                            "text": f"前一篇{phrase}如何计算归一化统计量。",
                        }
                    ]
                },
                [b],
            )
            == []
        )


def block(identifier, text):
    return {"id": identifier, "text": text, "document_id": "paper"}


def test_clause_reordering_does_not_add_another_verification_call():
    first = {
        "evidence_id": "E1",
        "text": "NET在推理时通过递推模式计算输出，而训练时采用并行模式进行参数更新，二者通过处理方式和应用场景区分",
    }
    second = {
        "evidence_id": "E1",
        "text": "NET在训练时采用并行模式进行参数更新，而在推理时通过递推模式计算输出，二者通过处理方式和应用场景区分",
    }
    assert duplicate_candidate(second, [first])
    assert not duplicate_candidate({**second, "evidence_id": "E2"}, [first])
    assert not duplicate_candidate(
        {**second, "text": second["text"].replace("采用", "不采用")}, [first]
    )
    assert not duplicate_candidate(
        {**second, "text": second["text"].replace("训练时", "部署时")}, [first]
    )


def test_different_quantities_roles_and_enumeration_are_preserved():
    original = {
        "evidence_id": "E1",
        "text": "NET训练时使用16位存储以节省显存，推理时使用8位存储以减少开销",
    }
    changed = {
        **original,
        "text": "NET训练时使用8位存储以节省显存，推理时使用16位存储以减少开销",
    }
    assert not duplicate_candidate(changed, [original])
    old = {"evidence_id": "E1", "text": "NET训练和推理的位宽分别是16，8"}
    assert not duplicate_candidate(
        {**old, "text": "NET训练和推理的位宽分别是8，16"}, [old]
    )


def test_partial_single_question_is_not_silently_presented_as_complete():
    message = answer_limitations("", [], 3, 1)
    assert "2 条候选" in message and "不代表问题已完整覆盖" in message
    assert answer_limitations("", [], 2, 2) == ""
    assert "未经全文核验" in answer_limitations("未报告", [], 1, 1)
    assert "未覆盖" in answer_limitations("", [{"status": "unresolved"}], 2, 1)


def test_single_question_rejection_notice_survives_grounding_and_export(monkeypatch):
    import asyncio

    from backend import query_facets, research, source_scope, store

    b = {
        **block("b", "The training batch contains four examples."),
        "title": "Paper",
        "page": 1,
    }
    monkeypatch.setattr(
        store, "get_document", lambda identifier: {"title": "Paper", "metadata": {}}
    )
    monkeypatch.setattr(research.retrieval, "search", lambda *args: [b])
    monkeypatch.setattr(query_facets, "concept_evidence", lambda *args: [])
    monkeypatch.setattr(source_scope, "explicit_scope_evidence", lambda *args: [])
    monkeypatch.setattr(research, "expand_neighbors", lambda blocks, limit: blocks)
    monkeypatch.setattr(research, "attach_table_headers", lambda blocks: blocks)

    async def generate(*args, **kwargs):
        return {
            "claims": [
                {
                    "evidence_id": "E1",
                    "quote": b["text"],
                    "text": "训练批次包含4个样本。",
                },
                {
                    "evidence_id": "E1",
                    "quote": b["text"],
                    "text": "训练批次包含99个样本。",
                },
            ],
            "limitations": "",
        }

    async def review(*args, **kwargs):
        return {
            "decisions": {
                "0": {"verdict": "supported_relevant", "support_span": b["text"]}
            }
        }

    monkeypatch.setattr(research, "single_answer", generate)
    monkeypatch.setattr(research, "support_review", review)
    result = asyncio.run(
        research.grounded("How many examples are in the training batch?", ["paper"])
    )
    assert len(result["claims"]) == 1
    assert result["candidate_claim_count"] == 2
    assert "1 条候选" in result["limitations"]
    exported = research.export_markdown(
        {
            "title": "Test",
            "kind": "answer",
            "content": {"sections": [{"title": "Answer", **result}]},
        }
    )
    assert "1 条候选" in exported and "99个样本" not in exported
