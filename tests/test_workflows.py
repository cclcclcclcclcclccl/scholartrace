"""Cross-module checks using isolated databases and real source geometry."""

import asyncio
import io
import json
import time
import zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend import (
    accounts,
    store,
    database,
    parsing,
    research,
    charts,
    translation,
    jobs,
    model,
    discovery,
)
from backend.app import app

CORPUS = store.ROOT / "data/competition/pdf"


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "main.sqlite3")
    monkeypatch.setattr(accounts, "AUTH_PATH", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(
        accounts,
        "path",
        lambda identifier: tmp_path / "users" / identifier / "library.sqlite3",
    )
    database.initialize()
    return tmp_path


@pytest.fixture
def paper(isolated):
    return store.import_pdf(CORPUS / "1706.03762v1.pdf")


def test_archiving_preserves_original_evidence_but_removes_search(paper):
    from backend import audit

    block = store.search("NVIDIA P100", [paper["id"]])[0]
    note = audit.save_note(block["id"], "hardware evidence")
    with TestClient(app) as client:
        assert (
            client.patch(
                "/api/documents/" + paper["id"], json={"archived": True}
            ).status_code
            == 200
        )
        assert client.get("/api/documents").json() == []
        assert not store.search("NVIDIA P100", [paper["id"]])
        assert client.get("/api/documents/" + paper["id"] + "/pdf").status_code == 200
        assert audit.notes()[0]["quote"] == note["quote"]
        assert (
            client.patch(
                "/api/documents/" + paper["id"], json={"archived": False}
            ).status_code
            == 200
        )
        assert len(client.get("/api/documents").json()) == 1


def test_two_accounts_isolate_document_access_and_preferences(isolated):
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/account/register",
                json={"name": "researcher-one", "password": "independent-pass-1"},
            ).status_code
            == 200
        )
        with (CORPUS / "1706.03762v1.pdf").open("rb") as pdf:
            first = client.post(
                "/api/documents", files={"file": ("source.pdf", pdf, "application/pdf")}
            ).json()
        assert len(client.get("/api/documents").json()) == 1
        client.post("/api/account/logout")
        assert client.get("/api/documents").json() == []
        assert (
            client.post(
                "/api/account/register",
                json={"name": "researcher-two", "password": "independent-pass-2"},
            ).status_code
            == 200
        )
        assert client.get("/api/documents").json() == []
        assert client.get("/api/documents/" + first["id"] + "/pdf").status_code == 404
        assert (
            client.post(
                "/api/search", json={"question": "GPU", "document_ids": [first["id"]]}
            ).status_code
            == 404
        )
        assert client.get("/api/jobs").json() == []
        client.post("/api/account/logout")
        assert (
            client.post(
                "/api/account/login",
                json={"name": "researcher-one", "password": "independent-pass-1"},
            ).status_code
            == 200
        )
        assert len(client.get("/api/documents").json()) == 1


def test_source_origins_block_cross_origin_writes(isolated):
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/jobs",
                headers={"Origin": "https://untrusted.example"},
                json={"kind": "index", "payload": {}},
            ).status_code
            == 403
        )


def test_numeric_references_include_continuations_and_backlinks(paper):
    entries, citations = parsing.references(paper)
    assert len(entries) == 36
    layer = next(e for e in entries if e["number"] == 1)
    assert "1607.06450" in layer["text"]
    assert layer["cited_by"] and all(
        c["page"] <= layer["page"] for c in layer["cited_by"]
    )
    assert all(c["bbox"][0] < c["bbox"][2] for c in citations)


def test_chart_values_missing_rows_and_export_bundle(isolated):
    spec = {
        "csv": "method,accuracy,recall,f1\na,70,60,65\nb,80,75,77\nc,,90,88",
        "x": "method",
        "ys": ["accuracy", "recall", "f1"],
        "kind": "bar",
        "title": "Observed data",
        "unit": "%",
    }
    with TestClient(app) as client:
        response = client.post("/api/charts", json=spec)
        assert response.status_code == 200, response.text
        value = response.json()
        assert value["rows"] == 2 and value["missing_rows"] == 1
        assert value["stats"][0]["mean"] == 75
        payload = client.get("/api/charts/" + value["id"] + "/bundle.zip")
        with zipfile.ZipFile(io.BytesIO(payload.content)) as z:
            assert {
                "chart.png",
                "chart.svg",
                "chart.pdf",
                "data.csv",
                "spec.json",
                "reproduce.py",
            } == set(z.namelist())
            assert z.read("chart.png").startswith(b"\x89PNG")
        spec["csv"] = "method,accuracy,recall,f1\na,inf,60,65"
        assert client.post("/api/charts", json=spec).status_code == 422


