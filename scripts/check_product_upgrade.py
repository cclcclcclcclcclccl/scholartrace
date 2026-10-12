"""Real local inference smoke checks. Preserve first results, including failures."""

import hashlib
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import store

output = ROOT / "artifacts/product-audit/live-first-run.json"
if output.exists():
    raise SystemExit("Refusing to overwrite first-run results")
report = {"notice": "Real model smoke checks; agent-authored cases, not an independent accuracy benchmark.", "results": []}


def save(name, value, checks):
    report["results"].append({"name": name, "value": value, "checks": checks})
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(name, checks, flush=True)


with httpx.Client(base_url="http://127.0.0.1:8765", timeout=240, trust_env=False) as client:
    papers = {p["name"]: p for p in client.get("/api/documents").json()}
    identifiers = [papers[n]["id"] for n in ["1706.03762v1.pdf", "N19-1423.pdf"]]
    csv = "step,loss\n1,0.8\n10,0.4\n100,0.1"
    intent = "横轴为 step，纵轴为 loss，使用散点图，两个坐标轴都用对数刻度。不要连线。"
    response = client.post("/api/charts/plan", json={"csv": csv, "intent": intent})
    plan = response.json()
    save("chart_intent", plan, {"http_ok": response.is_success, "requested_axes": plan.get("x") == "step" and plan.get("ys") == ["loss"], "kind": plan.get("kind") == "scatter", "scales": plan.get("xscale") == plan.get("yscale") == "log"})
    if response.is_success:
        chart = client.post("/api/charts", json={k: v for k, v in {**plan, "csv": csv}.items() if k in {"csv", "x", "ys", "kind", "title", "unit", "xscale", "yscale"}})
        save("chart_render", chart.json(), {"http_ok": chart.is_success})
    original = client.get("/api/translation/glossary").json()
    try:
        terms = [t for t in original if t["source"].lower() != "self-attention"] + [{"source": "self-attention", "target": "自注意力"}]
        client.put("/api/translation/glossary", json={"terms": terms}).raise_for_status()
        source = "Self-attention may not improve accuracy in all settings. We use 8 heads and a learning rate of 0.001. Keep `attention(x)` unchanged."
        response = client.post("/api/translate/text", json={"text": source, "language": "zh"})
        translated = response.json()
        value = translated.get("translation", "")
        save("translation", {"source": source, **translated}, {"http_ok": response.is_success, "term": "自注意力" in value, "numbers_code": all(t in value for t in ["8", "0.001", "`attention(x)`"]), "negation": any(t in value for t in ["不", "未", "无"]), "uncertainty": any(t in value for t in ["可能", "或许"])} )
    finally:
        client.put("/api/translation/glossary", json={"terms": original}).raise_for_status()
    job = client.post("/api/jobs", json={"kind": "matrix", "payload": {"document_ids": identifiers, "fields": ["主要模型的层数和隐藏维度是多少？", "训练实际产生多少千克碳排放？"], "topic": "实测：模型规格与未报告指标"}})
    job.raise_for_status()
    value = job.json()
    deadline = time.monotonic() + 600
    while value["state"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(2)
        value = client.get("/api/jobs/" + value["id"]).json()
    result = value.get("result") or {}
    matrix = result.get("matrix", [])
    claims = [claim for row in matrix for cell in row["cells"] for claim in cell["claims"]]
    sources = {b["id"]: b["text"] for identifier in identifiers for b in store.get_blocks(identifier)}
    save("matrix", value, {"completed": value["state"] == "completed", "two_papers": len(matrix) == 2, "known_answer_cells": all(row["cells"][0]["claims"] for row in matrix) if matrix else False, "unreported_emissions_abstained": all(not row["cells"][1]["claims"] for row in matrix) if matrix else False, "quotes_exist": bool(claims) and all(store.quote_in_source(c["quote"], sources.get(c["block_id"], "")) for c in claims)})
