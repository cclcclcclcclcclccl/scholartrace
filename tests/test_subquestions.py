import asyncio

import pytest
from fastapi.testclient import TestClient

from backend import accounts, database, research, store, subquestions
from backend.app import app


def block(identifier="b", text="We use a fixed encoder. We use a separate decoder."):
    return {
        "id": identifier,
        "document_id": "doc",
        "page": 1,
        "title": "Paper",
        "text": text,
    }


def test_plan_is_bounded_and_deduplicated():
    assert subquestions.split_question("") == []
    parts = subquestions.split_question(
        "第一项是什么？第二项如何？请保留限制条件。不要互换。"
    )
    assert len(parts) == 2
    assert parts[0]["id"] == "Q1"
    assert "不要互换" in parts[1]["question"]
    assert len(subquestions.split_question("什么？" * 8)) == 4
    assert (
        len(
            subquestions.split_question(
                "训练和微调各用哪个优化器？请区分两个阶段，不要混用。"
            )
        )
        == 1
    )


def test_coverage_counts_only_remaining_claims():
    parts = [{"id": "Q1", "question": "问题一"}, {"id": "Q2", "question": "问题二"}]
    result = subquestions.coverage(parts, [{"part_id": "Q2", "text": "答案"}])
    assert result[0]["status"] == "unresolved"
    assert result[0]["claim_count"] == 0
    assert result[1]["status"] == "reviewed_answer"
    assert result[1]["claim_count"] == 1


def test_coverage_retains_candidate_sources_and_explains_review_rejection():
    parts = [
        {
            "id": "Q1",
            "question": "为什么？",
            "candidate_claim_count": 1,
            "evidence_ids": ["b"],
            "selected_evidence_ids": ["b"],
        }
    ]
    item = subquestions.coverage(parts, [])[0]
    assert item["status"] == "unresolved"
    assert item["selected_evidence_ids"] == ["b"]
    assert "未通过引用或支持性初筛" in item["reason"]


def test_failed_review_does_not_abort_other_candidates(monkeypatch):
    async def complete(system, prompt, **kwargs):
        if prompt == "incomplete":
            raise ValueError("generation exceeded budget")
        return {"decisions": {"1": {"verdict": "supported_relevant"}}}

    monkeypatch.setattr(research.model, "complete", complete)

    async def run():
        first = await research.support_review("review", "incomplete")
        second = await research.support_review("review", "complete")
        return first, second

    first, second = asyncio.run(run())
    assert first == {"decisions": {}}
    assert second["decisions"]["1"]["verdict"] == "supported_relevant"


@pytest.mark.parametrize("first_failure", ["invented_id", "request_failure"])
def test_part_failure_preserves_later_answer_and_scope(monkeypatch, first_failure):
    b = block()
    queries = []

    def search(query, ids, limit):
        queries.append((query, ids))
        return [b]

    monkeypatch.setattr(subquestions.retrieval, "search", search)
    monkeypatch.setattr(subquestions, "concept_evidence", lambda *args: [])
    monkeypatch.setattr(subquestions, "expand_neighbors", lambda blocks, limit: blocks)
    monkeypatch.setattr(subquestions, "attach_table_headers", lambda blocks: blocks)
    generation_prompts = []

    async def complete(system, prompt, **kwargs):
        if "selected" in kwargs.get("schema", {}).get("properties", {}):
            if "第一项" in prompt:
                if first_failure == "request_failure":
                    raise ValueError("invalid model response")
                return {"selected": ["S99"]}
            return {"selected": ["S0"]}
        generation_prompts.append(prompt)
        if system.startswith("Compare EVERY"):
            return {"claims": [], "unanswered_parts": []}
        return {"claims": [{"evidence_id": "E1", "text": "使用独立的解码器。"}]}

    monkeypatch.setattr(subquestions.model, "complete", complete)
    parts = subquestions.split_question("第一项如何？第二项如何？")
    parts[0]["query"] = "first"
    parts[1]["query"] = "second"
    result, evidence, records = asyncio.run(
        subquestions.answer_parts(parts, ["doc"], [b], "Paper")
    )
    assert len(result["claims"]) == 1 and result["claims"][0]["part_id"] == "Q2"
    assert result["claims"][0]["quote"] == b["text"]
    assert len(evidence) == 1 and records[0]["reason"]
    assert len(generation_prompts) == 2
    assert b["text"] in generation_prompts[0]
    assert queries == [("first", ["doc"]), ("second", ["doc"])]