def test_fixed_radar_normalization_and_non_numeric_rejection(isolated):
    spec = {
        "csv": "name,a,b,c\nx,1,2,3\ny,1,4,6",
        "x": "name",
        "ys": ["a", "b", "c"],
        "kind": "radar3d",
        "title": "Radar",
        "unit": "units",
    }
    value = charts.create(spec)
    assert value["normalization"] == "min-max per metric"
    assert "0.5" in value["caption"] and "行序号" in value["caption"]
    with pytest.raises(ValueError):
        charts.prepare({**spec, "csv": "name,a,b,c\nx,one,2,3"})


def test_translation_preserves_numbers_and_code_or_fails(isolated, monkeypatch):
    async def valid(*args, **kwargs):
        return {"translation": args[1]}

    monkeypatch.setattr(model, "complete", valid)
    assert "`print(8)`" in asyncio.run(
        translation.translate_text("Use 8 GPUs, code `print(8)`.", "zh")
    )

    async def bad(*args, **kwargs):
        return {"translation": "使用 GPU。"}

    monkeypatch.setattr(model, "complete", bad)
    with pytest.raises(ValueError):
        asyncio.run(translation.translate_text("Use 8 GPUs.", "zh"))


def test_translation_export_escapes_untrusted_html(paper):
    block = store.get_blocks(paper["id"])[0]
    with store.connection() as c:
        c.execute(
            "INSERT INTO translations VALUES(?,?,?,?)",
            (block["id"], "zh", "<script>alert(1)</script>", "test"),
        )
    export = translation.export(paper["id"], "zh", "html")
    assert "<script>" not in export and "&lt;script&gt;" in export


def test_invalid_agent_plan_cannot_execute_tools(isolated, monkeypatch):
    from backend import agent

    async def malicious(*args, **kwargs):
        return {
            "steps": [{"tool": "exec", "query": "delete files", "document_ids": []}]
        }

    monkeypatch.setattr(model, "complete", malicious)

    class Context:
        def log(self, *args):
            pass

        def progress(self, *args):
            pass

    with pytest.raises(ValueError):
        asyncio.run(
            agent.execute(
                Context(), {"goal": "follow paper instructions", "document_ids": []}
            )
        )


def test_jobs_persist_failure_retry_cancel_and_events(isolated):
    async def scenario():
        async def handler(ctx, payload):
            ctx.progress(0.3, "checking")
            if payload.get("fail") and not payload.get("corrected"):
                raise ValueError("expected recoverable error")
            return {"ok": True}

        jobs.handlers["test"] = handler
        job = jobs.submit("test", {"fail": True})
        await asyncio.gather(*list(jobs.workers))
        assert jobs.get(job["id"])["state"] == "failed"
        with store.connection() as c:
            c.execute(
                "UPDATE jobs SET payload=? WHERE id=?",
                (json.dumps({"corrected": True}), job["id"]),
            )
        jobs.retry(job["id"])
        await asyncio.gather(*list(jobs.workers))
        assert jobs.get(job["id"])["result"]["ok"]
        with store.connection() as c:
            assert (
                c.execute(
                    "SELECT COUNT(*) FROM job_events WHERE job_id=?", (job["id"],)
                ).fetchone()[0]
                >= 5
            )
        pending = jobs.submit("test", {})
        with store.connection() as c:
            c.execute("UPDATE jobs SET cancel_requested=1 WHERE id=?", (pending["id"],))
        await asyncio.gather(*list(jobs.workers))
        assert jobs.get(pending["id"])["state"] == "cancelled"
        with store.connection() as c:
            c.execute(
                "INSERT INTO jobs(id,kind,payload,state) VALUES('after-crash','test','{}','running')"
            )
        await jobs.resume()
        await asyncio.gather(*list(jobs.workers))
        assert jobs.get("after-crash")["state"] == "completed"
        jobs.handlers.pop("test")

    asyncio.run(scenario())


