from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import (
    audit,
    store,
    database,
    jobs,
    retrieval,
    discovery,
    accounts,
    features,
    research,
    workspace_tools,
    experiments,
    proposal_revision,
)
from .review import review_change

ROOT = Path(__file__).resolve().parents[1]
# Windows registry associations may label .mjs as text/plain, breaking module workers.
mimetypes.add_type("text/javascript", ".mjs")
MODEL_URL = os.getenv("SCHOLARTRACE_MODEL_URL", "http://127.0.0.1:8081/v1").rstrip("/")
MODEL_NAME = os.getenv("SCHOLARTRACE_MODEL_NAME", "local")
if urlparse(MODEL_URL).hostname not in {"127.0.0.1", "localhost", "::1"}:
    raise RuntimeError(
        "This zero-budget prototype only accepts a loopback model service."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    accounts.initialize()
    schedulers = accounts.schedulers
    for path in [None] + accounts.databases():
        token = store.database_override.set(path)
        try:
            database.initialize()
            await jobs.resume()
            schedulers.append(asyncio.create_task(discovery.scheduler()))
        finally:
            store.database_override.reset(token)
    try:
        yield
    finally:
        for task in schedulers:
            task.cancel()
        await asyncio.gather(*schedulers, return_exceptions=True)
        schedulers.clear()
        await jobs.shutdown()


app = FastAPI(title="ScholarTrace", version="0.2.0", lifespan=lifespan)
app.middleware("http")(accounts.scope)
app.include_router(accounts.router)
app.include_router(features.router)
app.include_router(workspace_tools.router)
app.include_router(experiments.router)


@app.exception_handler(KeyError)
async def missing_record(request, exc):
    return JSONResponse({"detail": "记录不存在或不属于当前研究空间"}, 404)


@app.exception_handler(ValueError)
async def invalid_value(request, exc):
    return JSONResponse({"detail": str(exc)}, 422)


@app.exception_handler(httpx.HTTPError)
async def upstream_error(request, exc):
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        return JSONResponse(
            {
                "detail": "论文数据源暂时限制了请求频率，请稍后重试。也可以切换 Crossref 检索；已导入的论文与本地问答仍可使用。"
            },
            503,
        )
    return JSONResponse(
        {
            "detail": "当前数据源或本地模型未能响应，请稍后重试；已保存的文献和任务仍然保留。"
        },
        502,
    )


def document(document_id: str) -> dict:
    try:
        return store.get_document(document_id)
    except KeyError:
        raise HTTPException(404, "文献不存在") from None


@app.get("/api/health")
async def health():
    available = False
    try:
        async with httpx.AsyncClient(timeout=1.5, trust_env=False) as client:
            response = await client.get(f"{MODEL_URL}/models")
            available = response.status_code == 200
    except httpx.HTTPError:
        pass
    return {
        "status": "ok",
        "service": "scholartrace",
        "model_available": available,
        "model_url": MODEL_URL,
        "retrieval": "BM25 + multilingual MiniLM + reciprocal rank fusion",
        "version": "0.2.0",
    }


@app.get("/api/documents")
def documents():
    return store.list_documents()


@app.get("/api/documents/{document_id}")
def detail(document_id: str):
    result = document(document_id)
    result.pop("path", None)
    return result


@app.get("/api/documents/{document_id}/pdf")
def pdf(document_id: str):
    record = document(document_id)
    return FileResponse(
        record["path"],
        media_type="application/pdf",
        content_disposition_type="inline",
        filename=record["name"],
    )


@app.get("/api/documents/{document_id}/pages/{page}/blocks")
def page_blocks(document_id: str, page: int):
    record = document(document_id)
    if not 1 <= page <= record["pages"]:
        raise HTTPException(404, "页码超出范围")
    return store.get_blocks(document_id, page)


@app.post("/api/documents")
async def upload(file: UploadFile):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "请选择 PDF 文件")
    folder = ROOT / "data/uploads"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}.pdf"
    total = 0
    try:
        with path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > 80 * 1024 * 1024:
                    raise HTTPException(413, "当前单份 PDF 上限为 80 MB")
                output.write(chunk)
        with path.open("rb") as stream:
            if b"%PDF-" not in stream.read(1024):
                raise HTTPException(400, "文件内容不是有效的 PDF")
        result = await asyncio.to_thread(
            store.import_pdf, path, Path(file.filename).name
        )
        if result.get("already_exists"):
            path.unlink(missing_ok=True)
        else:
            record = store.get_document(result["id"])
            if record["status"] == "needs_ocr":
                jobs.submit("ocr", {"document_id": result["id"]})
            else:
                jobs.submit("index", {"document_ids": [result["id"]]})
        result.pop("path", None)
        return result
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    except Exception:
        path.unlink(missing_ok=True)
        raise HTTPException(422, "PDF 解析失败，文件可能损坏或加密") from None
    finally:
        await file.close()


