"""Account-local projects: explicit source membership, reusable outputs, and revision checks."""

import hashlib
import io
import json
import uuid
import zipfile
from contextvars import ContextVar
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import boundaries, research_tasks, store

router = APIRouter(prefix="/api/projects")
current = ContextVar("scholartrace_project", default=None)


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    goal: str = Field(default="", max_length=1800)
    document_ids: list[str] = Field(default_factory=list, max_length=500)

    @field_validator("title")
    @classmethod
    def meaningful_title(cls, value):
        if not value.strip():
            raise ValueError("项目名称不能为空")
        return value.strip()


class ProjectEdit(ProjectInput):
    expected_revision: int = Field(ge=1)
    archived: bool = False
    artifact_ids: list[str] = Field(default_factory=list, max_length=1000)


def row_for(conn, identifier):
    row = conn.execute("SELECT * FROM projects WHERE id=?", (identifier,)).fetchone()
    if row is None:
        raise KeyError(identifier)
    return dict(row)


def context(identifier, active=True):
    with store.connection() as conn:
        conn.execute("BEGIN")
        result = row_for(conn, identifier)
        if active and result["archived"]:
            raise HTTPException(409, "项目已归档，请先恢复项目")
        result["document_ids"] = [
            r[0]
            for r in conn.execute(
                "SELECT document_id FROM project_documents JOIN documents ON id=document_id WHERE project_id=? AND archived=0 ORDER BY document_id",
                (identifier,),
            )
        ]
    return result


def validate_scope(identifier, ids, require_sources=True):
    project = context(identifier)
    if require_sources and not ids:
        raise ValueError("项目任务需要明确选择文献，不会自动扩大到全库")
    if not set(ids).issubset(project["document_ids"]):
        raise ValueError("所选文献不在项目中或已归档，请回到项目更新文献范围")
    project["source_document_ids"] = list(dict.fromkeys(ids))
    return project


def validate_documents(conn, ids, previous=()):
    for identifier in dict.fromkeys(ids):
        row = conn.execute(
            "SELECT archived FROM documents WHERE id=?", (identifier,)
        ).fetchone()
        if row is None:
            raise KeyError(identifier)
        if row[0] and identifier not in previous:
            raise ValueError("不能加入已归档的文献，请先恢复文献")


@router.get("")
def listing():
    with store.connection() as conn:
        return [
            dict(r)
            for r in conn.execute("""
          SELECT p.*,
          (SELECT COUNT(*) FROM project_documents WHERE project_id=p.id) AS document_count,
          (SELECT COUNT(*) FROM project_artifacts WHERE project_id=p.id) AS artifact_count
          FROM projects p ORDER BY archived,updated_at DESC,id
        """)
        ]


@router.post("")
def create(body: ProjectInput):
    identifier = uuid.uuid4().hex
    with store.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        validate_documents(conn, body.document_ids)
        conn.execute(
            "INSERT INTO projects(id,title,goal) VALUES(?,?,?)",
            (identifier, body.title, body.goal.strip()),
        )
        conn.executemany(
            "INSERT INTO project_documents VALUES(?,?)",
            [(identifier, d) for d in dict.fromkeys(body.document_ids)],
        )
    return detail(identifier)


def snapshot(conn, identifier):
    project = row_for(conn, identifier)
    project["documents"] = [
        dict(r)
        for r in conn.execute(
            """
      SELECT d.id,d.title,d.name,d.pages,d.version,d.status,d.archived FROM documents d
      JOIN project_documents p ON p.document_id=d.id WHERE p.project_id=? ORDER BY d.title,d.version DESC
    """,
            (identifier,),
        )
    ]
    project["document_ids"] = [d["id"] for d in project["documents"]]
    project["notes"] = [
        {**dict(r), "bbox": json.loads(r["bbox"])}
        for r in conn.execute(
            """
      SELECT n.id,n.note,n.quote,n.block_id,b.document_id,b.page,b.bbox,b.width,b.height,d.title,d.version
      FROM evidence_notes n JOIN blocks b ON b.id=n.block_id JOIN documents d ON d.id=b.document_id
      JOIN project_documents p ON p.document_id=d.id WHERE p.project_id=? AND n.archived=0 ORDER BY n.id DESC
    """,
            (identifier,),
        )
    ]
    project["artifacts"] = [
        dict(r)
        for r in conn.execute(
            """
      SELECT a.id,a.title,a.kind,a.created_at FROM artifacts a JOIN project_artifacts p ON p.artifact_id=a.id
      WHERE p.project_id=? ORDER BY a.created_at DESC,a.id
    """,
            (identifier,),
        )
    ]
    project["research_tasks"] = research_tasks.snapshot(conn, identifier)
    project["jobs"] = [
        dict(r)
        for r in conn.execute(
            """
      SELECT id,kind,state,progress,message,error,created_at FROM jobs
      WHERE json_extract(payload,'$.project_id')=? ORDER BY created_at DESC,id LIMIT 25
    """,
            (identifier,),
        )
    ]
    return project


@router.get("/{identifier}")
def detail(identifier: str):
    with store.connection() as conn:
        conn.execute("BEGIN")
        return snapshot(conn, identifier)


