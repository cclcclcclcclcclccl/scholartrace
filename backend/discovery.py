"""Real scholarly metadata, allowlisted PDF retrieval, incremental trackers."""

import asyncio
import datetime as dt
import json
import hashlib
import re
import uuid
from collections import Counter
from urllib.parse import quote, urlparse
import httpx
from defusedxml import ElementTree as ET
from . import database, jobs, store

NS = {"a": "http://www.w3.org/2005/Atom", "ar": "http://arxiv.org/schemas/atom"}
HEADERS = {"User-Agent": "ScholarTrace/0.2 (local academic research assistant)"}
arxiv_gate = asyncio.Lock()
last_arxiv = 0.0


def persist(papers):
    with store.connection() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO remote_papers(id,data) VALUES(?,?)",
            [(p["id"], json.dumps(p, ensure_ascii=False)) for p in papers],
        )
    return papers


def feedback_scores():
    with store.connection() as conn:
        return {r[0]: r[1] for r in conn.execute("SELECT paper_id,vote FROM feedback")}


async def search(
    query, source="arxiv", limit=12, latest=False, start=0, year_from=None, year_to=None
):
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 500:
        raise ValueError("搜索词须为 1—500 字符")
    if year_from and year_to and year_from > year_to:
        raise ValueError("起始年份不能晚于结束年份")
    start = max(0, min(int(start), 9900))
    limit = max(1, min(int(limit), 100))
    papers = []
    async with httpx.AsyncClient(
        timeout=40, headers=HEADERS, follow_redirects=False
    ) as client:
        if source == "arxiv":
            global last_arxiv
            async with arxiv_gate:
                delay = 3 - (asyncio.get_running_loop().time() - last_arxiv)
                if delay > 0:
                    await asyncio.sleep(delay)
                params = {
                    "search_query": query
                    if re.search(r"\b(?:all|ti|au|cat|abs|id):", query)
                    else "all:" + query,
                    "max_results": limit,
                    "start": start,
                    "sortBy": "lastUpdatedDate" if latest else "relevance",
                    "sortOrder": "descending",
                }
                if year_from or year_to:
                    params["search_query"] = (
                        "("
                        + params["search_query"]
                        + f") AND submittedDate:[{year_from or 1900}01010000 TO {year_to or dt.datetime.now().year}12312359]"
                    )
                exact_id = re.fullmatch(r"id:((?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?)", query)
                if exact_id:
                    params = {"id_list": exact_id[1], "max_results": 1}
                for attempt in range(3):
                    response = await client.get(
                        "https://export.arxiv.org/api/query", params=params
                    )
                    last_arxiv = asyncio.get_running_loop().time()
                    if response.status_code not in {429, 502, 503, 504}:
                        break
                    if attempt < 2:
                        try:
                            delay = min(
                                45,
                                max(
                                    6 * (attempt + 1),
                                    int(response.headers.get("retry-after", "0")),
                                ),
                            )
                        except ValueError:
                            delay = 6 * (attempt + 1)
                        await asyncio.sleep(delay)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            for entry in root.findall("a:entry", NS):

                def value(name):
                    return store.normalize(entry.findtext(name, "", NS))

                link = value("a:id")
                identifier = re.sub(r"^https?://[^/]+/abs/", "", link)
                if not re.fullmatch(
                    r"(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?", identifier
                ):
                    continue
                abstract = value("a:summary")
                papers.append(
                    {
                        "id": "arxiv:" + identifier,
                        "title": value("a:title"),
                        "abstract": abstract,
                        "authors": [
                            a.findtext("a:name", "", NS)
                            for a in entry.findall("a:author", NS)
                        ],
                        "published": value("a:published"),
                        "updated": value("a:updated"),
                        "url": "https://arxiv.org/abs/" + identifier,
                        "pdf_url": "https://arxiv.org/pdf/" + identifier,
                        "source": "arXiv",
                        "arxiv_id": identifier,
                        "github": [
                            link.rstrip(".")
                            for link in re.findall(
                                r"https://github\.com/[\w.-]+/[\w.-]+", abstract
                            )
                        ],
                    }
                )
        elif source == "crossref":
            params = {"query.title" if query.startswith("title:") else "query.bibliographic": query[6:] if query.startswith("title:") else query, "rows": limit, "offset": start}
            filters = []
            if year_from:
                filters.append(f"from-pub-date:{year_from}-01-01")
            if year_to:
                filters.append(f"until-pub-date:{year_to}-12-31")
            if filters:
                params["filter"] = ",".join(filters)
            if latest:
                params.update(sort="published", order="desc")
            exact_doi = query.startswith("doi:")
            response = await client.get(
                "https://api.crossref.org/works/" + quote(query[4:], safe="")
                if exact_doi else "https://api.crossref.org/works",
                params={} if exact_doi else params,
            )
            if exact_doi and response.status_code == 404:
                return []
            response.raise_for_status()
            message = response.json()["message"]
            for item in ([message] if exact_doi else message["items"]):
                doi = item.get("DOI", "")
                parts = item.get("published", {}).get("date-parts", [[]])[0]
                papers.append(
                    {
                        "id": "doi:" + doi,
                        "title": " ".join(item.get("title", [])),
                        "abstract": re.sub("<[^>]+>", "", item.get("abstract", "")),
                        "authors": [
                            " ".join([a.get("given", ""), a.get("family", "")]).strip()
                            for a in item.get("author", [])
                        ],
                        "published": "-".join(str(v) for v in parts),
                        "updated": None,
                        "url": "https://doi.org/" + doi,
                        "pdf_url": None,
                        "source": "Crossref",
                        "record_type": item.get("type", "unknown"),
                        "doi": doi,
                        "github": [],
                    }
                )
        else:
            raise ValueError("数据源须为 arxiv 或 crossref")
    votes = feedback_scores()
    for rank, p in enumerate(papers):
        p["provider_rank"] = rank
        p["vote"] = votes.get(p["id"], 0)
    # Stable provider ranking within each preference group; no invented relevance score.
    papers.sort(key=lambda p: p["vote"], reverse=True)
    return persist(papers)


