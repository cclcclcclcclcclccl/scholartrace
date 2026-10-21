"""Explicitly selected real-source developer checks; not independent model accuracy."""

import ast
import asyncio
import copy
import json
import sqlite3
import sys
import time
import zipfile
from pathlib import Path

import httpx
import transfer_study as study

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import app, model, store

FOLDER = ROOT / "artifacts/source-followup-20261021"


async def main():
    assert not (FOLDER / "run.json").exists(), "Preserve every inference attempt"
    previous_zip = (
        ROOT / "output/research-polish-20261021/ScholarTrace-source-20261021.zip"
    )
    with zipfile.ZipFile(previous_zip) as archive:
        before = ast.parse(archive.read("backend/research.py").decode("utf-8"))
    after = ast.parse((ROOT / "backend/research.py").read_text(encoding="utf-8"))
    old = next(
        n
        for n in before.body
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "_grounded"
    )
    new = next(
        n
        for n in after.body
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "validate_answer"
    )
    start = next(
        i
        for i, n in enumerate(old.body)
        if isinstance(n, ast.Assign)
        and any(
            isinstance(t, ast.Name) and t.id == "candidate_claim_count"
            for t in n.targets
        )
    )
    assert ast.dump(
        ast.Module(body=copy.deepcopy(old.body[start:]), type_ignores=[])
    ) == ast.dump(ast.Module(body=new.body, type_ignores=[]))
    protocol = json.loads(study.PROTOCOL.read_text(encoding="utf-8"))
    chosen = [
        (
            "preln_original",
            "2002.04745v2.pdf",
            "966ff2ae0bf0e6614b4f4c32",
            next(c["question"] for c in protocol["cases"] if c["id"] == "preln_scope"),
        ),
        (
            "preln_focused",
            "2002.04745v2.pdf",
            "966ff2ae0bf0e6614b4f4c32",
            "原文中，Post-LN初始化时靠近输出层的参数梯度有什么特点？较大学习率会造成什么后果，warm-up怎样帮助？",
        ),
        (
            "ln_batch",
            "1607.06450v1.pdf",
            "d8678cd1dab39c165ca66171",
            "只依据此段，Layer Normalization可以在batch size为1时使用吗？请保留适用条件。",
        ),
        (
            "missing_hardware",
            "1607.06450v1.pdf",
            "d8678cd1dab39c165ca66171",
            "只依据此段，训练峰值显存实测精确是多少GB？不能估算或采用别的论文的数值。",
        ),
    ]
    cases = []
    for key, file, block_id, question in chosen:
        doc = protocol["papers"][file]["id"]
        block = next(b for b in store.get_blocks(doc) if b["id"] == block_id)
        cases.append(
            {
                "id": key,
                "question": question,
                "document_ids": [doc],
                "source_block_id": block_id,
                "source_quote": block["text"],
            }
        )
    freeze = {
        "notice": "Four developer-authored source-conditioned checks on exposed papers and questions. Sources deliberately selected by developer; no new blind accuracy score.",
        "cases": cases,
        "code_sha256": study.code_hashes(),
        "validation_body_unchanged": True,
        "previous_source_zip_sha256": study.digest(previous_zip),
    }
    study.write(FOLDER / "protocol.json", freeze)
    original = store.database_path()
    before_data = study.snapshot(original)
    study.write(FOLDER / "original-before.json", before_data)
    with (
        sqlite3.connect(original) as src,
        sqlite3.connect(FOLDER / "library.sqlite3") as dst,
    ):
        src.backup(dst)
    token = store.database_override.set(FOLDER / "library.sqlite3")
    calls = []
    rows = []
    current = {}
    complete = model.complete

    async def traced(*args, **kwargs):
        entry = {"case_id": current["id"], "args": args, "kwargs": kwargs}
        begin = time.monotonic()
        try:
            output = await complete(*args, **kwargs)
            entry["output"] = copy.deepcopy(output)
            return output
        except Exception as error:
            entry["error"] = type(error).__name__ + ": " + str(error)
            raise
        finally:
            entry["seconds"] = round(time.monotonic() - begin, 3)
            calls.append(entry)
            study.write(FOLDER / "model-calls.json", calls)

    model.complete = traced
    report = {"complete": False, "rows": rows, "code_sha256": freeze["code_sha256"]}
    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            runtime = (await client.get("http://127.0.0.1:8081/v1/models")).json()
        report["model_sha256"] = study.digest(Path(runtime["data"][0]["id"]))
        for case in cases:
            current["id"] = case["id"]
            row = {"id": case["id"]}
            begin = time.monotonic()
            try:
                async with asyncio.timeout(180):
                    response = await app.ask(
                        app.Query(**{k: v for k, v in case.items() if k != "id"})
                    )
                row["response"] = response
                assert [b["id"] for b in response["evidence"]] == [
                    case["source_block_id"]
                ]
                row["source_scope_correct"] = True
            except Exception as error:  # noqa: BLE001 -- retain all failed evaluation rows
                row["error"] = type(error).__name__ + ": " + str(error)
            row["seconds"] = round(time.monotonic() - begin, 3)
            rows.append(row)
            study.write(FOLDER / "run.json", report)
            print(
                case["id"],
                [c["text"] for c in row.get("response", {}).get("model_answer") or []],
                row.get("error", ""),
                flush=True,
            )
        report["complete"] = True
    finally:
        model.complete = complete
        store.database_override.reset(token)
        after_data = study.snapshot(original)
        study.write(FOLDER / "original-after.json", after_data)
        report["formal_data_unchanged"] = before_data == after_data
        study.write(FOLDER / "run.json", report)


if __name__ == "__main__":
    asyncio.run(main())
