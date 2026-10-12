"""Validated API for full research workflows, exports and durable task events."""

import asyncio
import io
import json
import re
import uuid
import zipfile
from typing import Literal

import pymupdf
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from . import (
    agent,
    audit,
    charts,
    database,
    diagrams,
    discovery,
    formula,
    impact,
    jobs,
    parsing,
    research,
    retrieval,
    store,
    tables,
    translation,
)

router = APIRouter(prefix="/api")


class NoteEdit(BaseModel):
    note: str | None = Field(default=None, min_length=1, max_length=1000)
    archived: bool | None = None


@router.patch("/notes/{identifier}")
def edit_note(identifier: int, body: NoteEdit):
    with store.connection() as c:
        previous = c.execute(
            "SELECT * FROM evidence_notes WHERE id=?", (identifier,)
        ).fetchone()
        if not previous:
            raise KeyError(identifier)
        if body.note is not None:
            if not body.note.strip():
                raise ValueError("笔记不能为空")
            c.execute(
                "INSERT INTO note_history(note_id,previous_text) VALUES(?,?)",
                (identifier, previous["note"]),
            )
            c.execute(
                "UPDATE evidence_notes SET note=? WHERE id=?",
                (body.note.strip(), identifier),
            )
        if body.archived is not None:
            c.execute(
                "UPDATE evidence_notes SET archived=? WHERE id=?",
                (int(body.archived), identifier),
            )
    return {"ok": True}


@router.get("/notes-archive")
def archived_notes():
    return audit.notes(True)


@router.get("/notes-export")
def export_notes(format: Literal["md", "json"] = "md"):
    notes = audit.notes()
    text = (
        json.dumps(notes, ensure_ascii=False, indent=2)
        if format == "json"
        else "# 证据笔记\n\n"
        + "\n\n".join(
            f"## {n['note']}\n\n{n['title']} · v{n['version'] or '?'} · PDF 第 {n['page']} 页\n\n> "
            + n["quote"].replace("\n", "\n> ")
            + f"\n\nSource: {n['document_id']} / {n['block_id']}"
            for n in notes
        )
    )
    return Response(
        text,
        media_type="application/json" if format == "json" else "text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="evidence-notes.{format}"'
        },
    )


class TaskPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str | None = None
    document_ids: list[str] = Field(default_factory=list, max_length=40)
    topic: str = Field(default="", max_length=1800)
    goal: str = Field(default="", max_length=1800)
    query: str = Field(default="", max_length=500)
    language: Literal["zh", "en"] = "zh"
    page: int | None = Field(default=None, ge=1)
    artifact_id: str | None = None
    paper_id: str | None = None
    tracker_id: str | None = None
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    fields: list[str] = Field(default_factory=list, max_length=6)


class TaskRequest(BaseModel):
    kind: Literal[
        "parse",
        "ocr",
        "index",
        "translate",
        "download",
        "track",
        "review",
        "writing",
        "future",
        "agent",
        "impact",
        "diagram",
        "formula",
        "table",
        "matrix",
        "refine_plan",
    ]
    payload: TaskPayload


@router.post("/jobs")
async def create_job(body: TaskRequest):
    payload = body.payload.model_dump(exclude_none=True)
    if body.kind == "refine_plan":
        if (
            not payload.get("artifact_id")
            or research.artifact(payload["artifact_id"])["kind"] != "writing"
        ):
            raise ValueError("请选择一份研究方案")
    if body.kind == "matrix" and (
        not 1 <= len(payload["document_ids"]) <= 6
        or not payload["fields"]
        or any(not f.strip() or len(f) > 180 for f in payload["fields"])
    ):
        raise ValueError("请选择 1—6 篇文献并填写 1—6 个核对问题，每题最多 180 字")
    if body.kind in {
        "parse",
        "ocr",
        "translate",
        "future",
        "impact",
        "formula",
        "table",
    } and not payload.get("document_id"):
        raise ValueError("请选择一篇文献")
    if body.kind in {"review", "writing", "diagram"} and not payload["topic"].strip():
        raise ValueError("请填写研究主题")
    if body.kind == "agent" and not payload["goal"].strip():
        raise ValueError("请填写研究目标")
    if body.kind == "formula":
        formula.area_for(
            store.get_document(payload["document_id"]),
            payload.get("page", 1),
            payload.get("bbox", []),
        )
    if body.kind == "table":
        tables.area_for(
            store.get_document(payload["document_id"]),
            payload.get("page", 1),
            payload.get("bbox", []),
        )
    if body.kind == "download" and not payload.get("paper_id"):
        raise ValueError("请选择检索结果")
    if body.kind == "track" and not payload.get("tracker_id"):
        raise ValueError("请选择追踪主题")
    for identifier in payload["document_ids"] + (
        [payload["document_id"]] if payload.get("document_id") else []
    ):
        store.get_document(identifier)
    # Repeated clicks reuse an identical in-flight task.
    for job in jobs.listing():
        if (
            job["kind"] == body.kind
            and job["payload"] == payload
            and job["state"] in {"queued", "running", "interrupted"}
        ):
            return job
    return jobs.submit(body.kind, payload)


