"""Refresh the previously identified public product pages without accounts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
import json
import re
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/moheng-final-20261021/competitors'
OUT.mkdir(parents=True, exist_ok=True)
class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden, self.parts = 0, []
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.hidden = max(0, self.hidden-1)
    def handle_data(self, data):
        if not self.hidden and data.strip(): self.parts.append(data.strip())
source = (ROOT / 'docs/第二轮竞品对比与搜索推荐改进_2026-10-14.md').read_text('utf-8').split('## 7. 全量平台目录', 1)[1]
urls = re.findall(r'\| \[([^]]+)\]\((https://[^)]+)\)', source)
urls += [('Semantic Reader', 'https://www.semanticscholar.org/product/semantic-reader')]
def fetch(item):
    name, url = item
    report = {'name':name, 'url':url, 'checked_at':datetime.now().astimezone().isoformat(), 'access':'anonymous public page'}
    slug = re.sub(r'[^\w-]', '_', name)
    try:
        with urlopen(Request(url, headers={'User-Agent':'Mozilla/5.0'}), timeout=25) as r:
            content = r.read(4_000_000).decode('utf-8', errors='replace')
            report.update(status=r.status, final_url=r.url)
        parser = Text(); parser.feed(content)
        text = '\n'.join(parser.parts)
        (OUT / (slug+'.txt')).write_text(text, encoding='utf-8')
        report.update(text_chars=len(text), text_file=slug+'.txt', excerpt=text[:250])
    except Exception as exc: report.update(error=str(exc), text_chars=0)
    return report
with ThreadPoolExecutor(max_workers=10) as pool: results = sorted(pool.map(fetch, urls), key=lambda r:r['name'])
(OUT / 'sources.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'pages':len(results), 'http_200':sum(r.get('status')==200 for r in results), 'failures':sum('error' in r for r in results), 'notice':'HTTP success is not feature validation; no updated traffic claims.'}, ensure_ascii=False))
