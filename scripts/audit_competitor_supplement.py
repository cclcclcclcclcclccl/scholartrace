import concurrent.futures
import json

from audit_competitor_sources import ROOT, fetch

SITES = [
    ("semantic-about", "Semantic Scholar About", "https://www.semanticscholar.org/about"),
    ("scholar-about", "Google Scholar About", "https://scholar.google.com/intl/en/scholar/about.html"),
    ("researchgate-about", "ResearchGate About", "https://www.researchgate.net/about"),
    ("researchgate-blog", "ResearchGate Blog", "https://www.researchgate.net/blog"),
    ("academia-about", "Academia About", "https://www.academia.edu/about"),
    ("scispace-legacy", "SciSpace product", "https://typeset.io/"),
    ("scispace-pricing", "SciSpace pricing", "https://scispace.com/pricing"),
    ("consensus-home", "Consensus product", "https://consensus.app/home/"),
    ("consensus-about", "Consensus About", "https://consensus.app/home/about-us/"),
    ("scite-product", "scite product", "https://scite.ai/"),
    ("scite-about", "scite About", "https://scite.ai/about"),
    ("notebooklm-product", "NotebookLM product", "https://notebooklm.google/"),
    ("notebooklm-help", "NotebookLM help", "https://support.google.com/notebooklm/answer/16206563?hl=en"),
    ("chatpdf-product", "ChatPDF product", "https://www.chatpdf.com/"),
    ("papers-product", "ReadCube Papers", "https://www.readcube.com/"),
    ("paperpal-product", "Paperpal product", "https://paperpal.com/features"),
    ("quillbot-about", "QuillBot About", "https://quillbot.com/about"),
    ("zotero-guide", "Zotero quick start", "https://www.zotero.org/support/quick_start_guide"),
    ("overleaf-features", "Overleaf features", "https://www.overleaf.com/about/features-overview"),
    ("similarweb-consensus", "Similarweb Consensus", "https://www.similarweb.com/website/consensus.app/"),
    ("similarweb-elicit", "Similarweb Elicit", "https://www.similarweb.com/website/elicit.com/"),
    ("similarweb-scholar", "Similarweb Google Scholar", "https://www.similarweb.com/website/scholar.google.com/"),
    ("semrush-consensus", "Semrush Consensus", "https://www.semrush.com/website/consensus.app/overview/"),
    ("semrush-elicit", "Semrush Elicit", "https://www.semrush.com/website/elicit.com/overview/"),
    ("semrush-scispace", "Semrush SciSpace", "https://www.semrush.com/website/scispace.com/overview/"),
]

if __name__ == "__main__":
    output = ROOT / "supplement.json"
    if output.exists():
        raise FileExistsError(output)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        for result in executor.map(fetch, SITES):
            results.append(result)
            print(json.dumps({k: result.get(k) for k in ["id", "status", "chars", "error", "metrics_candidates"]}, ensure_ascii=False), flush=True)
            output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf8")