@pytest.mark.parametrize("scoped", [False, True])
def test_grounded_coverage_uses_reviewed_results(monkeypatch, scoped):
    b = block()
    monkeypatch.setattr(
        store, "get_document", lambda identifier: {"title": "Paper", "metadata": {}}
    )
    monkeypatch.setattr(research.retrieval, "search", lambda *args: [b])
    monkeypatch.setattr(research, "expand_neighbors", lambda blocks, limit: blocks)

    async def parts_answer(parts, ids, blocks, title, ctx):
        return (
            {
                "claims": [
                    {
                        "text": "使用固定编码器。",
                        "evidence_id": "E1",
                        "quote": b["text"],
                        "part_id": "Q1",
                    },
                    {
                        "text": "使用另一个编码器。",
                        "evidence_id": "E1",
                        "quote": b["text"],
                        "part_id": "Q2",
                    },
                ],
                "limitations": "",
            },
            blocks,
            parts,
        )

    monkeypatch.setattr(research, "answer_parts", parts_answer)

    async def complete(system, prompt, **kwargs):
        if "decisions" in kwargs.get("schema", {}).get("properties", {}):
            return {
                "decisions": {
                    "0": {
                        "verdict": "supported_relevant",
                        "support_span": "We use a fixed encoder.",
                    },
                    "1": {"verdict": "unsupported", "support_span": ""},
                }
            }
        return {
            "query": "encoder decoder",
            "facets": [],
            "question": "编码器和解码器各是什么？",
            "parts": [
                {"question": "编码器是什么？", "query": "encoder"},
                {"question": "解码器是什么？", "query": "decoder"},
            ],
        }

    monkeypatch.setattr(research.model, "complete", complete)
    result = asyncio.run(
        research.grounded("编码器是什么？解码器是什么？", ["doc"], scoped=scoped)
    )
    assert len(result["claims"]) == 1
    assert [p["status"] for p in result["subquestions"]] == [
        "reviewed_answer",
        "unresolved",
    ]
    assert result["limitations"]
    assert [p["question"] for p in result["subquestions"]] == [
        "编码器是什么？",
        "解码器是什么？",
    ]


def test_dedup_never_removes_another_subquestion_or_paper():
    from backend.claim_checks import prune_repeated_facts

    blocks = [
        block("one", "The hidden dimension is 768."),
        {**block("two", "The hidden dimension is 768."), "document_id": "other"},
    ]
    claims = [
        {
            "text": "隐藏维度为768。",
            "evidence_id": "E1",
            "quote": blocks[0]["text"],
            "part_id": "Q1",
        },
        {
            "text": "隐藏维度为768。",
            "evidence_id": "E1",
            "quote": blocks[0]["text"],
            "part_id": "Q2",
        },
        {
            "text": "隐藏维度为768。",
            "evidence_id": "E2",
            "quote": blocks[1]["text"],
            "part_id": "Q1",
        },
    ]
    accepted = research.valid_claims({"claims": claims + [claims[0]]}, blocks)
    assert len(accepted) == 3
    assert prune_repeated_facts(accepted) == accepted
    assert all(
        p["status"] == "reviewed_answer"
        for p in subquestions.coverage(
            subquestions.split_question("维度是多少？隐藏维度是什么？"), accepted[:2]
        )
    )


