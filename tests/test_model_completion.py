import asyncio
import json

import httpx
import pytest

from backend import model


@pytest.mark.parametrize(
    "finish,content,valid",
    [
        ("stop", '{"claims":[]}', True),
        ("length", '{"claims":[]}', False),
        ("content_filter", '{"claims":[]}', False),
        ("stop", None, False),
        ("stop", "", False),
    ],
)
def test_rejects_incomplete_or_missing_model_output(
    monkeypatch, finish, content, valid
):
    received = []

    def response(request):
        received.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": finish, "message": {"content": content}}]
            },
        )

    client = httpx.AsyncClient
    monkeypatch.setattr(
        model.httpx,
        "AsyncClient",
        lambda **kwargs: client(transport=httpx.MockTransport(response), **kwargs),
    )
    monkeypatch.setattr(model, "gate", asyncio.Semaphore(1))
    if valid:
        result = asyncio.run(model.complete("system", "question", reasoning=True))
        assert result == {"claims": []}
    else:
        with pytest.raises(ValueError):
            asyncio.run(model.complete("system", "question", reasoning=True))
    assert received[0]["chat_template_kwargs"]["enable_thinking"] is True
