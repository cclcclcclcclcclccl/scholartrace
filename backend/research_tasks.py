"""Project-scoped evidence gaps with atomic source-backed completion."""

import json
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import boundaries, store

router = APIRouter(prefix="/api/research-tasks")


def stamp():
    return datetime.now(UTC).isoformat()


def decode(row):
    item = dict(row)
    item["evidence"] = json.loads(item["evidence"]) if item.get("evidence") else None
    return item


def read(conn, identifier):
    row = conn.execute(
        "SELECT t.*,p.title AS project_title,p.archived AS project_archived,c.archived AS comparison_archived,c.revision AS comparison_revision,c.title AS comparison_title,EXISTS(SELECT 1 FROM project_documents pd JOIN documents d ON d.id=pd.document_id WHERE pd.project_id=t.project_id AND pd.document_id=t.document_id AND d.archived=0) AS source_in_project FROM research_tasks t JOIN projects p ON p.id=t.project_id JOIN evidence_comparisons c ON c.id=t.comparison_id WHERE t.id=?",
        (identifier,),
    ).fetchone()
    if not row:
        raise KeyError(identifier)
    result = decode(row)
    result["events"] = [
        decode(r)
        for r in conn.execute(
            "SELECT * FROM research_task_events WHERE task_id=? ORDER BY id",
            (identifier,),
        )
    ]
    return result


def snapshot(conn, project_id):
    return [
        read(conn, r[0])
        for r in conn.execute(
            "SELECT id FROM research_tasks WHERE project_id=? ORDER BY updated_at DESC,id",
            (project_id,),
        ).fetchall()
    ]


def editable(task):
    if (
        task["project_archived"]
        or task["comparison_archived"]
        or not task["source_in_project"]
    ):
        raise HTTPException(
            409, "项目或对照表已归档，或文献已移出项目/归档；请恢复关联后再操作"
        )


def event(conn, identifier, state, outcome="", evidence=None):
    conn.execute(
        "INSERT INTO research_task_events(task_id,state,outcome,evidence,created_at) VALUES(?,?,?,?,?)",
        (
            identifier,
            state,
            outcome,
            json.dumps(evidence, ensure_ascii=False) if evidence else None,
            stamp(),
        ),
    )


class Create(BaseModel):
    project_id: str
    comparison_id: str
    document_id: str
    field: str
    comparison_revision: int = Field(gt=0)


@router.post("")
def create(body: Create):
    with store.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        project = conn.execute(
            "SELECT * FROM projects WHERE id=?", (body.project_id,)
        ).fetchone()
        if not project:
            raise KeyError(body.project_id)
        comparison = boundaries.read(body.comparison_id, conn)
        if body.field not in boundaries.FIELDS:
            raise ValueError("未知补查维度")
        paper = next(
            (
                p
                for p in comparison["content"]["papers"]
                if p["document_id"] == body.document_id
            ),
            None,
        )
        if not paper:
            raise KeyError(body.document_id)
        valid = conn.execute(
            "SELECT 1 FROM project_documents pd JOIN documents d ON d.id=pd.document_id WHERE pd.project_id=? AND pd.document_id=? AND d.archived=0",
            (body.project_id, body.document_id),
        ).fetchone()
        if project["archived"] or comparison["archived"] or not valid:
            raise ValueError("请选择包含本篇文献的未归档项目，并先恢复对照表与文献")
        previous = conn.execute(
            "SELECT id FROM research_tasks WHERE project_id=? AND comparison_id=? AND document_id=? AND field=?",
            (body.project_id, body.comparison_id, body.document_id, body.field),
        ).fetchone()
        if previous:
            return read(conn, previous[0])
        if comparison["revision"] != body.comparison_revision:
            raise HTTPException(409, "对照表已更新，请重新打开后再创建待办")
        if paper["cells"][body.field] is not None:
            raise ValueError("这一格已有整理，请仅从待补查单元格创建待办")
        identifier = uuid.uuid4().hex
        title = f"补查{boundaries.FIELDS[body.field]} · {paper['title']}"
        conn.execute(
            "INSERT INTO research_tasks(id,project_id,comparison_id,document_id,field,title,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                identifier,
                body.project_id,
                body.comparison_id,
                body.document_id,
                body.field,
                title,
                stamp(),
                stamp(),
            ),
        )
        event(conn, identifier, "todo")
        return read(conn, identifier)


