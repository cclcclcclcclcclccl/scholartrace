"""Source-backed self-assessment cards. Scheduling is a heuristic, not grading."""

import html
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import store

router = APIRouter(prefix="/api/recall")


def now():
    return datetime.now(UTC)


def cards():
    with store.connection() as conn:
        rows = conn.execute(
            "SELECT c.*,b.id AS block_id,b.document_id,b.page,b.bbox,b.width,b.height,"
            "d.title,d.version,n.archived AS note_archived,d.archived AS document_archived "
            "FROM recall_cards c JOIN evidence_notes n ON n.id=c.note_id "
            "JOIN blocks b ON b.id=n.block_id JOIN documents d ON d.id=b.document_id "
            "ORDER BY c.due_at,c.created_at,c.id"
        ).fetchall()
    moment = now()
    return [
        {
            **dict(r),
            "bbox": json.loads(r["bbox"]),
            "due": datetime.fromisoformat(r["due_at"]) <= moment,
        }
        for r in rows
    ]


@router.get("")
def listing():
    result = cards()
    active = [
        c
        for c in result
        if not c["archived"] and not c["note_archived"] and not c["document_archived"]
    ]
    return {
        "cards": active,
        "due_count": sum(c["due"] for c in active),
        "review_count": sum(c["reviews"] for c in active),
        "hidden_count": len(result) - len(active),
        "archived_cards": [c for c in result if c["archived"]],
        "notice": "自评用于安排复习，不代表掌握度或科研结论正确率。卡片保留创建时的观察和原文；论文新版本需另行复核。",
    }


class Create(BaseModel):
    note_id: int = Field(gt=0)
    prompt: str = Field(min_length=3, max_length=500)


@router.post("")
def create(body: Create):
    prompt = body.prompt.strip()
    if len(prompt) < 3:
        raise ValueError("请填写至少三个字的问题")
    with store.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT n.*,b.text,d.archived AS document_archived FROM evidence_notes n "
            "JOIN blocks b ON b.id=n.block_id JOIN documents d ON d.id=b.document_id WHERE n.id=?",
            (body.note_id,),
        ).fetchone()
        if not row:
            raise KeyError(body.note_id)
        if row["archived"] or row["document_archived"]:
            raise ValueError("请先恢复这条笔记及其文献，再创建复习卡")
        if not row["quote"].strip() or not store.quote_in_source(
            row["quote"], row["text"]
        ):
            raise ValueError("笔记引文无法在原文块中核对，请先检查来源")
        old = conn.execute(
            "SELECT id FROM recall_cards WHERE note_id=?", (body.note_id,)
        ).fetchone()
        if old:
            identifier = old["id"]
        else:
            identifier = uuid.uuid4().hex
            stamp = now().isoformat()
            conn.execute(
                "INSERT INTO recall_cards(id,note_id,prompt,observation,quote,due_at,created_at) VALUES(?,?,?,?,?,?,?)",
                (
                    identifier,
                    body.note_id,
                    prompt,
                    row["note"],
                    row["quote"],
                    stamp,
                    stamp,
                ),
            )
    return {
        "card": next(c for c in cards() if c["id"] == identifier),
        "already_exists": bool(old),
    }


class Review(BaseModel):
    revision: int = Field(gt=0)
    rating: Literal["again", "hard", "good"]


@router.post("/{identifier}/review")
def review(identifier: str, body: Review):
    moment = now()
    with store.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT c.*,n.archived AS note_archived,d.archived AS document_archived FROM recall_cards c "
            "JOIN evidence_notes n ON n.id=c.note_id JOIN blocks b ON b.id=n.block_id "
            "JOIN documents d ON d.id=b.document_id WHERE c.id=?",
            (identifier,),
        ).fetchone()
        if not row:
            raise KeyError(identifier)
        if row["archived"] or row["note_archived"] or row["document_archived"]:
            raise ValueError("卡片或来源已归档，请恢复后再复习")
        if row["revision"] != body.revision:
            raise HTTPException(
                409, "此卡片已在其他页面更新，请刷新后再评价；本次没有重复计入"
            )
        days = (
            0
            if body.rating == "again"
            else 1
            if body.rating == "hard"
            else min(60, max(3, row["interval_days"] * 2))
        )
        due = moment + (
            timedelta(minutes=10) if body.rating == "again" else timedelta(days=days)
        )
        conn.execute(
            "UPDATE recall_cards SET revision=revision+1,reviews=reviews+1,interval_days=?,due_at=?,last_rating=? WHERE id=?",
            (days, due.isoformat(), body.rating, identifier),
        )
        conn.execute(
            "INSERT INTO recall_reviews(card_id,rating,reviewed_at,next_due) VALUES(?,?,?,?)",
            (identifier, body.rating, moment.isoformat(), due.isoformat()),
        )
    return {"due_at": due.isoformat(), "interval_days": days}


class Edit(BaseModel):
    revision: int = Field(gt=0)
    prompt: str | None = Field(default=None, min_length=3, max_length=500)
    archived: bool | None = None


@router.patch("/{identifier}")
def edit(identifier: str, body: Edit):
    if body.prompt is None and body.archived is None:
        raise ValueError("请选择要修改的题目或归档状态")
    prompt = body.prompt.strip() if body.prompt is not None else None
    if prompt is not None and len(prompt) < 3:
        raise ValueError("问题至少需要三个字")
    with store.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM recall_cards WHERE id=?", (identifier,)
        ).fetchone()
        if not row:
            raise KeyError(identifier)
        if row["revision"] != body.revision:
            raise HTTPException(
                409, "卡片已在其他页面更新。草稿仍保留，请刷新核对后再保存。"
            )
        conn.execute(
            "UPDATE recall_cards SET prompt=?,archived=?,revision=revision+1 WHERE id=?",
            (
                prompt if prompt is not None else row["prompt"],
                int(body.archived) if body.archived is not None else row["archived"],
                identifier,
            ),
        )
    return {"revision": body.revision + 1}


@router.get("/export")
def export(format: Literal["md", "tsv", "json"] = "md"):
    rows = listing()["cards"]
    if format == "json":
        value = json.dumps(rows, ensure_ascii=False, indent=2)
    elif format == "tsv":

        def safe(value):
            return (
                html.escape(value)
                .replace("\t", " ")
                .replace("\r", "")
                .replace("\n", "<br>")
            )

        value = (
            "#separator:Tab\n#html:true\n#columns:问题\t原文与观察\t标签\n"
            + "\n".join(
                safe(c["prompt"])
                + "\t"
                + safe(
                    c["observation"]
                    + "\n\n"
                    + c["quote"]
                    + f"\n\n{c['title']} · v{c['version'] or '?'} · PDF第{c['page']}页\n来源块：{c['block_id']}"
                )
                + "\tMoheng"
                for c in rows
            )
        )
    else:
        value = (
            "# 证据复习卡\n\n自评不代表科研正确率；观察为用户笔记，原文为来源快照。\n\n"
            + "\n\n".join(
                f"## {c['prompt']}\n\n观察：{c['observation']}\n\n> "
                + c["quote"].replace("\n", "\n> ")
                + f"\n\n{c['title']} · v{c['version'] or '?'} · PDF第{c['page']}页\n\n来源块：{c['block_id']}"
                for c in rows
            )
        )
    return Response(
        value,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="Moheng-recall.{format}"'
        },
    )