class Query(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[str] = Field(default_factory=list, max_length=40)


@app.post("/api/search")
def search(query: Query):
    for identifier in query.document_ids:
        document(identifier)
    return {
        "question": query.question,
        "terms": store.query_terms(query.question),
        "evidence": retrieval.search(query.question, query.document_ids),
        "method": "hybrid_bm25_multilingual_rrf",
        "answer": None,
    }


@app.post("/api/ask")
async def ask(query: Query):
    for identifier in query.document_ids:
        document(identifier)
    try:
        result = await research.grounded(query.question, query.document_ids)
        claims = result["claims"]
        saved = (
            research.save_artifact(
                "answer",
                query.question,
                {
                    "sections": [{"title": "回答与原文依据", **result}],
                    "notice": "保存时的回答及原文引用；模型结论需要核验，论文更新后可在版本复核中检查成果依赖。",
                },
            )
            if claims or result.get("subquestions")
            else None
        )
        return {
            "evidence": result["evidence"],
            "mode": "local_model" if result["evidence"] else "evidence_only",
            "model_answer": claims if result["evidence"] else None,
            "insufficient_evidence": not bool(claims),
            "message": result.get("validation")
            if claims
            else "当前检索证据不足以给出可核验的回答；以下原文供复核，不代表问题的答案。",
            "limitations": result.get("limitations", ""),
            "comparison": result.get("comparison", []),
            "subquestions": result.get("subquestions", []),
            "artifact_id": saved["id"] if saved else None,
        }
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        result = await asyncio.to_thread(search, query)
        result.update(
            mode="evidence_only",
            model_answer=None,
            message="本地生成服务未就绪或输出未通过检查；当前展示原文检索结果。",
        )
        return result


class Pair(BaseModel):
    first: str
    second: str


@app.post("/api/versions/compare")
def compare(pair: Pair):
    document(pair.first)
    document(pair.second)
    return store.content_similarity(pair.first, pair.second)


class Note(BaseModel):
    block_id: str
    note: str = Field(min_length=1, max_length=1000)


@app.get("/api/notes")
def notes():
    return audit.notes()


@app.post("/api/notes")
def save_note(note: Note):
    try:
        return audit.save_note(note.block_id, note.note)
    except KeyError:
        raise HTTPException(404, "原文块不存在") from None


class AuditTarget(BaseModel):
    target_document_id: str


@app.post("/api/versions/audit")
async def audit_version(target: AuditTarget):
    document(target.target_document_id)
    result = await asyncio.to_thread(audit.audit_against, target.target_document_id)
    async with httpx.AsyncClient(timeout=45, trust_env=False) as client:
        for item in result["results"][:12]:
            item["semantic_review"] = await review_change(
                item, client, MODEL_URL, MODEL_NAME
            )
    result["semantic_review_limit"] = 12
    return result


FRONTEND = ROOT / "frontend/dist"
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