def test_empty_and_skipped_papers_keep_original_parts(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "isolated.sqlite3")
    database.initialize()
    monkeypatch.setattr(
        store,
        "get_document",
        lambda identifier: {
            "title": "Shared title",
            "name": identifier + ".pdf",
            "metadata": {},
        },
    )
    monkeypatch.setattr(research.retrieval, "search", lambda *args: [])
    monkeypatch.setattr(research, "expand_neighbors", lambda blocks, limit: blocks)
    monkeypatch.setattr("backend.query_facets.concept_evidence", lambda *args: [])

    async def complete(*args, **kwargs):
        return {
            "question": "Discarded rewrite",
            "query": "encoder",
            "facets": [],
            "part_queries": {},
        }

    monkeypatch.setattr(research.model, "complete", complete)
    result = asyncio.run(
        research.grounded("编码器是什么？解码器是什么？", [str(i) for i in range(9)])
    )
    assert len(result["comparison"]) == 9
    assert len(result["subquestions"]) == 18
    assert len({p["id"] for p in result["subquestions"]}) == 18
    assert "8.pdf" in result["subquestions"][-1]["question"]
    assert "未检索到" in result["comparison"][0]["subquestions"][0]["reason"]
    assert "未处理" in result["comparison"][-1]["subquestions"][0]["reason"]


def test_failed_paper_does_not_discard_other_paper(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "isolated.sqlite3")
    database.initialize()
    original = research.grounded
    monkeypatch.setattr(
        store,
        "get_document",
        lambda identifier: {"title": identifier, "name": identifier + ".pdf"},
    )
    b = {**block(), "document_id": "good"}

    async def scoped(question, ids, *args, **kwargs):
        if len(ids) > 1:
            return await original(question, ids, *args, **kwargs)
        if ids == ["bad"]:
            raise ValueError("invalid generation")
        return {
            "claims": [
                {
                    "text": "使用固定编码器。",
                    "block_id": b["id"],
                    "document_id": "good",
                    "quote": b["text"],
                }
            ],
            "evidence": [b],
        }

    monkeypatch.setattr(research, "grounded", scoped)
    result = asyncio.run(research.grounded("编码器是什么？", ["bad", "good"]))
    assert result["claims"][0]["document_id"] == "good"
    assert result["claims"][0]["evidence_id"] == "E1"
    assert "处理失败" in result["comparison"][0]["subquestions"][0]["reason"]


