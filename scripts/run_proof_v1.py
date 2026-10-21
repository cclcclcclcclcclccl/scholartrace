"""Frozen first-pass real inference in an isolated SQLite snapshot, with incremental evidence."""

import argparse
import asyncio
import copy
import hashlib
import importlib
import json
import platform
import re
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import alignment, model, retrieval, review, store

parser = argparse.ArgumentParser()
parser.add_argument("--protocol-dir", default="evaluation/proof_v1")
parser.add_argument("--output-dir", default="artifacts/proof-v1-first-run")
parser.add_argument("--model-file", default="models/Qwen3-4B-Q4_K_M.gguf")
parser.add_argument("--runtime-config", default="scripts/supervisor.mjs")
args = parser.parse_args()
FOLDER = ROOT / args.output_dir
PROTOCOL = ROOT / args.protocol_dir / "protocol.json"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def snapshot(path):
    with sqlite3.connect(path) as c:
        c.row_factory = sqlite3.Row
        c.execute("BEGIN")
        result = {}
        for table in [
            "documents",
            "blocks",
            "evidence_notes",
            "artifacts",
            "projects",
            "project_documents",
            "project_artifacts",
        ]:
            rows = sorted(
                json.dumps(dict(r), sort_keys=True, ensure_ascii=False)
                for r in c.execute("SELECT * FROM " + table)
            )
            result[table] = {
                "count": len(rows),
                "sha256": hashlib.sha256("\n".join(rows).encode()).hexdigest(),
            }
        return {
            "integrity": c.execute("PRAGMA integrity_check").fetchone()[0],
            "tables": result,
        }


