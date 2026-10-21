"""Regression checks for information lost between source selection, subquestions and numeric review."""

from decimal import Decimal

from backend import research, subquestions
from backend.numeric_evidence import unsupported_numbers


def test_pdf_page_locator_is_checked_against_metadata_not_measured_quantities():
    source = "We train a 33B model on a 24GB consumer GPU in less than 12 hours."
    claim = "论文第10页：33B模型在24GB显存GPU上不到12小时训练。"
    assert not unsupported_numbers(claim, source, source_page=10)
    assert unsupported_numbers(claim, source, source_page=11)
    assert unsupported_numbers(claim, source) == {Decimal(10)}
    assert unsupported_numbers("第10页报告耗时10小时", source, source_page=10) == {
        Decimal(10)
    }
    assert unsupported_numbers(
        "第10页报告33B和24GB；第11页同样如此", source, source_page=10
    )
    assert not unsupported_numbers("On page 10: 33B and 24GB", source, source_page=10)


def test_page_number_cannot_be_laundered_using_matching_measurement():
    assert unsupported_numbers("第9页：9小时", "We train for 9 hours.", source_page=10)


def test_page_locator_does_not_drop_an_otherwise_supported_claim():
    b = {
        "id": "b",
        "document_id": "doc",
        "page": 10,
        "title": "Method",
        "text": "We train a 33B model on a 24GB consumer GPU in less than 12 hours.",
    }
    result = research.valid_claims(
        {
            "claims": [
                {
                    "text": "第10页：33B模型在24GB显存GPU上不到12小时训练。",
                    "quote": b["text"],
                    "evidence_id": "E1",
                }
            ]
        },
        [b],
    )
    assert len(result) == 1 and result[0]["page"] == 10


def test_anaphoric_subquestion_retains_preceding_user_context_without_changing_display():
    parts = subquestions.split_question("无语音片段怎样采样？这些片段用于什么任务？")
    original = parts[1]["question"]
    resolved = subquestions.contextual_question(parts, 1)
    assert "无语音片段怎样采样？" in resolved and original in resolved
    assert parts[1]["question"] == original
    assert subquestions.contextual_question(parts, 0) == parts[0]["question"]
    unrelated = subquestions.split_question("A有多少层？B的训练数据量是多少？")
    assert subquestions.contextual_question(unrelated, 1) == unrelated[1]["question"]
