"""Check statistics against known values, source preservation and protocol revision isolation."""

import asyncio
import hashlib
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from backend import accounts, database, experiments, research, store
from backend.app import app
from backend.claim_checks import prune_repeated_facts


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "library.sqlite3")
    monkeypatch.setattr(accounts, "AUTH_PATH", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(
        accounts, "path", lambda identifier: tmp_path / identifier / "library.sqlite3"
    )
    database.initialize()
    with TestClient(app) as client:
        yield client


def protocol():
    return {
        "title": "检索基线试验",
        "hypothesis": "语义检索可能提高证据召回率。",
        "task": "retrieval",
        "dataset": "本地冻结题集，许可已核对",
        "split": "官方固定测试划分，开发集不参与评分",
        "baseline": "BM25",
        "variable": "检索方式：BM25 与混合检索",
        "controls": "固定文档版本、查询、top-k 与模型",
        "metric": "score",
        "direction": "higher",
        "criterion": "预先记录召回率差异，报告所有失败案例",
        "seeds": [11, 23, 47],
        "resources": "CPU 本地试跑",
        "failure": "索引失败标记无效运行，不丢弃低分运行",
        "document_ids": [],
    }


def measurements(**changes):
    return {
        "title": "重复测量检查",
        "csv": "method,seed,score\nA,11,1\nA,23,2\nA,47,3\nB,11,4\nB,23,4\nB,47,4\n",
        "group": "method",
        "run": "seed",
        "metric": "score",
        "unit": "units",
        "interval": "ci95",
        "data_label": "example",
        **changes,
    }


def test_known_sample_statistics_and_interval_not_population_sd():
    spec = measurements()
    result = experiments.summarize(spec)
    a, b = result["summary"]
    assert a["mean"] == 2 and a["sd"] == 1
    # n=3: t(.975,2)=4.3026527299; sample SD=1, SE=1/sqrt(3).
    assert a["ci95_low"] == pytest.approx(-0.4841377117)
    assert a["ci95_high"] == pytest.approx(4.4841377117)
    assert b["sd"] == 0 and b["ci95_low"] == b["ci95_high"] == 4
    assert result["source_sha256"] == hashlib.sha256(spec["csv"].encode()).hexdigest()
    assert a["runs"][0] == {"run": "11", "value": 1.0, "csv_line": 2}
    assert any("独立" in w for w in result["warnings"])


@pytest.mark.parametrize(
    "rows, reason",
    [
        ("A,11,1\nA,11,2", "重复"),
        ("A,11,1", "一次"),
        ("A,11,1\nA,23,", "缺少"),
        ("A,11,1\nA,23,NaN", "有限"),
        ("A,11,1\nA,23,inf", "有限"),
        ("A,11,1\nA,23,1e200", "有限"),
    ],
)
def test_invalid_runs_not_silently_removed(rows, reason):
    with pytest.raises(ValueError, match=reason):
        experiments.summarize(measurements(csv="method,seed,score\n" + rows))


def test_protocol_versions_keep_measurement_snapshot_and_export(client):
    created = client.post("/api/experiments/protocols", json=protocol())
    assert created.status_code == 200
    identifier = created.json()["id"]
    response = client.post(
        "/api/experiments/analyze", json=measurements(protocol_id=identifier)
    )
    assert response.status_code == 200
    value = response.json()
    assert value["protocol_snapshot"]["revision"] == 1
    changed = {**protocol(), "baseline": "新的对照基线"}
    edited = client.put(
        "/api/experiments/protocols/" + identifier,
        json={"protocol": changed, "revision": 1},
    )
    assert edited.json()["revision"] == 2
    assert (
        client.put(
            "/api/experiments/protocols/" + identifier,
            json={"protocol": changed, "revision": 1},
        ).status_code
        == 409
    )
    saved = research.artifact(value["id"])
    assert saved["content"]["protocol_snapshot"]["protocol"]["baseline"] == "BM25"
    bundle = client.get(f"/api/experiments/{value['id']}/files/bundle.zip")
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
        assert archive.testzip() is None
        assert archive.read("raw.csv") == measurements()["csv"].encode("utf-8")
        assert archive.read("chart.png").startswith(b"\x89PNG")
        analysis = json.loads(archive.read("analysis.json"))
        assert analysis["protocol_snapshot"]["revision"] == 1
    exported = client.get(f"/api/artifacts/{value['id']}/export?format=md").text
    assert "SHA-256" in exported and "ci95" in exported
    history = research.artifact(identifier)["content"]["history"]
    assert history[0]["protocol"]["baseline"] == "BM25"


def test_analysis_file_access_is_account_local(client):
    result = client.post("/api/experiments/analyze", json=measurements()).json()
    assert (
        client.post(
            "/api/account/register",
            json={"name": "separate-space", "password": "test-password-876"},
        ).status_code
        == 200
    )
    assert (
        client.get(f"/api/experiments/{result['id']}/files/raw.csv").status_code == 404
    )
    assert client.get("/api/artifacts/" + result["id"]).status_code == 404


def test_invalid_seed_and_false_source_rejected(client):
    assert (
        client.post(
            "/api/experiments/protocols", json={**protocol(), "seeds": [11, 11]}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/experiments/protocols",
            json={**protocol(), "source_artifact_id": "missing"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/experiments/analyze", json=measurements(protocol_id="missing")
        ).status_code
        == 404
    )


def test_protocol_mismatch_not_certified(client):
    value = client.post(
        "/api/experiments/protocols",
        json={
            **protocol(),
            "task": "language_modeling",
            "metric": "BLEU",
            "split": "按需要划分",
        },
    ).json()
    assert any("BLEU" in w for w in value["checks"])
    assert any("划分" in w for w in value["checks"])
    stats = experiments.summarize(
        measurements(csv="method,seed,score\nA,1,1\nA,2,2\nB,1,2\nB,3,3")
    )
    assert any("成对" in w for w in stats["warnings"])


def test_prune_numeric_restating_keeps_other_variants_conditions_and_sources():
    def c(text, block="source"):
        return {"text": text, "block_id": block}

    rich = c(
        "本论文的模型是12层的解码器-only transformer，隐藏维度为768，注意力头数为12。"
    )
    inputs = [
        rich,
        c("本论文的层数为12层"),
        c("本论文的隐藏维度为768"),
        c("本论文的注意力头数为12"),
        c("BERT-LARGE的层数是24，隐藏维度是1024，注意力头数是16。"),
        c("BERT-LARGE的隐藏维度是1024"),
        c("BERT-BASE的隐藏维度是768"),
        c("训练时隐藏维度为768"),
        c("本论文的隐藏维度为768", "different"),
        c("本论文的注意力头数不是12"),
    ]
    result = prune_repeated_facts(inputs)
    assert rich in result
    assert (
        inputs[1] not in result and inputs[2] not in result and inputs[3] not in result
    )
    assert inputs[5] not in result
    assert all(inputs[i] in result for i in [4, 6, 7, 8, 9])


def test_proposal_revision_preserves_original_and_source_background(
    client, monkeypatch
):
    from backend import model, proposal_revision

    original = {
        "abstract": "待开展研究",
        "introduction": "原文摘录：h=8",
        "method_plan": "调整注意力头，保持 dmodel、dk、dv 不变。",
        "evaluation_plan": "数据及训练测试划分：\n按比例划分。",
    }
    source = research.save_artifact(
        "writing",
        "注意力头实验",
        {
            "proposal": original,
            "sections": [],
            "draft": {"text": "人工草稿必须保留", "revision": 1},
        },
    )

    async def corrected(*args, **kwargs):
        return {
            "method_plan": "拟议从零训练小模型；固定 d_model=128，头数取 1、2、4、8，d_head=128/h 随之改变；不使用预训练权重。",
            "evaluation": {
                label: "拟议设置，资源待测；按官方固定划分，测试集不调参。"
                for label in proposal_revision.LABELS
            },
        }

    monkeypatch.setattr(model, "complete", corrected)

    class Context:
        def check(self):
            pass

        def progress(self, *args):
            pass

    revised = asyncio.run(
        proposal_revision.refine_plan(Context(), {"artifact_id": source["id"]})
    )
    assert revised["id"] != source["id"]
    assert revised["proposal"]["introduction"] == original["introduction"]
    assert revised["revision_audit"]["original_proposal"] == original
    assert (
        research.artifact(source["id"])["content"]["draft"]["text"]
        == "人工草稿必须保留"
    )
    assert not any("d_model = h" in w for w in revised["plan_checks"])


def test_dimension_checker_does_not_flag_explicit_correction():
    from backend.proposal_checks import fixed_attention_dimensions

    assert fixed_attention_dimensions("保持 dmodel、dk、dv 不变")
    assert not fixed_attention_dimensions("固定 d_model=128，d_head=128/h 随头数改变。")
    assert not fixed_attention_dimensions("不能同时固定 dmodel、dk、dv 不变。")


def test_statistics_preserve_physical_csv_lines():
    result = experiments.summarize(
        measurements(csv='method,seed,score\n\n"A\nmodel",11,1\n\n"A\nmodel",23,3\n')
    )
    assert [run["csv_line"] for run in result["summary"][0]["runs"]] == [3, 6]


def test_numeric_dedup_preserves_encoder_and_decoder_roles():
    claims = [
        {"text": "encoder层数为6", "block_id": "shared"},
        {"text": "decoder层数为6", "block_id": "shared"},
    ]
    assert prune_repeated_facts(claims) == claims


def test_plan_checks_expose_missing_runs_budget_and_hidden_failures():
    from backend.proposal_checks import assess_plan

    checks = assess_plan(
        {
            "method_plan": "从零训练小模型研究注意力头数量。不涉及预训练模型。",
            "evaluation_plan": "训练失败则重复运行。",
        }
    )
    assert any("随机种子" in check for check in checks)
    assert any("训练步数" in check for check in checks)
    assert any("失败重跑" in check for check in checks)
    assert not any("改变预训练模型头数" in check for check in checks)


def test_current_plan_checks_do_not_retain_obsolete_warning(client):
    source = research.save_artifact(
        "writing",
        "检查更新",
        {
            "proposal": {
                "method_plan": "从零训练小模型，不涉及预训练模型。",
                "evaluation_plan": "资源待测",
            },
            "plan_checks": ["旧版本误报"],
        },
    )
    content = research.artifact(source["id"])["content"]
    assert "旧版本误报" not in content["plan_checks"]
    assert content["historical_plan_checks"] == ["旧版本误报"]
    with store.connection() as conn:
        saved = json.loads(
            conn.execute(
                "SELECT content FROM artifacts WHERE id=?", (source["id"],)
            ).fetchone()[0]
        )
    assert saved["plan_checks"] == ["旧版本误报"]