async def search_cached(
    query,
    source="arxiv",
    *,
    latest=False,
    start=0,
    year_from=None,
    year_to=None,
    force=False,
):
    """Account-local query cache for interactive search only; trackers always fetch live."""
    args = dict(
        query=query.strip(),
        source=source,
        latest=latest,
        start=start,
        year_from=year_from,
        year_to=year_to,
    )
    key = (
        "discovery_cache:"
        + hashlib.sha256(json.dumps({"schema": 3, **args}, sort_keys=True).encode()).hexdigest()
    )
    cached = database.preference(key, None)
    now = dt.datetime.now(dt.timezone.utc)
    status = "live"
    if cached and not force and (now - timestamp(cached["at"])).total_seconds() < 600:
        papers, status = cached["papers"], "cache"
    else:
        try:
            papers = await search(**args)
            cached = {"at": now.isoformat(), "papers": papers}
            database.set_preference(key, cached)
        except httpx.HTTPError:
            if not cached or not cached["papers"]:
                raise
            papers, status = cached["papers"], "stale_after_error"
    votes = feedback_scores()
    ranked = [
        {
            **p,
            "vote": votes.get(p["id"], 0),
            "retrieval_status": status,
            "retrieved_at": cached["at"],
        }
        for p in papers
    ]
    ranked.sort(key=lambda p: (-p["vote"], p.get("provider_rank", len(ranked))))
    return ranked


def remote(identifier):
    with store.connection() as conn:
        row = conn.execute(
            "SELECT data FROM remote_papers WHERE id=?", (identifier,)
        ).fetchone()
    if not row:
        raise ValueError("请先搜索并选择真实论文记录")
    return json.loads(row[0])


async def check_repositories(identifier):
    paper = remote(identifier)
    checked = []
    async with httpx.AsyncClient(
        timeout=20, headers=HEADERS, follow_redirects=False
    ) as client:
        for url in paper.get("github", [])[:5]:
            match = re.fullmatch(r"https://github\.com/([\w.-]+)/([\w.-]+)", url)
            if not match:
                continue
            owner, repo = match.groups()
            repo = repo.rstrip(".").removesuffix(".git")
            url = f"https://github.com/{owner}/{repo}"
            result = {
                "url": url,
                "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "reproduction": "未复现实验",
            }
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}"
                )
                if response.status_code == 200:
                    data = response.json()
                    result.update(
                        status="公开仓库可访问",
                        archived=bool(data.get("archived")),
                        license=(data.get("license") or {}).get("spdx_id") or "未声明",
                        default_branch=data.get("default_branch"),
                    )
                elif response.status_code == 404:
                    result["status"] = "未找到公开仓库（可能为私有或已移除）"
                elif response.is_redirect:
                    result["status"] = "仓库地址已迁移，请打开来源链接核对"
                else:
                    result["status"] = f"暂无法核验（HTTP {response.status_code}）"
            except httpx.HTTPError:
                result["status"] = "网络请求失败，可稍后重新核验"
            checked.append(result)
    paper["code_checks"] = checked
    paper["github"] = [c["url"] for c in checked]
    persist([paper])
    return paper