@router.get("/jobs")
def tasks():
    return jobs.listing()


@router.get("/jobs/{identifier}")
def task(identifier: str):
    return jobs.get(identifier)


@router.post("/jobs/{identifier}/cancel")
def cancel(identifier: str):
    current = jobs.get(identifier)
    if current["state"] in {"completed", "failed", "cancelled"}:
        return current
    with store.connection() as c:
        c.execute(
            "UPDATE jobs SET cancel_requested=1,message=? WHERE id=?",
            ("正在停止，当前原子操作完成后生效", identifier),
        )
    return jobs.get(identifier)


@router.post("/jobs/{identifier}/retry")
async def retry(identifier: str):
    return jobs.retry(identifier)


@router.get("/jobs/{identifier}/events")
async def events(identifier: str, request: Request, after: int = 0):
    jobs.get(identifier)
    try:
        after = max(after, int(request.headers.get("last-event-id", "0")))
    except ValueError:
        raise HTTPException(422, "事件游标须为整数") from None

    async def stream():
        cursor = after
        while not await request.is_disconnected():
            with store.connection() as c:
                rows = [
                    dict(r)
                    for r in c.execute(
                        "SELECT * FROM job_events WHERE job_id=? AND id>? ORDER BY id LIMIT 100",
                        (identifier, cursor),
                    )
                ]
            for row in rows:
                cursor = row["id"]
                yield (
                    f"id: {cursor}\ndata: "
                    + json.dumps(row, ensure_ascii=False)
                    + "\n\n"
                )
            if (
                jobs.get(identifier)["state"] in {"completed", "failed", "cancelled"}
                and len(rows) < 100
            ):
                yield "event: end\ndata: {}\n\n"
                break
            if not rows:
                yield ": heartbeat\n\n"
            await asyncio.sleep(0.6)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/retrieval/status")
def retrieval_status():
    return retrieval.status()


class DocumentEdit(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=350)
    archived: bool | None = None
    aliases: list[str] | None = Field(default=None, max_length=12)


@router.patch("/documents/{identifier}")
def edit_document(identifier: str, body: DocumentEdit):
    record = store.get_document(identifier)
    with store.connection() as c:
        if body.aliases is not None:
            aliases = list(dict.fromkeys(a.strip() for a in body.aliases if a.strip()))
            if any(len(a) > 100 for a in aliases):
                raise ValueError("每个文献别名最多 100 字")
            metadata = {**record["metadata"], "aliases": aliases}
            c.execute(
                "UPDATE documents SET metadata=? WHERE id=?",
                (json.dumps(metadata, ensure_ascii=False), identifier),
            )
        if body.title is not None:
            c.execute(
                "UPDATE documents SET title=? WHERE id=?",
                (body.title.strip(), identifier),
            )
        if body.archived is not None:
            c.execute(
                "UPDATE documents SET archived=? WHERE id=?",
                (int(body.archived), identifier),
            )
    result = store.get_document(identifier)
    result.pop("path", None)
    return result


@router.get("/library/archived")
def archived():
    with store.connection() as c:
        return [
            dict(r)
            for r in c.execute(
                "SELECT id,name,title,pages,version FROM documents WHERE archived=1"
            )
        ]


