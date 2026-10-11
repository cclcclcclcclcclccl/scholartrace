"""Small development smoke set. This is not a held-out accuracy benchmark."""
import json
from pathlib import Path
from time import perf_counter
import httpx

ROOT = Path(__file__).resolve().parents[1]
client = httpx.Client(base_url="http://127.0.0.1:8765", timeout=150, trust_env=False)
docs = client.get("/api/documents").json()
first = next(d for d in docs if d["name"] == "1706.03762v1.pdf")
scan = next(d for d in docs if d["name"] == "1706.03762v1_img.pdf")
newer = next(d for d in docs if d["name"] == "1706.03762v7.pdf")
cases = [("gpu", first, "训练用了哪些 GPU？"),
         ("optimizer", first, "Adam optimizer 的 beta1 和 beta2 分别是多少？"),
         ("unanswerable", first, "每张 NVIDIA P100 GPU 的采购价格是多少美元？"),
         ("scan_gpu", scan, "训练用了哪些 GPU？")]
results = []
for label, doc, question in cases:
    start = perf_counter()
    response = client.post("/api/ask", json={"question": question, "document_ids": [doc["id"]]})
    response.raise_for_status()
    result = {"case": label, "document": doc["name"], "question": question,
              "seconds": round(perf_counter()-start,2), "response": response.json()}
    results.append(result)
    print(json.dumps({"case":label,"seconds":result["seconds"],"mode":result["response"]["mode"],"claims":result["response"]["model_answer"]},ensure_ascii=False),flush=True)
    (ROOT/"artifacts/inspection/local-model-smoke.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")

# A real version change: v1 promises code soon; v7 provides a repository URL.
evidence = client.post("/api/search",json={"question":"code available","document_ids":[first["id"]]}).json()["evidence"]
source = next(b for b in evidence if "We intend to make the code" in b["text"])
existing = client.get("/api/notes").json()
if not any(n["block_id"]==source["id"] and "版本复核样例" in n["note"] for n in existing):
    client.post("/api/notes",json={"block_id":source["id"],"note":"版本复核样例：旧版声明代码将于近期公开"}).raise_for_status()
audit = client.post("/api/versions/audit",json={"target_document_id":newer["id"]}).json()
(ROOT/"artifacts/inspection/real-version-audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
print("Real version audit", [(r["note"]["note"],r["status"],r["similarity"]) for r in audit["results"]],flush=True)
