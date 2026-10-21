"""Durable per-paper answers; retry resumes completed papers without regenerating them."""

import json

from . import jobs, research, store


def checkpoints(identifier):
    job = jobs.get(identifier)
    if job["kind"] != "ask":
        raise ValueError("该任务不是后台问答")
    with store.connection() as conn:
        saved = {
            r[0]: json.loads(r[1])
            for r in conn.execute(
                "SELECT document_id,content FROM answer_checkpoints WHERE job_id=?",
                (identifier,),
            )
        }
    return [saved[d] for d in job["payload"]["document_ids"] if d in saved]


class AnswerContext:
    def __init__(self, parent, label):
        self.parent = parent
        self.label = label

    def check(self):
        self.parent.check()

    def log(self, message, data=None):
        self.parent.log(message, data)
        with store.connection() as conn:
            conn.execute(
                "UPDATE jobs SET message=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (self.label + " · " + message, self.parent.id),
            )


@jobs.register("ask")
async def answer(ctx, payload):
    # If the worker stopped after saving the final artifact, reuse it on recovery.
    with store.connection() as conn:
        row = conn.execute(
            "SELECT id FROM artifacts WHERE kind='answer' AND json_extract(content,'$.answer_job_id')=? ORDER BY created_at LIMIT 1",
            (ctx.id,),
        ).fetchone()
    if row:
        return {"id": row[0], "kind": "answer", "title": payload["question"]}
    ids = payload["document_ids"]
    done = {p["document_id"]: p for p in checkpoints(ctx.id)}
    for index, identifier in enumerate(ids):
        ctx.check()
        record = store.get_document(identifier)
        label = f"第 {index + 1}/{len(ids)} 篇：{record['name']}"
        if identifier in done:
            ctx.progress((index + 1) / len(ids) * 0.95, label + " · 已恢复保存结果")
            continue
        ctx.progress(index / len(ids) * 0.95, label + " · 开始取证")
        result = await research.grounded(
            payload["question"], [identifier], AnswerContext(ctx, label)
        )
        # A completed paper is retained even if cancellation arrived at its end.
        section = {
            "title": f"{record['title']}（{record['name']}）",
            "document_id": identifier,
            **result,
        }
        with store.connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO answer_checkpoints(job_id,document_id,content) VALUES(?,?,?)",
                (ctx.id, identifier, json.dumps(section, ensure_ascii=False)),
            )
        done[identifier] = section
        ctx.progress((index + 1) / len(ids) * 0.95, label + " · 本篇结果已保存")
    ctx.check()
    return research.save_artifact(
        "answer",
        payload["question"],
        {
            "answer_job_id": ctx.id,
            "sections": [done[d] for d in ids],
            "notice": "后台逐篇问答，已完成论文结果会保存并用于恢复；未解决项不表示论文没有答案。支持性检查仍为模型初判，请核对原文。",
        },
    )