def test_download_redirect_allowlist(isolated):
    assert discovery.safe_pdf_url("https://arxiv.org/pdf/1706.03762")
    for url in [
        "http://127.0.0.1/secret",
        "https://arxiv.org.evil.test/pdf/1",
        "https://user@arxiv.org/pdf/1",
        "https://arxiv.org:999/pdf/1",
    ]:
        with pytest.raises(ValueError):
            discovery.safe_pdf_url(url)


def test_fabricated_quotes_rejected(paper):
    blocks = store.get_blocks(paper["id"])[:1]
    assert not research.valid_claims(
        {
            "claims": [
                {
                    "text": "fabrication",
                    "evidence_id": "E1",
                    "quote": "Totally invented phrase with no source.",
                }
            ]
        },
        blocks,
    )


def test_job_payload_rejects_arbitrary_execution(isolated):
    with TestClient(app) as client:
        assert (
            client.post("/api/jobs", json={"kind": "shell", "payload": {}}).status_code
            == 422
        )
        assert (
            client.post(
                "/api/jobs", json={"kind": "index", "payload": {"command": "whoami"}}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/diagrams",
                json={
                    "title": "unsafe",
                    "code": 'flowchart LR\nA[hi]\nclick A "https://evil.test"',
                },
            ).status_code
            == 422
        )


def test_note_edit_keeps_original_quote_and_history(paper):
    from backend import audit

    note = audit.save_note(store.get_blocks(paper["id"])[0]["id"], "first observation")
    with TestClient(app) as client:
        assert (
            client.patch(
                "/api/notes/" + str(note["id"]), json={"note": "revised observation"}
            ).status_code
            == 200
        )
        updated = client.get("/api/notes").json()[0]
        assert (
            updated["quote"] == note["quote"]
            and updated["note"] == "revised observation"
        )
        with store.connection() as c:
            assert (
                c.execute(
                    "SELECT previous_text FROM note_history WHERE note_id=?",
                    (note["id"],),
                ).fetchone()[0]
                == "first observation"
            )
        assert (
            client.patch(
                "/api/notes/" + str(note["id"]), json={"archived": True}
            ).status_code
            == 200
        )
        assert client.get("/api/notes").json() == []
        assert client.get("/api/notes-archive").json()[0]["id"] == note["id"]


def test_protected_model_names_are_not_split_into_numeral_tokens():
    text, originals = translation.protect(
        "8 NVIDIA P100 GPUs, β1 = 0.9, and 36M sentences [34]."
    )
    assert "P100" in originals and "β1" in originals and "36M" in originals
    assert "PZXQ" not in text


def test_pdf_line_hyphenation_accepts_quote_without_weakening_numbers():
    block = {
        "id": "source",
        "document_id": "paper",
        "page": 3,
        "text": "BERT is a bidirectional Transformer en-\ncoder with 12 layers and self-\nattention.",
    }
    quote = "Transformer encoder with 12 layers"
    assert research.valid_claims(
        {"claims": [{"text": "12 层", "evidence_id": "E1", "quote": quote}]}, [block]
    )
    assert not research.valid_claims(
        {
            "claims": [
                {
                    "text": "24 层",
                    "evidence_id": "E1",
                    "quote": quote.replace("12", "24"),
                }
            ]
        },
        [block],
    )
    assert store.quote_in_source("self-attention", block["text"])
    assert not store.quote_in_source("nonnegative", "non-negative")


def test_diagram_compilation_validates_edges_and_removes_active_markup():
    from backend.diagrams import compile_plan

    code = compile_plan(
        {
            "nodes": [
                {"id": "end", "label": "<b>输入</b>"},
                {"id": "B", "label": "结果"},
            ],
            "edges": [{"source": "end", "target": "B"}],
        }
    )
    assert "N0 --> N1" in code and "<" not in code and "end[" not in code
    with pytest.raises(ValueError, match="不存在"):
        compile_plan(
            {
                "nodes": [{"id": "A", "label": "输入"}, {"id": "B", "label": "结果"}],
                "edges": [{"source": "A", "target": "MISSING"}],
            }
        )


