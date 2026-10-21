"""Explicit identifier lookup and explainable seed-paper discovery (no generated facts)."""

import re
from collections import Counter
from urllib.parse import unquote, urlparse

import httpx

from . import discovery, store

STOP = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "their",
    "have",
    "using",
    "based",
    "towards",
    "through",
    "understanding",
    "learning",
    "models",
    "model",
    "neural",
    "networks",
    "network",
    "need",
    "all",
    "you",
    "are",
    "into",
    "via",
    "our",
    "has",
    "was",
    "were",
    "which",
    "than",
    "also",
    "these",
    "those",
    "can",
    "not",
    "more",
    "less",
    "both",
    "each",
    "most",
    "new",
    "show",
    "propose",
    "paper",
    "results",
    "result",
    "task",
    "tasks",
    "data",
    "method",
    "methods",
    "performance",
    "state-of-the-art",
    "over",
    "while",
    "such",
    "between",
    "well",
    "other",
    "after",
    "achieves",
    "existing",
    "best",
    "quality",
    "two",
    "three",
    "one",
    "first",
}


def terms(text):
    return {
        w.lower()
        for w in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}|[\u4e00-\u9fff]{2,}", text or "")
        if w.lower() not in STOP
    }


def identifier(value):
    value = unquote(value.strip())
    if value.startswith(("https://", "http://")):
        parsed = urlparse(value)
        if parsed.hostname in {"doi.org", "dx.doi.org", "www.doi.org"}:
            value = parsed.path.lstrip("/")
        elif parsed.hostname in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
            value = re.sub(r"^/(abs|pdf)/", "", parsed.path).removesuffix(".pdf")
        else:
            raise ValueError(
                "请提供 doi.org 或 arxiv.org 的论文链接，或直接填写 DOI / arXiv 编号"
            )
    value = re.sub(r"^(doi|arxiv):\s*", "", value, flags=re.IGNORECASE)
    if re.fullmatch(r"10\.\d{4,9}/\S+", value, re.IGNORECASE):
        return "crossref", "doi:" + value.lower()
    if re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?", value):
        return "arxiv", "id:" + value
    raise ValueError(
        "未识别论文编号。示例：1706.03762v7 或 10.1038/nature14539；标题请使用“论文标题”模式"
    )


def title_key(value):
    return re.sub(r"[^\w]", "", value or "").casefold()


def family(value):
    return re.sub(r"v\d+$", "", value or "")


def library_matches(paper, documents):
    result = []
    for d in documents:
        same_id = paper.get("arxiv_id") and family(paper["arxiv_id"]) == family(
            d.get("arxiv_id")
        )
        same_title = title_key(paper.get("title")) and title_key(
            paper.get("title")
        ) == title_key(d.get("title"))
        if same_id or same_title:
            remote_version = re.search(r"v(\d+)$", paper.get("arxiv_id") or "")
            result.append(
                {
                    "id": d["id"],
                    "title": d["title"],
                    "name": d.get("name", ""),
                    "version": d.get("version"),
                    "match": "arxiv_id" if same_id else "title",
                    "different_version": bool(
                        same_id
                        and remote_version
                        and d.get("version")
                        and int(remote_version[1]) != d["version"]
                    ),
                }
            )
    return result


def annotate(papers):
    documents = store.list_documents()
    return [{**p, "library_matches": library_matches(p, documents)} for p in papers]


async def lookup(query, mode="topic", **kwargs):
    query = query.strip()
    if not query:
        raise ValueError("请输入检索内容")
    if mode == "identifier":
        source, query = identifier(query)
        kwargs.update(
            source=source, start=0, latest=False, year_from=None, year_to=None
        )
    elif mode == "title" and kwargs.get("source", "arxiv") == "arxiv":
        query = 'ti:"' + query.replace('"', " ") + '"'
    elif mode == "title":
        query = "title:" + query
    papers = await discovery.search_cached(query, **kwargs)
    return annotate(papers)


