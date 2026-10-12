"""Actual local model/API checks; saves complete results, including failures."""
import asyncio
import json
import time
from pathlib import Path
import sys
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "artifacts/full-workbench"
V1 = "0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476"
V7 = "bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697"
BERT = "987545ffb087f1ece898142c403a516baeabeb70ce19089397fac6f7db12c3d4"


async def main():
    report = json.loads((OUT / "completion-report.json").read_text(encoding="utf-8")) if "--retry" in sys.argv else {}
    def save():
        (OUT / "completion-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8765", timeout=240, trust_env=False) as client:
        async def job(kind, payload):
            response = await client.post("/api/jobs", json={"kind": kind, "payload": payload})
            response.raise_for_status()
            value = response.json()
            for _ in range(240):
                if value["state"] in {"completed", "failed", "cancelled"}:
                    break
                await asyncio.sleep(1)
                value = (await client.get("/api/jobs/" + value["id"])).json()
            return value
        async def check(name, fn, predicate):
            if report.get(name, {}).get("passed"):
                return
            start = time.monotonic()
            try:
                value = await fn()
                report[name] = {"result": value, "passed": bool(predicate(value)), "seconds": round(time.monotonic()-start, 2)}
            except Exception as exc:
                report[name] = {"passed": False, "error": repr(exc)}
            save()
            print(name, report[name]["passed"], report[name].get("seconds"), flush=True)
        async def post(path, body):
            response = await client.post(path, json=body); response.raise_for_status(); return response.json()
        await check("multi_paper", lambda: post("/api/ask", {"question": "比较 BERT 和原始 Transformer 的编码器架构，每篇分别说明其结构及注意力方式。", "document_ids": [V1, BERT]}),
                    lambda v: len(v.get("comparison", [])) == 2 and all(r["claims"] for r in v["comparison"]))
        await check("diagram", lambda: job("diagram", {"topic": "为论文助手设计流程图：导入 PDF，解析段落，混合检索，检查原文引文，然后输出有出处的回答。"}), lambda v: v["state"] == "completed" and "flowchart" in v["result"]["code"])
        await check("agent_chart", lambda: job("agent", {"goal": "只根据以下 CSV 画 loss 折线图，横轴 step，纵轴 loss。不要综述。\nstep,loss\n1,4\n10,2\n100,1", "document_ids": [V1]}),
                    lambda v: v["state"] == "completed" and any(r["tool"] == "chart" for r in v["result"]["results"]))
        await check("version_diff", lambda: post("/api/versions/diff", {"first": V1, "second": V7}), lambda v: len(v["changes"]) > 0 and all(b["document_id"] == V1 for c in v["changes"] for b in c["before"]))
        response = await client.get(f"/api/documents/{V1}/translation/export?language=zh&format=html")
        response.raise_for_status()
        (OUT / "transformer-bilingual.html").write_text(response.text, encoding="utf-8")
        report["full_translation_export"] = {"passed": "[尚未翻译]" not in response.text and response.text.count('<section id=') == 526, "blocks": response.text.count('<section id=')}
        save()
    if "--local-only" in sys.argv:
        return
    # Live external tracker/repository checks in a separate database.
    from backend import store, database, discovery
    token = store.database_override.set(OUT / "discovery-test.sqlite3")
    database.initialize()
    class Context:
        def check(self): pass
        def log(self, *args): pass
    try:
        with store.connection() as c:
            c.execute("INSERT OR REPLACE INTO trackers(id,query,interval_hours) VALUES('live-check','ti:\"Attention Is All You Need\"',24)")
        first = await discovery.track(Context(), {"tracker_id": "live-check"})
        second = await discovery.track(Context(), {"tracker_id": "live-check"})
        report["live_tracker"] = {"first": first, "second": second, "passed": first["checked"] > 0 and not second["new_papers"]}
        papers = await discovery.search('id:1810.04805', limit=1)
        if papers and papers[0]["github"]:
            checked = await discovery.check_repositories(papers[0]["id"])
            report["live_repository"] = {"result": checked, "passed": any(c["status"] == "公开仓库可访问" for c in checked["code_checks"])}
        else:
            report["live_repository"] = {"passed": False, "reason": "Data source did not return a code link"}
    except Exception as exc:
        report["external_error"] = repr(exc)
    finally:
        store.database_override.reset(token)
        save()
    print(json.dumps({k: v.get("passed") for k,v in report.items() if isinstance(v,dict)}), flush=True)


asyncio.run(main())
