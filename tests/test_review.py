import asyncio
import httpx
from backend.review import review_change


def run_response(value):
    item = {
        "status": "review_required",
        "note": {
            "note": "Code availability",
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