def timestamp(value):
    if not value:
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        dt.timezone.utc
    )


async def recommend():
    with store.connection() as conn:
        liked = [
            json.loads(r[0])
            for r in conn.execute(
                "SELECT p.data FROM remote_papers p JOIN feedback f ON f.paper_id=p.id WHERE f.vote=1"
            )
        ]
    titles = [p["title"] for p in liked] or [p["title"] for p in store.list_documents()]
    stop = {
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
    }
    words = Counter(
        w.lower()
        for title in titles
        for w in re.findall(r"[A-Za-z]{4,}", title)
        if w.lower() not in stop
    )
    terms = [w for w, _ in words.most_common(3)]
    if not terms:
        raise ValueError("先导入论文或为搜索结果点赞，以建立推荐主题")
    query = " AND ".join("all:" + word for word in terms)
    papers = await search(query, "arxiv", 12)
    return {
        "papers": papers,
        "query": query,
        "reason": ("根据已点赞论文" if liked else "根据当前文献库")
        + "标题中的高频主题词："
        + ", ".join(terms)
        + "。相同结果结合点赞/踩排序。",
    }


def safe_pdf_url(url):
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"arxiv.org", "export.arxiv.org", "www.arxiv.org"}
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ValueError("下载地址不在允许的 arXiv 全文来源内")
    if not parsed.path.startswith("/pdf/"):
        raise ValueError("下载地址不是 PDF 链接")
    return url


@jobs.register("download")
async def download(ctx, payload):
    paper = remote(payload["paper_id"])
    url = paper.get("pdf_url")
    if not url:
        raise ValueError("该记录未提供可下载的开放全文，请从来源页取得合法 PDF 后导入")
    folder = store.ROOT / "data/uploads"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (uuid.uuid4().hex + ".pdf")
    try:
        async with httpx.AsyncClient(
            timeout=90, headers=HEADERS, follow_redirects=False
        ) as client:
            for attempt in range(5):
                safe_pdf_url(url)
                async with client.stream("GET", url) as response:
                    if response.is_redirect:
                        from urllib.parse import urljoin

                        url = urljoin(url, response.headers["location"])
                        continue
                    response.raise_for_status()
                    total = 0
                    with path.open("wb") as output:
                        async for chunk in response.aiter_bytes(262144):
                            ctx.check()
                            total += len(chunk)
                            if total > 80 * 1024 * 1024:
                                raise ValueError("PDF 超过 80 MB 上限")
                            output.write(chunk)
                    break
            else:
                raise ValueError("下载重定向次数过多")
        with path.open("rb") as stream:
            if b"%PDF-" not in stream.read(1024):
                raise ValueError("来源未返回有效 PDF，可能暂时限流")
        ctx.progress(0.8, "全文已下载，正在解析入库")
        record = await asyncio.to_thread(
            store.import_pdf, path, paper["title"][:100] + ".pdf"
        )
        if record.get("already_exists"):
            path.unlink(missing_ok=True)
        with store.connection() as conn:
            meta = store.get_document(record["id"])["metadata"]
            meta["download_source"] = url
            meta["remote_paper"] = paper
            conn.execute(
                "UPDATE documents SET metadata=? WHERE id=?",
                (json.dumps(meta, ensure_ascii=False), record["id"]),
            )
        if not record.get("already_exists") and meta.get("pages_without_text"):
            jobs.submit("ocr", {"document_id": record["id"]})
        else:
            jobs.submit("index", {"document_ids": [record["id"]]})
        record.pop("path", None)
        return record
    except BaseException:
        # Do not remove an original PDF after it has successfully entered the library.
        with store.connection() as conn:
            owned = conn.execute(
                "SELECT 1 FROM documents WHERE path=?", (str(path.resolve()),)
            ).fetchone()
        if not owned:
            path.unlink(missing_ok=True)
        raise


