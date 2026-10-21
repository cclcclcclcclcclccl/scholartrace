"""Immutable account-local snapshots of interactive paper discovery."""

import json

from . import discovery, discovery_tools, store


def save(kind, label, spec, result):
    with store.connection() as c:
        cursor = c.execute(
            "INSERT INTO discovery_history(kind,label,spec,result) VALUES(?,?,?,?)",
            (
                kind,
                label,
                json.dumps(spec, ensure_ascii=False),
                json.dumps(result, ensure_ascii=False),
            ),
        )
    return cursor.lastrowid


def listing(before=0):
    if before < 0:
        raise ValueError("历史游标无效")
    with store.connection() as c:
        rows = [
            dict(r)
            for r in c.execute(
                "SELECT id,kind,label,spec,created_at FROM discovery_history WHERE (?=0 OR id<?) ORDER BY id DESC LIMIT 21",
                (before, before),
            )
        ]
    items = [{**r, "spec": json.loads(r["spec"])} for r in rows[:20]]
    return {"items": items, "next_before": items[-1]["id"] if len(rows) > 20 else None}


def get(identifier):
    with store.connection() as c:
        row = c.execute(
            "SELECT * FROM discovery_history WHERE id=?", (identifier,)
        ).fetchone()
    if not row:
        raise KeyError(identifier)
    record = {
        **dict(row),
        "spec": json.loads(row["spec"]),
        "result": json.loads(row["result"]),
    }
    votes = discovery.feedback_scores()

    def current(papers):
        return [
            {
                **p,
                "vote": votes.get(p["id"], 0),
                "original_retrieval_status": p.get("retrieval_status"),
                "retrieval_status": "snapshot",
            }
            for p in discovery_tools.annotate(papers)
        ]

    if record["kind"] == "search":
        view = current(record["result"])
    else:
        view = {**record["result"], "papers": current(record["result"]["papers"])}
        if record["kind"] == "related":
            docs = {d["id"]: d for d in store.list_documents()}
            view["local"] = [
                {**p, **docs[p["id"]]} for p in view["local"] if p["id"] in docs
            ]
            view["unavailable_local_count"] = len(record["result"]["local"]) - len(
                view["local"]
            )
    return {**record, "view": view}
