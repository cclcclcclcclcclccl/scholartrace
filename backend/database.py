"""Additive schemas; original documents and evidence remain immutable."""

import json
from . import store


def initialize():
    store.initialize()
    with store.connection() as conn:
        columns = {r[1] for r in conn.execute("PRAGMA table_info(documents)")}
        if "archived" not in columns:
            conn.execute(
                "ALTER TABLE documents ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
            )
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs(
          id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'queued', progress REAL NOT NULL DEFAULT 0,
          message TEXT NOT NULL DEFAULT '', result TEXT, error TEXT,
          cancel_requested INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS job_events(
          id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
          kind TEXT NOT NULL, message TEXT NOT NULL, data TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS structures(document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE, content TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS translations(block_id TEXT NOT NULL REFERENCES blocks(id), language TEXT NOT NULL, text TEXT NOT NULL, model TEXT NOT NULL, PRIMARY KEY(block_id,language));
        CREATE TABLE IF NOT EXISTS vectors(block_id TEXT PRIMARY KEY REFERENCES blocks(id) ON DELETE CASCADE, model TEXT NOT NULL, vector BLOB NOT NULL);
        CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS preferences(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS remote_papers(id TEXT PRIMARY KEY, data TEXT NOT NULL, fetched_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS feedback(paper_id TEXT PRIMARY KEY,vote INTEGER NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS trackers(id TEXT PRIMARY KEY,query TEXT NOT NULL,interval_hours INTEGER NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,last_checked TEXT,next_check TEXT,error TEXT);
        CREATE TABLE IF NOT EXISTS tracker_hits(tracker_id TEXT NOT NULL,paper_id TEXT NOT NULL,PRIMARY KEY(tracker_id,paper_id));
        CREATE TABLE IF NOT EXISTS edge_feedback(source TEXT NOT NULL,target TEXT NOT NULL,hidden INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(source,target));
        CREATE TABLE IF NOT EXISTS note_history(id INTEGER PRIMARY KEY,note_id INTEGER NOT NULL,previous_text TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS reader_bookmarks(document_id TEXT NOT NULL REFERENCES documents(id),page INTEGER NOT NULL,label TEXT NOT NULL,PRIMARY KEY(document_id,page));
        CREATE TABLE IF NOT EXISTS translation_history(id INTEGER PRIMARY KEY,block_id TEXT NOT NULL REFERENCES blocks(id),language TEXT NOT NULL,text TEXT NOT NULL,model TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """)


def preference(key, default=None):
    with store.connection() as conn:
        row = conn.execute(
            "SELECT value FROM preferences WHERE key=?", (key,)
        ).fetchone()
    return json.loads(row[0]) if row else default


def set_preference(key, value):
    with store.connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO preferences VALUES(?,?)",
            (key, json.dumps(value, ensure_ascii=False)),
        )
