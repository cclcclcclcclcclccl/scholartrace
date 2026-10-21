"""Guided group-meeting practice using source snapshots, never invented grading."""

import json
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import store

router = APIRouter(prefix="/api/rehearsal")
ROUNDS = (
    (
        "讲清主张",
        "请用自己的话说明这段证据涉及的研究主张。区分原文明确报告的内容与你自己的解释；如果仅凭片段无法确定，请说明缺少什么。",
    ),
    (
        "回应证据追问",
        "如果听众问“你的依据是什么”，你会怎样引用这段原文？请明确数字对应的对象、实验设置或比较条件；原文未给出的信息不要补猜。",
    ),
    (
        "说明适用边界",
        "如果听众追问“这个结论能否推广”，你会怎样回应？请区分原文明确的条件、尚未验证的推测，以及需要回到全文补查的问题。",
    ),
)
NOTICE = "通用组会追问模板，按所选证据逐条练习；不是模型生成的论文结论，也不自动评判回答正确率。记录中的自检均由用户勾选。"


def read(identifier, conn):
    row = conn.execute(
        "SELECT * FROM rehearsal_sessions WHERE id=?", (identifier,)
    ).fetchone()
    if not row:
        raise KeyError(identifier)
    return {**dict(row), "content": json.loads(row["content"])}


@router.get("")
def listing():
    with store.connection() as conn:
        rows = conn.execute(
            "SELECT id,title,revision,created_at,updated_at FROM rehearsal_sessions ORDER BY updated_at DESC,id DESC LIMIT 100"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM rehearsal_sessions").fetchone()[0]
    return {"sessions": [dict(r) for r in rows], "total": total, "limit": 100}


class Create(BaseModel):
    request_id: uuid.UUID
    title: str = Field(min_length=2, max_length=120)
    note_ids: list[int] = Field(min_length=1, max_length=3)


@router.post("")
def create(body: Create):
    if (
        len(body.title.strip()) < 2
        or any(n < 1 for n in body.note_ids)
        or len(set(body.note_ids)) != len(body.note_ids)
    ):
        raise ValueError("请填写标题，并选择1—3条不同的证据笔记")
    with store.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        previous = conn.execute(
            "SELECT id FROM rehearsal_sessions WHERE request_id=?",
            (str(body.request_id),),
        ).fetchone()
        if previous:
            result = read(previous["id"], conn)
            if (
                result["title"] != body.title.strip()
                or result["content"]["note_ids"] != body.note_ids
            ):
                raise HTTPException(409, "同一次创建请求的内容发生变化，请重新创建")
            return result
        rounds = []
        for identifier in body.note_ids:
            row = conn.execute(
                "SELECT n.*,b.text,b.document_id,b.page,b.bbox,b.width,b.height,d.title,d.version,d.archived AS document_archived "
                "FROM evidence_notes n JOIN blocks b ON b.id=n.block_id JOIN documents d ON d.id=b.document_id WHERE n.id=?",
                (identifier,),
            ).fetchone()
            if not row:
                raise KeyError(identifier)
            if row["archived"] or row["document_archived"]:
                raise ValueError("请先恢复所选笔记及文献")
            if not row["quote"].strip() or not store.quote_in_source(
                row["quote"], row["text"]
            ):
                raise ValueError("所选笔记引文无法在来源中核对，请先检查原文")
            source = {
                k: row[k]
                for k in (
                    "block_id",
                    "document_id",
                    "page",
                    "width",
                    "height",
                    "title",
                    "version",
                    "quote",
                )
            }
            source.update(
                note_id=identifier,
                observation=row["note"],
                bbox=json.loads(row["bbox"]),
            )
            for label, question in ROUNDS:
                rounds.append(
                    {
                        "id": len(rounds),
                        "label": label,
                        "question": question,
                        "source": source,
                        "answer": "",
                        "checks": [],
                        "saved_at": None,
                    }
                )
        stamp = datetime.now(UTC).isoformat()
        session_id = uuid.uuid4().hex
        content = {"note_ids": body.note_ids, "rounds": rounds, "notice": NOTICE}
        conn.execute(
            "INSERT INTO rehearsal_sessions(id,request_id,title,content,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (
                session_id,
                str(body.request_id),
                body.title.strip(),
                json.dumps(content, ensure_ascii=False),
                stamp,
                stamp,
            ),
        )
        return read(session_id, conn)


@router.get("/{identifier}")
def detail(identifier: str):
    with store.connection() as conn:
        return read(identifier, conn)


class Answer(BaseModel):
    revision: int = Field(gt=0)
    answer: str = Field(max_length=6000)
    checks: list[Literal["source", "conditions", "unknowns"]] = Field(
        default_factory=list, max_length=3
    )


@router.patch("/{identifier}/rounds/{number}")
def save(identifier: str, number: int, body: Answer):
    with store.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        session = read(identifier, conn)
        if session["revision"] != body.revision:
            raise HTTPException(
                409,
                "演练已在其他页面更新。当前草稿仍保留，请载入最新记录核对后再保存。",
            )
        rounds = session["content"]["rounds"]
        if not 0 <= number < len(rounds):
            raise ValueError("演练轮次超出范围")
        stamp = datetime.now(UTC).isoformat()
        rounds[number].update(
            answer=body.answer, checks=list(dict.fromkeys(body.checks)), saved_at=stamp
        )
        conn.execute(
            "UPDATE rehearsal_sessions SET content=?,revision=revision+1,updated_at=? WHERE id=?",
            (json.dumps(session["content"], ensure_ascii=False), stamp, identifier),
        )
        return read(identifier, conn)


@router.get("/{identifier}/export")
def export(identifier: str, format: Literal["md", "json"] = "md"):
    session = detail(identifier)
    if format == "json":
        text = json.dumps(session, ensure_ascii=False, indent=2)
    else:
        labels = {
            "source": "核对原文",
            "conditions": "核对对象与条件",
            "unknowns": "标明不确定项",
        }
        parts = [f"# {session['title']}", NOTICE]
        for r in session["content"]["rounds"]:
            s = r["source"]
            parts.extend(
                [
                    f"## 第{r['id'] + 1}轮 · {r['label']}",
                    r["question"],
                    "我的回答：\n" + (r["answer"] or "尚未填写"),
                    "用户自检："
                    + ("、".join(labels[c] for c in r["checks"]) or "尚未勾选"),
                    "笔记观察（非标准答案）：" + s["observation"],
                    "> " + s["quote"].replace("\n", "\n> "),
                    f"{s['title']} · v{s['version'] or '?'} · PDF第{s['page']}页 · 来源块{s['block_id']}",
                ]
            )
        text = "\n\n".join(parts)
    return Response(
        text,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="ScholarTrace-rehearsal-{identifier}.{format}"'
        },
    )
