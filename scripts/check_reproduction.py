"""Start a second isolated HTTP app using the invoking Python environment."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/full-workbench/reproduction"
OUT.mkdir(parents=True, exist_ok=True)
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
code = """
from pathlib import Path
import sys
from backend import store,accounts,database
out=store.ROOT/'artifacts/full-workbench/reproduction'
store.DB_PATH=out/'library.sqlite3'
accounts.AUTH_PATH=out/'auth.sqlite3'
database.initialize()
store.import_pdf(store.ROOT/'data/competition/pdf/1706.03762v1.pdf')
import uvicorn
uvicorn.run('backend.app:app',host='127.0.0.1',port=int(sys.argv[1]))
"""
report = {"interpreter": sys.executable, "lock_sha256": hashlib.sha256((ROOT / "requirements-lock.txt").read_bytes()).hexdigest(), "models": "Existing local model files and inference service reused; independent Python install and database", "checks": []}
with (OUT / "server.log").open("w", encoding="utf-8") as log:
    process = subprocess.Popen([sys.executable, "-c", code, str(port)], cwd=ROOT, stdout=log, stderr=log,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=15, trust_env=False) as client:
            for _ in range(45):
                try:
                    response = client.get("/api/health")
                    response.raise_for_status()
                    break
                except httpx.HTTPError:
                    if process.poll() is not None:
                        raise RuntimeError("Independent application exited; see server.log")
                    time.sleep(1)
            else:
                raise RuntimeError("Independent application did not start")
            report["checks"].append("HTTP health responds from fresh Python environment")
            papers = client.get("/api/documents").json()
            assert len(papers) == 1 and papers[0]["pages"] == 15
            report["checks"].append("Isolated database contains one imported source PDF")
            assert client.get("/api/documents/"+papers[0]["id"]+"/pdf").content.startswith(b"%PDF")
            assert client.get("/").status_code == 200
            report["checks"].append("PDF and built frontend served over HTTP")
            assert client.get("/api/account/status").json()["account"] is None
            report["checks"].append("Separate authentication database initializes")
            report["passed"] = True
    except Exception as exc:
        report.update(passed=False, error=repr(exc))
    finally:
        process.terminate()
        process.wait(timeout=15)
(OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))
if not report["passed"]:
    raise SystemExit(1)