def write(name, value):
    (FOLDER / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def checks(case, result, docs):
    claims = result.get("model_answer") or []
    text = " ".join(c["text"] for c in claims)
    valid = []
    for c in claims:
        b = docs.get(c.get("block_id"))
        valid.append(
            bool(
                b
                and b["document_id"] == c.get("document_id")
                and store.quote_in_source(c.get("quote", ""), b["text"])
            )
        )
    return {
        "claims": len(claims),
        "claims_with_valid_source": sum(valid),
        "source_valid": all(valid) if claims else None,
        "nonempty": bool(claims),
        "pattern_screen": all(
            re.search(p, text, re.IGNORECASE) for p in case["required_patterns"]
        )
        if not case["unanswerable"]
        else None,
        "abstained": not claims,
        "labelled_source_hit": any(
            b["id"] in {e["id"] for e in result.get("evidence", [])}
            for b in case["sources"]
        )
        if case["sources"]
        else None,
    }


async def main():
    assert not (FOLDER / "run.json").exists(), "Refuse to overwrite first-run evidence"
    FOLDER.mkdir(parents=True, exist_ok=True)
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    freeze = json.loads((PROTOCOL.parent / "freeze.json").read_text(encoding="utf-8"))
    assert digest(PROTOCOL) == freeze["protocol_sha256"]
    assert all(digest(ROOT / p) == h for p, h in freeze["code_sha256"].items()), (
        "Product changed after freeze"
    )
    original = store.database_path()
    before = snapshot(original)
    write("original-before.json", before)
    with (
        sqlite3.connect(original) as src,
        sqlite3.connect(FOLDER / "evaluation.sqlite3") as dst,
    ):
        src.backup(dst)
    token = store.database_override.set(FOLDER / "evaluation.sqlite3")
    papers = {d["name"]: d for d in store.list_documents()}
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "protocol_sha256": freeze["protocol_sha256"],
        "code_sha256": freeze["code_sha256"],
        "python": sys.version,
        "platform": platform.platform(),
        "model_file_sha256": digest(ROOT / args.model_file),
        "model_file": args.model_file,
        "model_endpoint": model.URL,
        "runtime_config_sha256": digest(ROOT / args.runtime_config),
        "runtime_config": args.runtime_config,
        "notice": protocol["notice"],
        "qa": [],
        "controlled_review": [],
        "real_review": [],
        "complete": False,
    }
    model_trace = []
    current = {"id": None}
    original_complete = model.complete

    async def traced(*args, **kwargs):
        start = time.monotonic()
        entry = {"case_id": current["id"], "args": args, "kwargs": kwargs}
        try:
            output = await original_complete(*args, **kwargs)
            entry["output"] = copy.deepcopy(output)
            return output
        except BaseException as e:
            entry["error"] = type(e).__name__ + ": " + str(e)
            raise
        finally:
            entry["seconds"] = round(time.monotonic() - start, 3)
            model_trace.append(entry)
            write("model-calls.json", model_trace)

    model.complete = traced
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=15) as health:
            report["health"] = (
                await health.get("http://127.0.0.1:8765/api/health")
            ).json()
            report["models"] = (await health.get(model.URL + "/models")).json()
        used = (
            {f for c in protocol["qa"] for f in c["files"]}
            | {c["source"]["file"] for c in protocol["real_review"]}
            | {c["target_file"] for c in protocol["real_review"]}
        )
        report["pdf_hashes"] = {
            f: digest(Path(store.get_document(papers[f]["id"])["path"]))
            for f in sorted(used)
        }
        write("run.json", report)
        app = importlib.import_module("backend.app")
        for case in protocol["qa"]:
            current["id"] = case["id"]
            ids = [papers[f]["id"] for f in case["files"]]
            docs = {b["id"]: b for id in ids for b in store.get_blocks(id)}
            row = {"id": case["id"], "question": case["question"]}
            start = time.monotonic()
            try:
                # Equal Chinese query and explicit scope. This comparison excludes product query expansion.
                baseline = {}
                for name, fn in [
                    ("lexical", store.search),
                    ("hybrid", retrieval.search),
                ]:
                    t = time.monotonic()
                    hits = await asyncio.to_thread(fn, case["question"], ids, 10)
                    baseline[name] = {
                        "ids": [b["id"] for b in hits],
                        "seconds": round(time.monotonic() - t, 3),
                        "labelled_hits": sum(
                            s["id"] in {b["id"] for b in hits} for s in case["sources"]
                        ),
                        "labelled_total": len(case["sources"]),
                    }
                row["retrieval_baselines"] = baseline
                t = time.monotonic()
                async with asyncio.timeout(300):
                    result = await app.ask(
                        app.Query(question=case["question"], document_ids=ids)
                    )
                row["answer_seconds"] = round(time.monotonic() - t, 3)
                row["response"] = result
                row["screen"] = checks(case, result, docs)
            except Exception as e:  # noqa: BLE001 -- every failed evaluation remains in the denominator
                row["error"] = type(e).__name__ + ": " + str(e)
            row["total_seconds"] = round(time.monotonic() - start, 3)
            report["qa"].append(row)
            write("run.json", report)
            print("QA", case["id"], row.get("screen", row.get("error")), flush=True)
        indexes = {}
        async with httpx.AsyncClient(timeout=80, trust_env=False) as client:
            for group in ["controlled_review", "real_review"]:
                for case in protocol[group]:
                    current["id"] = case["id"]
                    row = {"id": case["id"], "expected": case["expected"]}
                    start = time.monotonic()
                    try:
                        if group == "controlled_review":
                            item = {
                                "status": "review_required",
                                "note": {
                                    "note": case["observation"],
                                    "quote": case["old"],
                                },
                                "candidate": {"text": case["new"]},
                            }
                        else:
                            d = papers[case["target_file"]]
                            if d["id"] not in indexes:
                                indexes[d["id"]] = await asyncio.to_thread(
                                    alignment.SourceAligner, store.get_blocks(d["id"])
                                )
                            aligned = await asyncio.to_thread(
                                indexes[d["id"]].locate, case["source"]["text"]
                            )
                            item = {
                                **aligned,
                                "note": {
                                    **case["source"],
                                    "note": case["observation"],
                                    "quote": case["source"]["text"],
                                },
                            }
                        row["input"] = item
                        row["baseline"] = (
                            "same_claim"
                            if item.get("candidate")
                            and store.quote_normalize(item["note"]["quote"])
                            == store.quote_normalize(item["candidate"]["text"])
                            else "claim_changed"
                            if item.get("candidate")
                            else "unclear"
                        )
                        async with asyncio.timeout(90), model.gate:
                            row["result"] = await review.review_change(
                                item, client, model.URL, model.NAME
                            )
                        row["prediction"] = row["result"].get("decision", "unavailable")
                        row["exact"] = row["prediction"] == row["expected"]
                    except Exception as e:  # noqa: BLE001 -- every failed evaluation remains in the denominator
                        row.update(
                            error=type(e).__name__ + ": " + str(e),
                            prediction="unavailable",
                            exact=False,
                        )
                    row["seconds"] = round(time.monotonic() - start, 3)
                    report[group].append(row)
                    write("run.json", report)
                    print(
                        group,
                        case["id"],
                        row.get("baseline"),
                        row["prediction"],
                        row["expected"],
                        row["seconds"],
                        flush=True,
                    )
        report["complete"] = True
    finally:
        model.complete = original_complete
        store.database_override.reset(token)
        after = snapshot(original)
        write("original-after.json", after)
        report["original_data_unchanged"] = before == after
        report["finished_at"] = datetime.now(UTC).isoformat()
        write("run.json", report)
        print(
            "Finished; original data unchanged:",
            report["original_data_unchanged"],
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