@router.get("")
def listing(project_id: str | None = None, comparison_id: str | None = None):
    if not project_id and not comparison_id:
        raise ValueError("请选择项目或对照表")
    with store.connection() as conn:
        if (
            project_id
            and not conn.execute(
                "SELECT 1 FROM projects WHERE id=?", (project_id,)
            ).fetchone()
        ):
            raise KeyError(project_id)
        if comparison_id:
            boundaries.read(comparison_id, conn)
        rows = conn.execute(
            "SELECT id FROM research_tasks WHERE (? IS NULL OR project_id=?) AND (? IS NULL OR comparison_id=?) ORDER BY updated_at DESC,id LIMIT 200",
            (project_id, project_id, comparison_id, comparison_id),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM research_tasks WHERE (? IS NULL OR project_id=?) AND (? IS NULL OR comparison_id=?)",
            (project_id, project_id, comparison_id, comparison_id),
        ).fetchone()[0]
        return {"items": [read(conn, r[0]) for r in rows], "total": total}


class Update(BaseModel):
    revision: int = Field(gt=0)
    state: Literal["todo", "working", "dismissed"]
    outcome: str = Field(default="", max_length=1500)


@router.patch("/{identifier}")
def update(identifier: str, body: Update):
    with store.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        task = read(conn, identifier)
        editable(task)
        if task["revision"] != body.revision:
            raise HTTPException(409, "待办已在其他页面更新，请刷新核对后重试")
        if body.state == "dismissed" and not body.outcome.strip():
            raise ValueError("未解决关闭时请说明原因，不能当成已证实")
        conn.execute(
            "UPDATE research_tasks SET state=?,outcome=?,revision=revision+1,updated_at=? WHERE id=?",
            (body.state, body.outcome.strip(), stamp(), identifier),
        )
        event(conn, identifier, body.state, body.outcome.strip(), task["evidence"])
        return read(conn, identifier)


class Complete(BaseModel):
    revision: int = Field(gt=0)
    comparison_revision: int = Field(gt=0)
    note_id: int = Field(gt=0)
    value: str = Field(min_length=1, max_length=1500)
    quote: str = Field(min_length=1, max_length=12000)


@router.post("/{identifier}/complete")
def complete(identifier: str, body: Complete):
    with store.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        task = read(conn, identifier)
        editable(task)
        if (
            task["revision"] != body.revision
            or task["comparison_revision"] != body.comparison_revision
        ):
            raise HTTPException(
                409, "待办或对照表已更新。草稿仍保留，请刷新核对最新状态后重试"
            )
        if task["state"] not in {"todo", "working"}:
            raise ValueError("请先重新打开已结束的待办")
        comparison = boundaries.read(task["comparison_id"], conn)
        paper = next(
            p
            for p in comparison["content"]["papers"]
            if p["document_id"] == task["document_id"]
        )
        if paper["cells"][task["field"]] is not None:
            raise HTTPException(
                409,
                "目标单元格已有内容，本次没有覆盖。请返回对照表核对，必要时手动清空后再回填",
            )
        row = conn.execute(
            "SELECT n.*,b.text,b.document_id,b.page,b.bbox,b.width,b.height,d.archived AS document_archived FROM evidence_notes n JOIN blocks b ON b.id=n.block_id JOIN documents d ON d.id=b.document_id WHERE n.id=?",
            (body.note_id,),
        ).fetchone()
        if not row:
            raise KeyError(body.note_id)
        if (
            row["document_id"] != task["document_id"]
            or row["archived"]
            or row["document_archived"]
        ):
            raise ValueError("请选择本篇文献的未归档证据笔记")
        value, quote = body.value.strip(), body.quote.strip()
        if (
            not value
            or not quote
            or not row["quote"].strip()
            or not store.quote_in_source(row["quote"], row["text"])
            or not store.quote_in_source(quote, row["quote"])
        ):
            raise ValueError("整理与摘录不能为空，且摘录必须能在所选笔记原文中核对")
        source = {
            k: row[k]
            for k in ("block_id", "document_id", "page", "width", "height", "quote")
        }
        source.update(
            note_id=body.note_id, observation=row["note"], bbox=json.loads(row["bbox"])
        )
        existing = next(
            (s for s in paper["sources"] if s["note_id"] == body.note_id), None
        )
        if existing and existing["quote"] != source["quote"]:
            raise HTTPException(409, "该笔记的引文与历史快照不同，请新建证据笔记后回填")
        if not existing:
            paper["sources"].append(source)
            comparison["content"]["note_ids"].append(body.note_id)
        cell = {"value": value, "quote": quote, "note_id": body.note_id}
        paper["cells"][task["field"]] = cell
        evidence = {
            "source": source,
            "cell": cell,
            "comparison_revision": comparison["revision"] + 1,
        }
        conn.execute(
            "UPDATE evidence_comparisons SET content=?,revision=revision+1,updated_at=? WHERE id=?",
            (
                json.dumps(comparison["content"], ensure_ascii=False),
                stamp(),
                comparison["id"],
            ),
        )
        conn.execute(
            "UPDATE research_tasks SET state='done',outcome=?,evidence=?,revision=revision+1,updated_at=? WHERE id=?",
            (value, json.dumps(evidence, ensure_ascii=False), stamp(), identifier),
        )
        event(conn, identifier, "done", value, evidence)
        return read(conn, identifier)
