"""Read public product pages and preserve dated research evidence (no login)."""

import concurrent.futures
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import httpx

ROOT = Path("artifacts/competitor-audit-2026-10-13")
SITES = [
    ("google-scholar", "Google Scholar", "https://scholar.google.com/"),
    ("semantic-scholar", "Semantic Scholar", "https://www.semanticscholar.org/"),
    ("researchgate", "ResearchGate", "https://www.researchgate.net/"),
    ("academia", "Academia.edu", "https://www.academia.edu/"),
    ("aminer", "AMiner", "https://www.aminer.cn/"),
    ("cnki", "中国知网", "https://www.cnki.net/"),
    ("scispace", "SciSpace", "https://scispace.com/"),
    ("elicit", "Elicit", "https://elicit.com/"),
    ("consensus", "Consensus", "https://consensus.app/"),
    ("scite", "scite", "https://scite.ai/"),
    ("notebooklm", "NotebookLM", "https://notebooklm.google/"),
    ("chatpdf", "ChatPDF", "https://www.chatpdf.com/"),
    ("humata", "Humata", "https://www.humata.ai/"),
    ("scholarcy", "Scholarcy", "https://www.scholarcy.com/"),
    ("explainpaper", "Explainpaper", "https://www.explainpaper.com/"),
    ("openread", "OpenRead", "https://www.openread.academy/"),
    ("scisummary", "SciSummary", "https://scisummary.com/"),
    ("undermind", "Undermind", "https://www.undermind.ai/"),
    ("iris", "Iris.ai", "https://iris.ai/"),
    ("researchrabbit", "ResearchRabbit", "https://www.researchrabbit.ai/"),
    ("connectedpapers", "Connected Papers", "https://www.connectedpapers.com/"),
    ("litmaps", "Litmaps", "https://www.litmaps.com/"),
    ("zotero", "Zotero", "https://www.zotero.org/"),
    ("mendeley", "Mendeley", "https://www.mendeley.com/"),
    ("endnote", "EndNote", "https://endnote.com/"),
    ("papers", "Papers", "https://www.papersapp.com/"),
    ("paperpile", "Paperpile", "https://paperpile.com/"),
    ("overleaf", "Overleaf", "https://www.overleaf.com/"),
    ("paperpal", "Paperpal", "https://paperpal.com/"),
    ("writefull", "Writefull", "https://www.writefull.com/"),
    ("jenni", "Jenni", "https://jenni.ai/"),
    ("quillbot", "QuillBot", "https://quillbot.com/"),
    ("grammarly", "Grammarly", "https://www.grammarly.com/"),
    ("biorender", "BioRender", "https://www.biorender.com/"),
    ("napkin", "Napkin", "https://www.napkin.ai/"),
    ("drawio", "draw.io", "https://www.drawio.com/"),
    ("xiaolujing", "小绿鲸", "https://www.xljsci.com/"),
    ("cnki-study", "知网研学", "https://x.cnki.net/"),
    ("metaso", "秘塔AI搜索", "https://metaso.cn/"),
    ("ima", "腾讯 ima", "https://ima.qq.com/"),
]


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip += 1
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "meta" and attrs.get("name") == "description":
            self.parts.append(attrs.get("content", ""))
        if tag in {"p", "h1", "h2", "h3", "li", "div", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def fetch(site):
    key, name, url = site
    item = {"id": key, "name": name, "requested_url": url, "fetched_at": datetime.now(timezone.utc).isoformat()}
    try:
        response = httpx.get(url, follow_redirects=True, timeout=25, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36"})
        item.update(status=response.status_code, url=str(response.url))
        parser = TextParser()
        parser.feed(response.text)
        lines = [re.sub(r"\s+", " ", line).strip() for line in " ".join(parser.parts).split("\n")]
        content = "\n".join(line for line in lines if line)
        (ROOT / f"{key}.txt").write_text(content, encoding="utf8")
        item["text_file"] = f"{key}.txt"
        item["chars"] = len(content)
        item["metrics_candidates"] = [line[:900] for line in lines if re.search(r"million|billion|\d[,.\d]*[MK]\+?|万|亿|researchers|users|scientists|research papers", line, re.I)][:25]
        item["relevant_links"] = list(dict.fromkeys(link for link in parser.links if re.search(r"about|feature|product|guide|pricing|help|blog|press", link, re.I)))[:45]
    except Exception as exc:
        item["error"] = f"{type(exc).__name__}: {exc}"
    return item


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    target = ROOT / "sources.json"
    if target.exists():
        raise FileExistsError("Preserve the first evidence snapshot")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        for result in executor.map(fetch, SITES):
            results.append(result)
            print(json.dumps({k: result.get(k) for k in ["id", "status", "chars", "error", "metrics_candidates"]}, ensure_ascii=False), flush=True)
            target.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf8")
