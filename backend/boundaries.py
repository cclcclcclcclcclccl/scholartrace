"""Human-curated comparisons with literal evidence validation, not semantic grading."""

import json
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import store
from .comparison_readiness import audit as readiness

router = APIRouter(prefix="/api/boundaries")
FIELDS = {
    "object": "研究对象",
    "data": "数据与样本",
    "metric": "指标与结果",
    "conditions": "实验条件",
    "limits": "适用范围与限制",
}
NOTICE = "每格由用户整理，系统只核对摘录是否存在于所选证据，不判断解释是否正确或两篇论文是否可直接比较。待补查不代表论文未报告。证据为创建时快照，版本更新需另行复核。"


def read(identifier, conn):
    row = conn.execute(
        "SELECT * FROM evidence_comparisons WHERE id=?", (identifier,)
    ).fetchone()
    if not row:
        raise KeyError(identifier)
    content = json.loads(row["content"])
    return {**dict(row), "content": content, "readiness": readiness(content)}


@router.get("")
def listing(archived: bool = False):
    with store.connection() as conn:
        rows = conn.execute(
            "SELECT id,title,revision,updated_at,archived FROM evidence_comparisons WHERE archived=? ORDER BY updated_at DESC,id DESC LIMIT 100",
            (int(archived),),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM evidence_comparisons WHERE archived=?",
            (int(archived),),
        ).fetchone()[0]
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "fields": FIELDS,
        "notice": NOTICE,
    }


class Create(BaseModel):
    request_id: uuid.UUID
    title: str = Field(min_length=2, max_length=120)
    note_ids: list[int] = Field(min_length=2, max_length=6)


@router.post("")
def create(body: Create):
    if len(body.title.strip()) < 2 or len(set(body.note_ids)) != len(body.note_ids):
        raise ValueError("填写标题并选择2—6条不同的证据笔记")
    with store.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        old = conn.execute(
            "SELECT id FROM evidence_comparisons WHERE request_id=?",
            (str(body.request_id),),
        ).fetchone()
        if old:
            result = read(old["id"], conn)
            if (
                result["title"] != body.title.strip()
                or result["content"]["note_ids"] != body.note_ids
            ):
                raise HTTPException(409, "创建请求内容已改变，请重新创建")
            return result
        papers = {}
        for identifier in body.note_ids:
            row = conn.execute(
                "SELECT n.*,b.text,b.document_id,b.page,b.bbox,b.width,b.height,d.title,d.version,d.archived AS document_archived FROM evidence_notes n JOIN blocks b ON b.id=n.block_id JOIN documents d ON d.id=b.document_id WHERE n.id=?",
                (identifier,),
            ).fetchone()
            if not row:
                raise KeyError(identifier)
            if row["archived"] or row["document_archived"]:
                raise ValueError("请先恢复所选笔记及文献")
            if not row["quote"].strip() or not store.quote_in_source(
                row["quote"], row["text"]
            ):
                raise ValueError("笔记引文无法在原文核对，请检查来源")
            document = row["document_id"]
            paper = papers.setdefault(
                document,
                {
                    "document_id": document,
                    "title": row["title"],
                    "version": row["version"],
                    "sources": [],
                    "cells": {k: None for k in FIELDS},
                },
            )
            source = {
                k: row[k]
                for k in ("block_id", "document_id", "page", "width", "height", "quote")
            }
            source.update(
                note_id=identifier,
                observation=row["note"],
                bbox=json.loads(row["bbox"]),
            )
            paper["sources"].append(source)
        if not 2 <= len(papers) <= 3:
            raise ValueError("请选择来自2—3篇文献的笔记；同一篇可选多条补充证据")
        stamp = datetime.now(UTC).isoformat()
        identifier = uuid.uuid4().hex
        content = {
            "note_ids": body.note_ids,
            "papers": list(papers.values()),
            "fields": FIELDS,
            "notice": NOTICE,
        }
        conn.execute(
            "INSERT INTO evidence_comparisons(id,request_id,title,content,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (
                identifier,
                str(body.request_id),
                body.title.strip(),
                json.dumps(content, ensure_ascii=False),
                stamp,
                stamp,
            ),
        )
        return read(identifier, conn)


