import asyncio
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import (
    accounts,
    database,
    evidence_context,
    model,
    proposal_revision,
    research,
    store,
)
from backend.app import app
from backend.claim_checks import negative_result_mismatch
from backend.execution_check import AttentionExecution, attention, preflight


def execution(**updates):
    return dict(
        kind="attention_from_scratch",
        d_model=32,
        heads=[1, 2, 4, 8],
        training_steps=100,
        optimizer="AdamW",
        learning_rate=0.001,
        batch_size=8,
        sequence_length=128,
        warmup_runs=10,
        timing_runs=30,
        device="undecided",
        failure_policy="retain_all_runs",
        **updates,
    )


def test_attention_template_does_not_replace_explicit_other_tasks():
    assert proposal_revision.attention_template_applies("注意力头数对效率的影响")
    assert not proposal_revision.attention_template_applies(
        "注意力头数对图像分类的影响"
    )
    assert not proposal_revision.attention_template_applies("检索结果质量研究")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "library.sqlite3")
    monkeypatch.setattr(accounts, "AUTH_PATH", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(
        accounts, "path", lambda identifier: tmp_path / identifier / "library.sqlite3"
    )
    database.initialize()
    with TestClient(app) as value:
        yield value


def test_attention_matches_hand_computed_uniform_weights():
    q = np.zeros((1, 2, 3, 4))
    v = np.arange(24).reshape(1, 2, 3, 4)
    output, weights = attention(q, q, v)
    assert np.allclose(weights, 1 / 3)
    assert np.allclose(output, np.broadcast_to(v.mean(axis=-2, keepdims=True), v.shape))
    result = preflight(execution(), 11)
    assert [r["d_head"] for r in result["results"]] == [32, 16, 8, 4]
    assert all(
        r["output_shape"] == [1, 16, 32] and r["finite"] for r in result["results"]
    )
    assert result == preflight(execution(), 11)


@pytest.mark.parametrize(
    "changes",
    [
        {"heads": [1, 3]},
        {"heads": [2, 2]},
        {"heads": [1, True]},
        {"training_steps": 0},
        {"learning_rate": float("nan")},
        {"warmup_runs": 0},
        {"timing_runs": 1},
    ],
)
def test_execution_rejects_invalid_constraints(changes):
    with pytest.raises(ValidationError):
        AttentionExecution.model_validate({**execution(), **changes})


def test_preflight_revision_snapshot_and_account_isolation(client):
    p = {"execution": execution(), "seeds": [11, 23, 47]}
    card = research.save_artifact(
        "protocol", "预检设计", {"protocol": p, "revision": 2}
    )
    url = f"/api/experiments/protocols/{card['id']}/preflight"
    assert client.post(url, json={"revision": 1}).status_code == 409
    response = client.post(url, json={"revision": 2})
    assert response.status_code == 200
    result = response.json()
    assert result["protocol_snapshot"]["revision"] == 2
    assert result["actual_sequence_length"] == 16
    with store.connection() as conn:
        conn.execute(
            "UPDATE artifacts SET content=? WHERE id=?",
            (json.dumps({"protocol": p, "revision": 3}), card["id"]),
        )
    assert (
        research.artifact(result["id"])["content"]["protocol_snapshot"]["revision"] == 2
    )
    assert (
        "非训练" in client.get(f"/api/artifacts/{result['id']}/export?format=md").text
    )
    client.post(
        "/api/account/register",
        json={"name": "other-reviewer", "password": "local-password-876"},
    )
    assert client.post(url, json={"revision": 3}).status_code == 404
    assert client.get(f"/api/artifacts/{result['id']}").status_code == 404


def test_negative_result_subject_and_no_proof_guard():
    quote = "We use learnable 1D position embeddings, since we have not observed significant performance gains from using more advanced 2D-aware position embeddings."
    assert negative_result_mismatch("使用一维位置嵌入未观察到显著性能提升。", quote)
    assert not negative_result_mismatch(
        "采用可学习一维位置嵌入；使用更复杂二维嵌入未观察到显著性能提升。", quote
    )
    assert not negative_result_mismatch("一维和二维嵌入都需要学习。", quote)
    assert negative_result_mismatch(
        "未在实验中证明二维嵌入更好。", "2-dimensional embeddings concatenate two axes."
    )
    assert not negative_result_mismatch("本文没有证明二维嵌入更好。", quote)
    assert negative_result_mismatch(
        "由于输入更短，所以不同方法差异不重要。",
        "We speculate that shorter inputs explain the smaller differences.",
    )
    assert not negative_result_mismatch(
        "作者推测，可能由于输入更短，不同方法差异较小。",
        "We speculate that shorter inputs explain the smaller differences.",
    )


def test_significance_warning_distinguishes_explicit_no_claim():
    from backend.proposal_checks import assess_plan

    assert not any(
        "显著性" in x for x in assess_plan({"evaluation_plan": "不预设显著性或胜者。"})
    )
    assert any(
        "显著性" in x
        for x in assess_plan({"evaluation_plan": "我们的方案显著提升性能。"})
    )


def test_multiple_table_rows_retain_header_and_distinct_models(monkeypatch):
    header = {
        "id": "head",
        "document_id": "p",
        "page": 1,
        "bbox": [10, 10, 300, 20],
        "text": "Model\nLayers\nHidden size\nHeads",
    }
    body = {
        "id": "body",
        "document_id": "p",
        "page": 1,
        "bbox": [10, 25, 300, 65],
        "text": "Small\n6\n128\n4\nLarge\n12\n256\n8",
    }
    monkeypatch.setattr(store, "get_blocks", lambda *a: [header, body])
    result = evidence_context.attach_table_headers([body])[0]
    assert result["source_context"][0]["id"] == "head"
    assert {x["field"]: x["value"] for x in result["table_fields"]}[
        "Large · Hidden size"
    ] == "256"
    assert result["text"] == body["text"] and result["id"] == "body"
    malformed = {**body, "text": body["text"] + "\n99"}
    assert not evidence_context.attach_table_headers([malformed])[0].get("table_fields")


def test_structured_revision_uses_validated_parameters_and_keeps_raw_response(
    client, monkeypatch
):
    source = research.save_artifact(
        "writing",
        "注意力头数研究",
        {
            "proposal": {
                "abstract": "尚未研究",
                "introduction": "原文出处保留",
                "method_plan": "错误旧方案",
                "evaluation_plan": "原计划",
            }
        },
    )

    async def complete(*args, **kwargs):
        return {
            "method_plan": "这段自然语言故意与结构化设置矛盾：固定头维度。",
            "evaluation": {
                k: "这是一段尚未验证的研究说明。" for k in proposal_revision.LABELS
            },
            "execution": execution(),
            "seeds": [11, 23, 47],
        }

    monkeypatch.setattr(model, "complete", complete)

    class Context:
        def progress(self, *a):
            pass

        def check(self):
            pass

    result = asyncio.run(
        proposal_revision.refine_plan(Context(), {"artifact_id": source["id"]})
    )
    assert result["execution_draft"]["execution"]["d_model"] == 32
    assert "固定头维度" not in result["proposal"]["method_plan"]
    assert "固定头维度" in result["revision_audit"]["raw_model_response"]["method_plan"]
    assert "模板" in result["proposal"]["method_plan"]
    assert result["proposal"]["introduction"] == "原文出处保留"
    assert not any("随机种子" in c or "训练步数" in c for c in result["plan_checks"])

    async def invalid_seeds(*args, **kwargs):
        value = await complete(*args, **kwargs)
        value["seeds"] = []
        return value

    monkeypatch.setattr(model, "complete", invalid_seeds)
    with pytest.raises(ValueError, match="种子"):
        asyncio.run(
            proposal_revision.refine_plan(Context(), {"artifact_id": source["id"]})
        )
    assert (
        research.artifact(source["id"])["content"]["proposal"]["method_plan"]
        == "错误旧方案"
    )