def context_terms(seed, document_id):
    abstract = seed.get("abstract") or seed.get("metadata", {}).get(
        "remote_paper", {}
    ).get("abstract", "")
    origin = "种子摘要元数据" if abstract else "仅标题"
    if not abstract and document_id:
        first_page = "\n".join(b["text"] for b in store.get_blocks(document_id, 1))
        match = re.search(
            r"\bAbstract\b(.*?)(?:\bIntroduction\b|$)",
            first_page,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            abstract, origin = match[1][:5000], "第一页 Abstract 后文本（解析候选）"
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", abstract[:5000].lower())
    allowed = terms(abstract) - terms(seed["title"])
    counts = Counter(w for w in words if w in allowed)
    return [w for w, count in counts.most_common(3) if count >= 2], origin


async def related(
    document_id=None, paper_id=None, online=False, source="crossref", force=False
):
    if bool(document_id) == bool(paper_id):
        raise ValueError("请选择一篇种子论文")
    seed = (
        store.get_document(document_id) if document_id else discovery.remote(paper_id)
    )
    if seed.get("archived"):
        raise ValueError("请先恢复已归档的论文")
    keywords = terms(seed["title"])
    if not keywords:
        raise ValueError("标题缺少可用主题词，请使用主题检索")
    context, context_origin = context_terms(seed, document_id)
    keywords |= set(context)
    documents = store.list_documents()
    local = []
    for d in documents:
        if (
            d["id"] == document_id
            or (
                seed.get("arxiv_id")
                and family(seed["arxiv_id"]) == family(d.get("arxiv_id"))
            )
            or title_key(seed["title"]) == title_key(d["title"])
        ):
            continue
        shared = sorted(keywords & terms(d["title"]))
        if not shared:
            continue
        score = len(shared) / len(keywords | terms(d["title"]))
        local.append(
            {
                **d,
                "shared_terms": shared,
                "related_score": round(score, 4),
                "reason": "与种子标题 / 摘要主题共同词：" + "、".join(shared),
            }
        )
    local.sort(key=lambda p: (-p["related_score"], p["title"]))
    # Use seed title order, not set iteration order, for stable provider queries.
    ordered = list(
        dict.fromkeys(
            w.lower()
            for w in re.findall(
                r"[A-Za-z][A-Za-z0-9-]{2,}|[\u4e00-\u9fff]{2,}", seed["title"]
            )
            if w.lower() in keywords
        )
    )[:6]
    ordered = list(dict.fromkeys(ordered[:3] + context))[:6]
    query = (
        " AND ".join("all:" + w for w in ordered[:3])
        if source == "arxiv"
        else " ".join(ordered)
    )
    papers, warnings = [], []
    if online:
        try:
            candidates = await discovery.search_cached(
                query, source=source, force=force
            )
            for p in candidates:
                # Crossref indexes individual figures/tables as components too.
                if p.get("record_type") == "component" or re.match(
                    r"^(?:Figure|Table)\s+\d+\s*[:.]", p["title"], re.IGNORECASE
                ):
                    continue
                if title_key(p["title"]) == title_key(seed["title"]) or (
                    seed.get("arxiv_id")
                    and family(seed["arxiv_id"]) == family(p.get("arxiv_id"))
                ):
                    continue
                shared = sorted(
                    keywords & terms(p["title"] + " " + p.get("abstract", ""))
                )
                if len(shared) < (2 if len(keywords) >= 2 else 1):
                    continue
                papers.append(
                    {
                        **p,
                        "shared_terms": shared,
                        "reason": ("标题或摘要共同词：" + "、".join(shared))
                        if shared
                        else "数据源按种子主题召回，未找到相同词；请核对相关性",
                    }
                )
            papers = annotate(papers)
            if candidates and not papers:
                warnings.append(
                    "在线候选未通过共同主题词初筛，未作为相关论文展示。可调整研究主题再检索；没有结果不代表不存在相关工作。"
                )
        except (httpx.HTTPError, ValueError) as exc:
            warnings.append(
                "在线扩展暂不可用，本地结果已保留。请稍后重试或切换数据源。"
                + (
                    " HTTP " + str(exc.response.status_code)
                    if isinstance(exc, httpx.HTTPStatusError)
                    else ""
                )
            )
    return {
        "seed": {"id": seed["id"], "title": seed["title"]},
        "local": local[:12],
        "papers": papers,
        "query": query,
        "context_terms": context,
        "context_origin": context_origin,
        "source": source,
        "online_requested": online,
        "warnings": warnings,
        "method": "按种子标题与可用摘要上下文提取主题词；库内按共同词比例排序，在线候选经过共同词初筛后沿用数据源排名。不是语义向量推荐，也不代表引用关系、研究质量或结论支持。",
    }