@router.patch("/{identifier}")
def edit(identifier: str, body: ProjectEdit):
    with store.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        project = row_for(conn, identifier)
        if project["revision"] != body.expected_revision:
            raise HTTPException(
                409,
                "项目已在其他页面更新。请先刷新项目，再重新应用修改；当前草稿仍保留",
            )
        previous = [
            r[0]
            for r in conn.execute(
                "SELECT document_id FROM project_documents WHERE project_id=?",
                (identifier,),
            )
        ]
        validate_documents(conn, body.document_ids, previous)
        for artifact_id in body.artifact_ids:
            if (
                conn.execute(
                    "SELECT 1 FROM artifacts WHERE id=?", (artifact_id,)
                ).fetchone()
                is None
            ):
                raise KeyError(artifact_id)
        conn.execute(
            "UPDATE projects SET title=?,goal=?,archived=?,revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (body.title, body.goal.strip(), int(body.archived), identifier),
        )
        conn.execute("DELETE FROM project_documents WHERE project_id=?", (identifier,))
        conn.executemany(
            "INSERT INTO project_documents VALUES(?,?)",
            [(identifier, d) for d in dict.fromkeys(body.document_ids)],
        )
        conn.execute("DELETE FROM project_artifacts WHERE project_id=?", (identifier,))
        conn.executemany(
            "INSERT INTO project_artifacts VALUES(?,?)",
            [(identifier, a) for a in dict.fromkeys(body.artifact_ids)],
        )
    return detail(identifier)


@router.get("/{identifier}/export")
def export(identifier: str):
    return Response(
        json.dumps(detail(identifier), ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="project-{identifier}.json"'
        },
    )


@router.get("/{identifier}/bundle")
def bundle(identifier: str):
    """Export a consistent read snapshot; no model calls or source mutation."""
    with store.connection() as conn:
        conn.execute("BEGIN")
        project = snapshot(conn, identifier)
        artifacts = []
        for row in conn.execute(
            "SELECT a.* FROM artifacts a JOIN project_artifacts p ON p.artifact_id=a.id WHERE p.project_id=? ORDER BY a.id",
            (identifier,),
        ):
            item = dict(row)
            item["content"] = json.loads(item["content"])
            artifacts.append(item)
        notes = [
            dict(row)
            for row in conn.execute(
                "SELECT n.*,b.document_id,b.page,b.bbox,b.width,b.height FROM evidence_notes n JOIN blocks b ON b.id=n.block_id JOIN project_documents p ON p.document_id=b.document_id WHERE p.project_id=? ORDER BY n.id",
                (identifier,),
            )
        ]
        for note in notes:
            note["bbox"] = json.loads(note["bbox"])
            note["history"] = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM note_history WHERE note_id=? ORDER BY id",
                    (note["id"],),
                )
            ]
        project_jobs = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM jobs WHERE json_extract(payload,'$.project_id')=? ORDER BY rowid",
                (identifier,),
            )
        ]
        for job in project_jobs:
            for key in ("payload", "result"):
                if job[key]:
                    job[key] = json.loads(job[key])
        comparisons = [
            boundaries.read(i, conn)
            for i in sorted({t["comparison_id"] for t in project["research_tasks"]})
        ]
    files = {}

    def add(name, value):
        files[name] = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")

    add("project.json", project)
    add("research_tasks.json", project["research_tasks"])
    add("evidence_comparisons.json", comparisons)
    add("notes.json", notes)
    add("jobs.json", project_jobs)
    artifact_index = []
    for index, item in enumerate(artifacts, 1):
        name = f"artifacts/{index:04d}.json"
        add(name, item)
        artifact_index.append({"id": item["id"], "title": item["title"], "file": name})
    add("artifacts/index.json", artifact_index)
    files["README.txt"] = (
        "研证项目成果包 / ScholarTrace project bundle\n"
        "project.json：项目目标、文献元数据、活跃笔记和成果索引。\n"
        "notes.json：关联文献的全部证据笔记（含归档状态、编辑历史和原始引用）。\n"
        "jobs.json：本项目全部任务的持久化状态、输入和结果。\n"
        "research_tasks.json：人工补查待办、处理历史与完成时的证据。\n"
        "evidence_comparisons.json：这些待办关联对照表的当前快照。\n"
        "artifacts/：已关联成果的完整 JSON，包含已保存正文及修订历史。\n"
        "manifest.json：文件大小与 SHA-256 校验。\n"
        "不含 PDF 原文件、外部模型、外部链接文件或未保存的页面草稿。\n"
        "这是可审阅的成果快照，不是整站备份或一键恢复包。模型判断仍需核对原文。\n"
    ).encode()
    add(
        "manifest.json",
        {
            "format": "scholartrace-project-bundle-v1",
            "exported_at": datetime.now(UTC).isoformat(),
            "project_id": identifier,
            "artifact_count": len(artifacts),
            "note_count": len(notes),
            "job_count": len(project_jobs),
            "excludes": ["source PDFs", "external files", "models", "unsaved drafts"],
            "files": [
                {
                    "name": name,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
                for name, data in files.items()
            ],
        },
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return Response(
        output.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="scholartrace-project.zip"'
        },
    )