@router.get("/documents/{identifier}/duplicates")
def duplicates(identifier: str):
    target = store.get_document(identifier)
    candidates = []
    docs = store.list_documents()
    similarities = {}
    if retrieval.available() and docs:
        vectors = retrieval.embed([target["title"]] + [d["title"] for d in docs])
        similarities = {
            d["id"]: float(vectors[0] @ v) for d, v in zip(docs, vectors[1:])
        }
    for doc in docs:
        if doc["id"] == identifier:
            continue
        same = (
            target["arxiv_id"] and target["arxiv_id"] == doc["arxiv_id"]
        ) or research.normalized_title(target["title"]) == research.normalized_title(
            doc["title"]
        )
        if same or similarities.get(doc["id"], 0) >= 0.87:
            candidates.append(
                {
                    **doc,
                    **store.content_similarity(identifier, doc["id"]),
                    "semantic_title_similarity": round(
                        similarities.get(doc["id"], 0), 5
                    ),
                    "match_status": "同文版本候选"
                    if same
                    else "语义相近，需人工确认是否同一论文",
                }
            )
    return candidates


class VersionPair(BaseModel):
    first: str
    second: str


@router.post("/versions/diff")
def diff(body: VersionPair):
    return impact.version_diff(body.first, body.second)


@router.get("/documents/{identifier}/structure")
def structure(identifier: str):
    store.get_document(identifier)
    return parsing.stored(identifier) or {
        "complete": False,
        "pages": [],
        "references": [],
        "headings": [],
    }


@router.get("/documents/{identifier}/formula-regions")
def formula_regions(identifier: str, page: int = Query(default=1, ge=1)):
    return formula.regions(identifier, page)


class FormulaCorrection(BaseModel):
    latex: str = Field(min_length=1, max_length=12000)


@router.patch("/formulas/{identifier}")
def correct_formula(identifier: str, body: FormulaCorrection):
    item = research.artifact(identifier)
    if item["kind"] != "formula":
        raise ValueError("请选择公式识别记录")
    content = item["content"]
    content.setdefault("edits", []).append({"previous": content["latex"]})
    content.update(latex=body.latex, warnings=formula.validation(body.latex))
    with store.connection() as c:
        c.execute(
            "UPDATE artifacts SET content=? WHERE id=?",
            (json.dumps(content, ensure_ascii=False), identifier),
        )
    return research.artifact(identifier)


@router.get("/documents/{identifier}/references")
def references(identifier: str):
    record = store.get_document(identifier)
    entries, citations = parsing.references(record)
    return {"references": entries, "citations": citations}


@router.get("/documents/{identifier}/table-regions")
def table_regions(identifier: str, page: int = Query(default=1, ge=1)):
    return tables.regions(identifier, page)


class TableCorrection(BaseModel):
    rows: list[list[str]] | None = Field(default=None, max_length=200)
    column_bounds: list[float] | None = Field(default=None, max_length=31)
    revision: int = Field(ge=0)


@router.patch("/tables/{identifier}")
def correct_table(identifier: str, body: TableCorrection):
    if (body.rows is None) == (body.column_bounds is None):
        raise ValueError("请提交单元格修改或分列线设置")
    with store.connection() as c:
        c.execute("BEGIN IMMEDIATE")
        row = c.execute(
            "SELECT * FROM artifacts WHERE id=? AND kind='table'", (identifier,)
        ).fetchone()
        if row is None:
            raise KeyError(identifier)
        content = json.loads(row["content"])
        if content["revision"] != body.revision:
            raise HTTPException(409, "此表格已在其他页面修改，请重新打开后再保存")
        content.setdefault("edits", []).append(
            {
                "revision": body.revision,
                "rows": content["rows"],
                "column_bounds": content["column_bounds"],
            }
        )
        if body.rows is not None:
            same_shape = len(body.rows) == len(content["rows"]) and all(
                len(a) == len(b) for a, b in zip(body.rows, content["rows"])
            )
            content["rows"] = tables.validate_rows(body.rows)
            # Added/deleted rows are user edits, not newly detected source coordinates.
            if not same_shape:
                content["cells"] = None
        else:
            content.update(
                tables.grid_from_tokens(
                    content["tokens"], content["source"]["bbox"], body.column_bounds
                )
            )
        content["revision"] += 1
        c.execute(
            "UPDATE artifacts SET content=? WHERE id=?",
            (json.dumps(content, ensure_ascii=False), identifier),
        )
    return research.artifact(identifier)


