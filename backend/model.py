"""Bounded local inference shared by all workflows; no paid fallback."""

import asyncio
import json
import os
import re
from urllib.parse import urlparse

import httpx

URL = os.getenv("SCHOLARTRACE_MODEL_URL", "http://127.0.0.1:8081/v1").rstrip("/")
NAME = os.getenv("SCHOLARTRACE_MODEL_NAME", "local")
if urlparse(URL).hostname not in {"localhost", "127.0.0.1", "::1"}:
    raise RuntimeError("Only a local inference endpoint is supported")
gate = asyncio.Semaphore(1)


async def complete(
    system, prompt, max_tokens=1100, structured=True, schema=None, reasoning=False
):
    async with gate:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(150, connect=5), trust_env=False
        ) as client:
            payload = {
                "model": NAME,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "max_tokens": max_tokens,
                # Reserve output space instead of letting reasoning consume the
                # entire completion. Fresh prompts avoid KV-cache-dependent logits.
                **(
                    {
                        "reasoning_budget_tokens": min(512, max_tokens // 2),
                        "cache_prompt": False,
                        "seed": 0,
                    }
                    if reasoning
                    else {}
                ),
                **(
                    {
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "result",
                                "strict": True,
                                "schema": schema,
                            },
                        }
                    }
                    if schema
                    else {"response_format": {"type": "json_object"}}
                    if structured
                    else {}
                ),
                "chat_template_kwargs": {"enable_thinking": reasoning},
            }
            for attempt in range(4):
                try:
                    response = await client.post(
                        URL + "/chat/completions", json=payload
                    )
                    response.raise_for_status()
                    break
                except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                    if isinstance(
                        exc, httpx.HTTPStatusError
                    ) and exc.response.status_code not in {502, 503, 504}:
                        raise
                    if attempt == 3:
                        raise
                    await asyncio.sleep(2 ** (attempt + 1))
            choice = response.json()["choices"][0]
            if choice.get("finish_reason") not in (None, "stop"):
                raise ValueError("模型输出未正常结束，请缩小问题范围后重试")
            text = choice["message"].get("content")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("模型未返回可用内容，请稍后重试")
    if structured:
        value = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip()))
        if not isinstance(value, dict):
            raise ValueError("模型未返回对象")
        return value
    return text


async def stream(system, prompt, max_tokens=1600):
    async with gate:
        async with httpx.AsyncClient(timeout=180, trust_env=False) as client:
            async with client.stream(
                "POST",
                URL + "/chat/completions",
                json={
                    "model": NAME,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0,
                    "stream": True,
                    "max_tokens": max_tokens,
                    "chat_template_kwargs": {"enable_thinking": False},
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    token = (
                        json.loads(data)["choices"][0]
                        .get("delta", {})
                        .get("content", "")
                    )
                    if token:
                        yield token