@router.get("/{identifier}")
def detail(identifier: str):
    with store.connection() as conn:
        return read(identifier, conn)


class Cell(BaseModel):
    revision: int = Field(gt=0)
    value: str = Field(default="", max_length=1500)
    quote: str = Field(default="", max_length=12000)
    note_id: int | None = None


@router.patch("/{identifier}/cells/{document}/{field}")
def save(identifier: str, document: str, field: str, body: Cell):
    if field not in FIELDS:
        raise ValueError("未知对照维度")
    with store.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        result = read(identifier, conn)
        if result["archived"]:
            raise ValueError("对照表已归档，请先恢复后再编辑")
        if result["revision"] != body.revision:
            raise HTTPException(
                409, "对照表已在其他页面更新，草稿仍保留。请核对最新单元格后再保存。"
            )
        paper = next(
            (p for p in result["content"]["papers"] if p["document_id"] == document),
            None,
        )
        if paper is None:
            raise KeyError(document)
        value, quote = body.value.strip(), body.quote.strip()
        if value or quote:
            source = next(
                (s for s in paper["sources"] if s["note_id"] == body.note_id), None
            )
            if not source or not value or not quote:
                raise ValueError(
                    "填写你的整理和对应摘录，并选择本篇来源；证据不足时请留为待补查"
                )
            if not store.quote_in_source(quote, source["quote"]):
                raise ValueError(
                    "摘录不在所选证据中，请从原文复制；不要补写未经报告的内容"
                )
            paper["cells"][field] = {
                "value": value,
                "quote": quote,
                "note_id": body.note_id,
            }
        else:
            paper["cells"][field] = None
        conn.execute(
            "UPDATE evidence_comparisons SET content=?,revision=revision+1,updated_at=? WHERE id=?",
            (
                json.dumps(result["content"], ensure_ascii=False),
                datetime.now(UTC).isoformat(),
                identifier,
            ),
        )
        return read(identifier, conn)


class Manage(BaseModel):
    revision: int = Field(gt=0)
    archived: bool


@router.patch("/{identifier}")
def manage(identifier: str, body: Manage):
    with store.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        result = read(identifier, conn)
        if result["revision"] != body.revision:
            raise HTTPException(409, "对照表已更新，请刷新后再归档或恢复")
        conn.execute(
            "UPDATE evidence_comparisons SET archived=?,revision=revision+1,updated_at=? WHERE id=?",
            (int(body.archived), datetime.now(UTC).isoformat(), identifier),
        )
        return read(identifier, conn)


@router.get("/{identifier}/export")
def export(identifier: str, format: Literal["md", "json"] = "md"):
    result = detail(identifier)
    if format == "json":
        text = json.dumps(result, ensure_ascii=False, indent=2)
    else:
        lines = ["# " + result["title"], NOTICE]
        check = result["readiness"]
        lines += [
            "## 比较前检查",
            check["notice"],
            f"当前待补查：{check['missing_cells']} 格",
        ]
        lines += ["- " + text for text in check["hints"] + check["questions"]]
        for paper in result["content"]["papers"]:
            lines.append(f"## {paper['title']} · v{paper['version'] or '?'}")
            for key, label in FIELDS.items():
                cell = paper["cells"][key]
                lines.append("### " + label)
                if not cell:
                    lines.append("待补查（不代表论文未报告）")
                    continue
                source = next(
                    s for s in paper["sources"] if s["note_id"] == cell["note_id"]
                )
                lines.extend(
                    [
                        "用户整理：" + cell["value"],
                        "> " + cell["quote"].replace("\n", "\n> "),
                        f"PDF第{source['page']}页 · 来源块{source['block_id']} · 笔记{source['note_id']}",
                    ]
                )
        text = "\n\n".join(lines)
    return Response(
        text,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="Moheng-boundaries-{identifier}.{format}"'
        },
    )
