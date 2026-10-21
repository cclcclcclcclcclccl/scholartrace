import concurrent.futures
import json

from audit_competitor_sources import ROOT, fetch

DOMAINS = [
    "scholar.google.com", "semanticscholar.org", "researchgate.net", "academia.edu",
    "zotero.org", "mendeley.com", "overleaf.com", "chatpdf.com", "scite.ai",
    "researchrabbit.ai", "litmaps.com", "connectedpapers.com", "jenni.ai",
    "biorender.com", "notebooklm.google.com", "quillbot.com", "paperpal.com",
    "paperpile.com", "xljsci.com", "metaso.cn", "aminer.cn", "ima.qq.com",
]

if __name__ == "__main__":
    target = ROOT / "traffic.json"
    if target.exists():
        raise FileExistsError(target)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        sites = [("traffic-" + d.replace(".", "-"), d, "https://www.semrush.com/website/" + d + "/overview/") for d in DOMAINS]
        for item in executor.map(fetch, sites):
            results.append(item)
            candidates = [s for s in item.get("metrics_candidates", []) if "received" in s or "ranked" in s]
            print(json.dumps({"id": item["id"], "status": item.get("status"), "error": item.get("error"), "traffic": candidates[:2]}, ensure_ascii=False), flush=True)
            target.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf8")
