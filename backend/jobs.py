"""Durable, resumable work queue with cancellation and real execution events."""

import asyncio
import json
import traceback
import uuid
from . import store

handlers = {}
workers = set()
active = set()
gate = asyncio.Semaphore(2)


class Cancelled(Exception):
    pass


def register(kind):
    def decorate(function):
        handlers[kind] = function
        return function

    return decorate


def decode(row):
    value = dict(row)
    for key in ["payload", "result"]:
        if value.get(key):
            value[key] = json.loads(value[key])
    return value


def get(identifier):
    with store.connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone()
    if not row:
        raise KeyError(identifier)
    return decode(row)


def listing():
    with store.connection() as conn:
        return [
            decode(r)
            for r in conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT 100"
            )
        ]


def event(identifier, kind, message, data=None):
    with store.connection() as conn:
        conn.execute(
            "INSERT INTO job_events(job_id,kind,message,data) VALUES(?,?,?,?)",
            (
                identifier,
                kind,
                message,
                json.dumps(data, ensure_ascii=False) if data is not None else None,
            ),
        )


class Context:
    def __init__(self, identifier):
        self.id = identifier

    def check(self):
        if get(self.id)["cancel_requested"]:
            raise Cancelled()

    def progress(self, fraction, message):
        self.check()
        with store.connection() as conn:
            conn.execute(
                "UPDATE jobs SET progress=?,message=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (max(0, min(1, fraction)), message, self.id),
            )
        event(self.id, "progress", message, {"progress": fraction})

    def log(self, message, data=None):
        self.check()
        event(self.id, "tool", message, data)

    def token(self, text):
        self.check()
        event(self.id, "token", text)


async def run(identifier):
    if identifier in active:
        return
    active.add(identifier)
    try:
        async with gate:
            job = get(identifier)
            if job["state"] not in {"queued", "interrupted"}:
                return
            ctx = Context(identifier)
            ctx.check()
            with store.connection() as conn:
                conn.execute(
                    "UPDATE jobs SET state='running',error=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (identifier,),
                )
            event(identifier, "start", "开始执行 " + job["kind"])
            result = await handlers[job["kind"]](ctx, job["payload"])
            ctx.check()
            with store.connection() as conn:
                conn.execute(
                    "UPDATE jobs SET state='completed',progress=1,result=?,message='已完成',updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (json.dumps(result, ensure_ascii=False), identifier),
                )
            event(identifier, "completed", "任务完成", result)
    except (Cancelled, asyncio.CancelledError) as exc:
        state = "cancelled" if isinstance(exc, Cancelled) else "interrupted"
        with store.connection() as conn:
            conn.execute(
                "UPDATE jobs SET state=?,message=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (
                    state,
                    "已停止" if state == "cancelled" else "等待重启恢复",
                    identifier,
                ),
            )
        if isinstance(exc, asyncio.CancelledError):
            raise
    except Exception as exc:
        message = str(exc)[:1500] or type(exc).__name__
        with store.connection() as conn:
            conn.execute(
                "UPDATE jobs SET state='failed',error=?,message='执行失败，可重试',updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (message, identifier),
            )
        event(identifier, "error", message)
        traceback.print_exc()
    finally:
        active.discard(identifier)


def schedule(identifier):
    task = asyncio.create_task(run(identifier))
    workers.add(task)
    task.add_done_callback(workers.discard)


def submit(kind, payload):
    if kind not in handlers:
        raise ValueError("未知任务类型")
    identifier = uuid.uuid4().hex
    with store.connection() as conn:
        conn.execute(
            "INSERT INTO jobs(id,kind,payload) VALUES(?,?,?)",
            (identifier, kind, json.dumps(payload, ensure_ascii=False)),
        )
    schedule(identifier)
    return get(identifier)


def retry(identifier):
    job = get(identifier)
    if job["state"] not in {"failed", "cancelled", "interrupted"}:
        raise ValueError("仅失败或停止的任务可以重试")
    with store.connection() as conn:
        conn.execute(
            "UPDATE jobs SET state='queued',cancel_requested=0,error=NULL WHERE id=?",
            (identifier,),
        )
    schedule(identifier)
    return get(identifier)


async def resume():
    with store.connection() as conn:
        conn.execute("UPDATE jobs SET state='interrupted' WHERE state='running'")
        rows = list(
            conn.execute(
                "SELECT id FROM jobs WHERE state IN ('queued','interrupted') AND cancel_requested=0"
            )
        )
    for row in rows:
        schedule(row[0])


async def shutdown():
    tasks = list(workers)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