def test_unresolved_answer_saved_reopened_and_exported(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "library.sqlite3")
    monkeypatch.setattr(accounts, "AUTH_PATH", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(
        accounts, "path", lambda identifier: tmp_path / identifier / "library.sqlite3"
    )
    database.initialize()
    statuses = subquestions.coverage(
        [
            {"id": "Q1", "question": "缺失问题一？"},
            {"id": "Q2", "question": "缺失问题二？"},
        ],
        [],
    )

    async def grounded(*args):
        return {
            "claims": [],
            "evidence": [],
            "subquestions": statuses,
            "limitations": "本轮无回答",
        }

    monkeypatch.setattr(research, "grounded", grounded)
    with TestClient(app) as client:
        response = client.post(
            "/api/ask", json={"question": "缺失问题一和二？", "document_ids": []}
        )
        assert response.status_code == 200
        result = response.json()
        assert result["subquestions"] == statuses
        assert result["artifact_id"]
        saved = client.get("/api/artifacts/" + result["artifact_id"]).json()
        assert saved["content"]["sections"][0]["subquestions"] == statuses
        exported = client.get(
            "/api/artifacts/" + result["artifact_id"] + "/export?format=md"
        )
        assert exported.status_code == 200 and "逐项回答情况" in exported.text
        assert all(p["question"] in exported.text for p in statuses)
        assert "本轮未形成通过核验的回答" in exported.text


def test_table_number_has_caption_anchor_and_unrelated_caption_is_ignored(monkeypatch):
    from backend.evidence_context import attach_table_headers
    from backend.numeric_evidence import unsupported_numbers

    header = {
        **block("header", "Model\nLayers\nHidden\nParams"),
        "bbox": [0, 0, 100, 10],
    }
    row = {**block("row", "Base\n12\n768\n86M"), "bbox": [0, 12, 100, 25]}
    caption = {**block("caption", "Table 1: Model settings."), "bbox": [0, 32, 100, 42]}
    distant = {**block("other", "Table 7: Other settings."), "bbox": [0, 100, 100, 110]}
    monkeypatch.setattr(
        store, "get_blocks", lambda *args: [header, row, caption, distant]
    )
    enriched = attach_table_headers([row])[0]
    assert [b["id"] for b in enriched["source_context"]] == ["header", "caption"]
    assert enriched["source_context"][1]["context_role"] == "table_caption"
    context = [b["text"] for b in enriched["source_context"]]
    assert not unsupported_numbers("表1显示Base有12层", enriched["text"], context)
    assert unsupported_numbers("表7显示Base有12层", enriched["text"], context)


def test_subquestion_keeps_three_requested_fields(monkeypatch):
    b = block()
    monkeypatch.setattr(subquestions.retrieval, "search", lambda *args: [b])
    monkeypatch.setattr(subquestions, "concept_evidence", lambda *args: [])
    monkeypatch.setattr(subquestions, "expand_neighbors", lambda blocks, limit: blocks)
    monkeypatch.setattr(subquestions, "attach_table_headers", lambda blocks: blocks)

    async def select(*args, **kwargs):
        return {"selected": ["S0"]}

    async def answer(*args, **kwargs):
        return {"claims": [{"text": f"字段{i}", "evidence_id": "E1"} for i in range(3)]}

    monkeypatch.setattr(subquestions.model, "complete", select)
    monkeypatch.setattr(research, "single_answer", answer)
    result, _, _ = asyncio.run(
        subquestions.answer_parts(
            subquestions.split_question("列出三个字段？"), ["doc"], [b], "Paper"
        )
    )
    assert [c["text"] for c in result["claims"]] == ["字段0", "字段1", "字段2"]


@pytest.mark.parametrize(
    "quote,rejected",
    [
        (
            "We learn separate embeddings for the X and Y axes and concatenate them.",
            True,
        ),
        ("We did not directly compare the two alternatives in this experiment.", False),
    ],
)
def test_absence_of_comparison_needs_source(quote, rejected):
    from backend.claim_checks import semantic_overreach

    assert (
        semantic_overreach("论文并未直接比较这两种嵌入的性能差异。", quote) == rejected
    )


def test_partial_answer_retains_omitted_candidate_notice_and_source():
    parts = [
        {
            "id": "Q1",
            "question": "分别多少？",
            "candidate_claim_count": 3,
            "selected_evidence_ids": ["source-a", "source-b"],
        }
    ]
    item = subquestions.coverage(parts, [{"part_id": "Q1", "text": "一个已保留事实"}])[
        0
    ]
    assert item["status"] == "reviewed_answer"
    assert item["omitted_candidate_count"] == 2
    assert item["selected_evidence_ids"] == ["source-a", "source-b"]
    assert "被去重" in item["reason"] and "不代表本项完整" in item["reason"]
    # A second pass after multi-document subject filtering must recompute counts.
    reduced = subquestions.coverage([item], [])[0]
    assert reduced["omitted_candidate_count"] == 3 and reduced["status"] == "unresolved"
    assert (
        subquestions.coverage([{"id": "legacy"}], [{"part_id": "legacy"}])[0][
            "omitted_candidate_count"
        ]
        == 0
    )


def test_partly_answered_export_preserves_notice_and_candidate_location():
    source = block("source", "Evidence candidate")
    parts = subquestions.coverage(
        [
            {
                "id": "Q1",
                "question": "两个模型各是多少？",
                "candidate_claim_count": 2,
                "selected_evidence_ids": ["source"],
            }
        ],
        [{"part_id": "Q1"}],
    )
    item = {
        "title": "Partial",
        "kind": "answer",
        "content": {
            "sections": [
                {
                    "title": "Answer",
                    "claims": [],
                    "subquestions": parts,
                    "evidence": [source],
                }
            ]
        },
    }
    markdown = research.export_markdown(item)
    assert parts[0]["reason"] in markdown
    assert "1 条回答通过初筛" in markdown
    assert "候选原文（未经支持性确认）" in markdown
    assert "doc p.1" in markdown and "/ source" in markdown