@router.get("/tables/{identifier}/export")
def export_table(identifier: str):
    item = research.artifact(identifier)
    if item["kind"] != "table":
        raise ValueError("请选择表格记录")
    return Response(
        tables.csv_text(item["content"]["rows"]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="source-table.csv"'},
    )


@router.get("/documents/{identifier}/crop")
def crop(
    identifier: str,
    page: int = Query(ge=1),
    x0: float = 0,
    y0: float = 0,
    x1: float = 10000,
    y1: float = 10000,
):
    record = store.get_document(identifier)
    if page > record["pages"]:
        raise ValueError("页码超出范围")
    with pymupdf.open(record["path"]) as pdf:
        area = pymupdf.Rect(x0, y0, x1, y1) & pdf[page - 1].rect
        if area.is_empty or area.is_infinite:
            raise ValueError("裁剪区域无效")
        pix = pdf[page - 1].get_pixmap(dpi=120, clip=area, alpha=False)
        return Response(pix.tobytes("png"), media_type="image/png")


class TextTranslation(BaseModel):
    text: str = Field(min_length=1, max_length=7000)
    language: Literal["zh", "en"] = "zh"


@router.post("/translate/text")
async def translate_text(body: TextTranslation):
    result = await translation.translate_text(body.text, body.language)
    return {
        "translation": result,
        "quality": translation.quality_signals(body.text, result, body.language),
    }


@router.get("/documents/{identifier}/translation")
def translations(
    identifier: str,
    language: Literal["zh", "en"] = "zh",
    page: int | None = Query(default=None, ge=1),
):
    store.get_document(identifier)
    return translation.aligned(identifier, language, page)


@router.get("/documents/{identifier}/translation/export")
def translation_export(
    identifier: str,
    language: Literal["zh", "en"] = "zh",
    format: Literal["md", "html"] = "md",
):
    return Response(
        translation.export(identifier, language, format),
        media_type="text/html" if format == "html" else "text/markdown",
        headers={"Content-Disposition": f'attachment; filename="translation.{format}"'},
    )


class SearchPapers(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    source: Literal["arxiv", "crossref"] = "arxiv"
    latest: bool = False
    start: int = Field(default=0, ge=0, le=9900)
    year_from: int | None = Field(default=None, ge=1900, le=2100)
    year_to: int | None = Field(default=None, ge=1900, le=2100)
    force: bool = False


@router.post("/discover/search")
async def discover(body: SearchPapers):
    if body.year_from and body.year_to and body.year_from > body.year_to:
        raise ValueError("起始年份不能晚于结束年份")
    return await discovery.search_cached(**body.model_dump())


@router.get("/discover/recommendations")
async def recommendations():
    return await discovery.recommend()


class Vote(BaseModel):
    paper_id: str
    vote: Literal[-1, 0, 1]


@router.post("/discover/feedback")
def feedback(body: Vote):
    discovery.remote(body.paper_id)
    with store.connection() as c:
        c.execute(
            "INSERT OR REPLACE INTO feedback(paper_id,vote) VALUES(?,?)",
            (body.paper_id, body.vote),
        )
    return body


class Tracker(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    interval_hours: int = Field(default=24, ge=1, le=720)


class RepositoryCheck(BaseModel):
    paper_id: str = Field(min_length=1, max_length=250)


@router.post("/discover/repositories")
async def repositories(body: RepositoryCheck):
    return await discovery.check_repositories(body.paper_id)


@router.get("/trackers")
def trackers():
    return discovery.trackers()


@router.post("/trackers")
async def tracker(body: Tracker):
    identifier = uuid.uuid4().hex
    with store.connection() as c:
        c.execute(
            "INSERT INTO trackers(id,query,interval_hours) VALUES(?,?,?)",
            (identifier, body.query, body.interval_hours),
        )
    return {"id": identifier, "job": jobs.submit("track", {"tracker_id": identifier})}


class Enable(BaseModel):
    enabled: bool


@router.patch("/trackers/{identifier}")
def toggle_tracker(identifier: str, body: Enable):
    with store.connection() as c:
        changed = c.execute(
            "UPDATE trackers SET enabled=? WHERE id=?", (int(body.enabled), identifier)
        ).rowcount
    if not changed:
        raise KeyError(identifier)
    return {"ok": True}


@router.get("/graph")
def graph():
    return research.build_graph()


class Edge(BaseModel):
    source: str
    target: str
    hidden: bool


@router.post("/graph/edge")
def edge(body: Edge):
    store.get_document(body.source)
    store.get_document(body.target)
    with store.connection() as c:
        c.execute(
            "INSERT OR REPLACE INTO edge_feedback VALUES(?,?,?)",
            (body.source, body.target, int(body.hidden)),
        )
    return {"ok": True}


@router.get("/artifacts")
def artifacts():
    with store.connection() as c:
        return [
            dict(r)
            for r in c.execute(
                "SELECT id,kind,title,created_at FROM artifacts ORDER BY created_at DESC"
            )
        ]


@router.get("/artifacts/{identifier}")
def artifact(identifier: str):
    return research.artifact(identifier)


@router.get("/artifacts/{identifier}/export")
def export(identifier: str, format: Literal["md", "json"] = "md"):
    item = research.artifact(identifier)
    text = (
        json.dumps(item, ensure_ascii=False, indent=2)
        if format == "json"
        else research.export_markdown(item)
    )
    return Response(
        text,
        media_type="application/json" if format == "json" else "text/markdown",
        headers={"Content-Disposition": f'attachment; filename="research.{format}"'},
    )


class Bibtex(BaseModel):
    document_ids: list[str] = Field(max_length=100)


@router.post("/bibliography")
def bibliography(body: Bibtex):
    return {"bibtex": research.bibtex(body.document_ids)}


class Chart(BaseModel):
    csv: str = Field(min_length=1, max_length=2_000_000)
    x: str = Field(min_length=1, max_length=150)
    ys: list[str] = Field(min_length=1, max_length=6)
    kind: Literal["line", "bar", "table", "radar3d", "scatter"]
    title: str = Field(default="", max_length=200)
    unit: str = Field(default="Value", max_length=100)
    xscale: Literal["linear", "log"] = "linear"
    yscale: Literal["linear", "log"] = "linear"


@router.post("/charts")
def chart(body: Chart):
    return charts.create(body.model_dump())


@router.get("/charts/{identifier}/{filename}")
def chart_file(identifier: str, filename: str):
    item = research.artifact(identifier)
    if item["kind"] != "chart":
        raise ValueError("不是图表记录")
    folder = store.database_path().parent / "exports" / identifier
    allowed = {
        "chart.png",
        "chart.svg",
        "chart.pdf",
        "data.csv",
        "spec.json",
        "reproduce.py",
    }
    if filename == "bundle.zip":
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
            for name in sorted(allowed):
                z.write(folder / name, name)
        return Response(
            buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="chart-bundle.zip"'},
        )
    if filename not in allowed:
        raise KeyError(filename)
    return FileResponse(
        folder / filename,
        filename=filename,
        content_disposition_type="inline"
        if filename.endswith(".png")
        else "attachment",
    )


class Diagram(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=12000)


@router.post("/diagrams")
def diagram(body: Diagram):
    if not re.match(
        r"^\s*(?:flowchart|graph|sequenceDiagram|classDiagram|stateDiagram|erDiagram|mindmap)\b",
        body.code,
    ):
        raise ValueError("请选择支持的 Mermaid 图类型")
    if re.search(r"%%\{|\bclick\b|<|>|javascript:|https?://", body.code, re.I):
        # Arrow syntax is permitted, HTML and external interactions are not.
        cleaned = re.sub(r"[-=.]+>", "", body.code)
        if re.search(r"%%\{|\bclick\b|<|>|javascript:|https?://", cleaned, re.I):
            raise ValueError("图脚本不允许 HTML、链接或交互指令")
    return research.save_artifact("diagram", body.title, {"code": body.code})