def trackers():
    with store.connection() as conn:
        result = [
            dict(r) for r in conn.execute("SELECT * FROM trackers ORDER BY rowid DESC")
        ]
        for tracker in result:
            tracker["papers"] = [
                json.loads(r[0])
                for r in conn.execute(
                    "SELECT p.data FROM tracker_hits h JOIN remote_papers p ON p.id=h.paper_id WHERE h.tracker_id=? ORDER BY p.fetched_at DESC LIMIT 60",
                    (tracker["id"],),
                )
            ]
    return result


@jobs.register("track")
async def track(ctx, payload):
    with store.connection() as conn:
        row = conn.execute(
            "SELECT * FROM trackers WHERE id=?", (payload["tracker_id"],)
        ).fetchone()
    if not row:
        raise ValueError("追踪主题不存在")
    ctx.log(
        "检索 arXiv 最新更新",
        {"query": row["query"], "previous_cursor": row["last_checked"]},
    )
    try:
        papers = []
        cursor = row["last_checked"]
        started_at = dt.datetime.now(dt.timezone.utc)
        # Overlap absorbs provider indexing delay; saved IDs deduplicate repeated hits.
        boundary = timestamp(cursor) - dt.timedelta(hours=24) if cursor else None
        initial = not cursor
        for start in range(0, 2000, 100):
            ctx.check()
            batch = await search(
                row["query"], "arxiv", 30 if initial else 100, latest=True, start=start
            )
            papers.extend(
                p
                for p in batch
                if not boundary
                or timestamp(p.get("updated") or p["published"]) >= boundary
            )
            if (
                initial
                or len(batch) < 100
                or any(
                    timestamp(p.get("updated") or p["published"]) < boundary
                    for p in batch
                )
            ):
                break
            ctx.log(
                "继续翻页检查增量",
                {"offset": start + 100, "new_candidates": len(papers)},
            )
        else:
            raise ValueError(
                "本轮更新超过 2000 条，已保留检索缓存但未推进游标；请缩小追踪主题后重试"
            )
        now = dt.datetime.now(dt.timezone.utc)
        next_check = (now + dt.timedelta(hours=row["interval_hours"])).isoformat()
        with store.connection() as conn:
            previous = {
                r[0]
                for r in conn.execute(
                    "SELECT paper_id FROM tracker_hits WHERE tracker_id=?", (row["id"],)
                )
            }
            conn.executemany(
                "INSERT OR IGNORE INTO tracker_hits VALUES(?,?)",
                [(row["id"], p["id"]) for p in papers],
            )
            conn.execute(
                "UPDATE trackers SET last_checked=?,next_check=?,error=NULL WHERE id=?",
                (started_at.isoformat(), next_check, row["id"]),
            )
        return {
            "new_papers": [p for p in papers if p["id"] not in previous],
            "checked": len(papers),
            "cursor": started_at.isoformat(),
            "scope": "首次收集最新 30 条；后续按更新时间逐页回溯到上次检查前 24 小时并去重。单次最多 2000 条，超限不推进游标；数据源延迟超过回溯窗口时可能漏收。",
        }
    except Exception as exc:
        with store.connection() as conn:
            conn.execute(
                "UPDATE trackers SET error=?,next_check=? WHERE id=?",
                (
                    str(exc)[:500],
                    (
                        dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=15)
                    ).isoformat(),
                    row["id"],
                ),
            )
        raise


async def scheduler():
    while True:
        await asyncio.sleep(30)
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        with store.connection() as conn:
            rows = list(
                conn.execute(
                    "SELECT id FROM trackers WHERE enabled=1 AND (next_check IS NULL OR next_check<=?)",
                    (now,),
                )
            )
            running = {
                json.loads(r[0]).get("tracker_id")
                for r in conn.execute(
                    "SELECT payload FROM jobs WHERE kind='track' AND state IN ('queued','running','interrupted')"
                )
            }
        for row in rows:
            if row[0] not in running:
                jobs.submit("track", {"tracker_id": row[0]})