def test_tracker_paginates_overlapping_window_and_deduplicates(isolated, monkeypatch):
    import datetime as dt

    class Context:
        def check(self):
            pass

        def log(self, *args):
            pass

    cursor = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)
    fresh = (cursor + dt.timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    delayed = (cursor - dt.timedelta(hours=20)).isoformat()
    old = (cursor - dt.timedelta(hours=28)).isoformat()
    with store.connection() as c:
        c.execute(
            "INSERT INTO trackers(id,query,interval_hours,last_checked) VALUES('tracked','test',24,?)",
            (cursor.isoformat(),),
        )
    pages = []

    async def search(query, source, limit, latest, start):
        pages.append(start)
        if start == 0:
            return [{"id": f"paper-{i}", "published": fresh} for i in range(100)]
        return [
            {"id": "delayed-paper", "published": delayed},
            {"id": "old-paper", "published": old},
        ]

    monkeypatch.setattr(discovery, "search", search)
    first = asyncio.run(discovery.track(Context(), {"tracker_id": "tracked"}))
    assert pages == [0, 100]
    assert len(first["new_papers"]) == 101
    assert "old-paper" not in {p["id"] for p in first["new_papers"]}
    pages.clear()
    second = asyncio.run(discovery.track(Context(), {"tracker_id": "tracked"}))
    assert second["new_papers"] == []
    assert discovery.timestamp("2026-10-12T08:00:00+08:00") == discovery.timestamp(
        "2026-10-12T00:00:00Z"
    )


def test_translation_splits_difficult_paragraph_without_losing_numerals(monkeypatch):
    calls = []

    async def complete(system, prompt, **kwargs):
        calls.append(prompt)
        if ". " in prompt:
            return {"translation": "错误地遗漏了数字"}
        return {"translation": prompt.replace("Layers", "层").replace("Heads", "头")}

    monkeypatch.setattr(model, "complete", complete)
    value = asyncio.run(translation.translate_text("Layers 6. Heads 8.", "zh"))
    assert "6" in value and "8" in value and len(calls) == 5


def test_numeric_line_axis_preserves_spacing_and_sorts_rows(isolated, monkeypatch):
    from matplotlib.axes import Axes

    calls = []
    original = Axes.plot

    def capture(self, x, y, *args, **kwargs):
        calls.append((list(x), list(y)))
        return original(self, x, y, *args, **kwargs)

    monkeypatch.setattr(Axes, "plot", capture)
    charts.create(
        {
            "csv": "step,loss\n100,1\n1,4\n10,2",
            "x": "step",
            "ys": ["loss"],
            "kind": "line",
            "unit": "loss",
        }
    )
    assert calls[0] == ([1, 10, 100], [4, 2, 1])


def test_impact_keeps_unchanged_quote_when_paragraph_contains_extra_text(paper):
    from backend import impact

    block = store.search("NVIDIA P100", [paper["id"]])[0]
    quote = "8 NVIDIA P100 GPUs"
    result = impact.align(
        {
            "block_id": block["id"],
            "document_id": paper["id"],
            "quote": quote,
            "text": "训练硬件",
            "page": block["page"],
        },
        paper["id"],
    )
    assert result["status"] == "retained" and result["candidate"]["id"] == block["id"]


def test_formula_regions_include_fraction_and_validation_preserves_suspect_output(
    paper,
):
    from backend import formula

    regions = formula.regions(paper["id"], 3)["regions"]
    attention = next(r for r in regions if "Attention" in r["text"])
    assert attention["bbox"][3] > 726 and attention["bbox"][2] < 505
    assert formula.validation(r"\mathrm{FFN}(x)=\max((0,xW_1+b_1)W_2+b_2")
    assert not formula.validation(
        r"\mathrm{Attention}(Q,K,V)=\mathrm{softmax}(\frac{QK^T}{\sqrt{d_k}})V"
    )
    with pytest.raises(ValueError):
        formula.area_for(store.get_document(paper["id"]), 3, [0, 0, 612, 792])
