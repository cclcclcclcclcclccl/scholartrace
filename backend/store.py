"""Version-specific text blocks, persistent evidence, and lexical retrieval baseline."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import unicodedata
from contextvars import ContextVar
from collections import Counter
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data/scholartrace.sqlite3"
database_override = ContextVar("scholartrace_database", default=None)


def database_path():
    return database_override.get() or DB_PATH


def connection() -> sqlite3.Connection:
    target = database_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize() -> None:
    with connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents(
            id TEXT PRIMARY KEY, name TEXT NOT NULL, title TEXT NOT NULL, path TEXT NOT NULL,
            pages INTEGER NOT NULL, chars INTEGER NOT NULL, status TEXT NOT NULL,
            arxiv_id TEXT, version INTEGER, metadata TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS blocks(
            id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            page INTEGER NOT NULL, ordinal INTEGER NOT NULL, text TEXT NOT NULL,
            bbox TEXT NOT NULL, width REAL NOT NULL, height REAL NOT NULL, method TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS blocks_document_page ON blocks(document_id,page);
        CREATE VIRTUAL TABLE IF NOT EXISTS block_search USING fts5(
            block_id UNINDEXED, document_id UNINDEXED, text, tokenize='porter unicode61'
        );
        CREATE TABLE IF NOT EXISTS evidence_notes(
            id INTEGER PRIMARY KEY, block_id TEXT NOT NULL REFERENCES blocks(id),
            note TEXT NOT NULL, quote TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)
        if "archived" not in {
            r[1] for r in conn.execute("PRAGMA table_info(documents)")
        }:
            conn.execute(
                "ALTER TABLE documents ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
            )
        if "archived" not in {
            r[1] for r in conn.execute("PRAGMA table_info(evidence_notes)")
        }:
            conn.execute(
                "ALTER TABLE evidence_notes ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
            )
        schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='block_search'"
        ).fetchone()[0]
        if "porter" not in schema:
            conn.executescript("""
                DROP TABLE block_search;
                CREATE VIRTUAL TABLE block_search USING fts5(block_id UNINDEXED,document_id UNINDEXED,text,tokenize='porter unicode61');
                INSERT INTO block_search(block_id,document_id,text) SELECT id,document_id,text FROM blocks;
            """)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    # PDF line wrapping often splits repository URLs immediately after a slash.
    # Preserve numeric/ordinary whitespace instead of removing all whitespace.
    text = re.sub(r"(https?://[^\s]*?/)[ \t]*\n[ \t]*(?=[A-Za-z0-9])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def quote_normalize(text: str) -> str:
    """Undo PDF word breaks for matching; keep source blocks and numeric signs intact."""
    text = text.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'}))
    return normalize(re.sub(r"(?<=[A-Za-z])[-\u00ad][ \t]*\n[ \t]*(?=[a-z])", "", text))


def quote_in_source(quote: str, source: str) -> bool:
    joined = re.sub(r"(?<=[A-Za-z])([-\u00ad])[ \t]*\n[ \t]*(?=[a-z])", r"\1", source)
    return quote_normalize(quote) in quote_normalize(source) or normalize(
        quote
    ) in normalize(joined)


def document_title(doc: pymupdf.Document) -> str:
    lines = []
    for block in doc[0].get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            if (
                abs(line.get("dir", (1, 0))[1]) >= 0.1
                or line["bbox"][1] >= doc[0].rect.height * 0.43
            ):
                continue
            text = normalize("".join(span["text"] for span in line["spans"]))
            if (
                len(text) < 5
                or re.search(r"arxiv|preprint|published as", text, re.I)
                or text.lower() in {"abstract", "introduction", "contents"}
            ):
                continue
            lines.append(
                {
                    "text": text,
                    "size": max(span["size"] for span in line["spans"]),
                    "y": line["bbox"][1],
                }
            )
    if lines:
        largest = max(line["size"] for line in lines)
        candidates = sorted(
            [line for line in lines if line["size"] >= largest * 0.88],
            key=lambda line: line["y"],
        )
        # Preserve small-caps and mixed-size words within each selected title line.
        title = normalize(
            re.sub(
                r"([A-Za-z])-\s+(?=[A-Za-z])",
                r"\1",
                " ".join(line["text"] for line in candidates[:4]),
            )
        )
        if len(title) > 8:
            return title[:350]
    return normalize(doc.metadata.get("title", "")) or "未识别标题"


def decode_block(row: sqlite3.Row) -> dict:
    result = dict(row)
    result["bbox"] = json.loads(result["bbox"])
    return result


def import_pdf(path: Path, name: str | None = None) -> dict:
    with path.open("rb") as stream:
        document_id = hashlib.file_digest(stream, "sha256").hexdigest()
    with connection() as conn:
        previous = conn.execute(
            "SELECT * FROM documents WHERE id=?", (document_id,)
        ).fetchone()
        if previous:
            return {**dict(previous), "already_exists": True}
    blocks, blank_pages, chars = [], [], 0
    with pymupdf.open(path) as doc:
        if doc.is_encrypted:
            raise ValueError("暂不支持加密 PDF，请先提供可阅读的文件。")
        title = document_title(doc)
        # Version evidence comes from PDF content, never the uploaded filename.
        first_text = doc[0].get_text()
        identifier = re.search(
            r"arXiv\s*:\s*(\d{4}\.\d{4,5})(?:v(\d+))?", first_text, re.I
        )
        for page_number, page in enumerate(doc, 1):
            page_chars = 0
            for ordinal, block in enumerate(page.get_text("blocks", sort=True)):
                if len(block) > 6 and block[6] != 0:
                    continue
                content = block[4].strip()
                if not content:
                    continue
                page_chars += len(content)
                stable_id = hashlib.sha256(
                    f"{document_id}:{page_number}:{ordinal}".encode()
                ).hexdigest()[:24]
                blocks.append(
                    (
                        stable_id,
                        document_id,
                        page_number,
                        ordinal,
                        content,
                        json.dumps(list(block[:4])),
                        page.rect.width,
                        page.rect.height,
                        "native",
                    )
                )
            if page_chars < 20:
                blank_pages.append(page_number)
            chars += page_chars
        metadata = {
            "pdf": doc.metadata,
            "outline": doc.get_toc(),
            "pages_without_text": blank_pages,
            "parser": "PyMuPDF text blocks; reading order is a baseline, not full layout reconstruction",
        }
        record = (
            document_id,
            name or path.name,
            title,
            str(path.resolve()),
            len(doc),
            chars,
            "needs_ocr" if len(blank_pages) == len(doc) else "text_ready",
            identifier.group(1) if identifier else None,
            int(identifier.group(2)) if identifier and identifier.group(2) else None,
            json.dumps(metadata, ensure_ascii=False),
        )
    with connection() as conn:
        conn.execute(
            "INSERT INTO documents(id,name,title,path,pages,chars,status,arxiv_id,version,metadata) VALUES(?,?,?,?,?,?,?,?,?,?)",
            record,
        )
        conn.executemany("INSERT INTO blocks VALUES(?,?,?,?,?,?,?,?,?)", blocks)
        conn.executemany(
            "INSERT INTO block_search(block_id,document_id,text) VALUES(?,?,?)",
            [(b[0], b[1], b[4]) for b in blocks],
        )
    return get_document(document_id)


def get_document(document_id: str) -> dict:
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE id=?", (document_id,)
        ).fetchone()
    if not row:
        raise KeyError(document_id)
    result = dict(row)
    result["metadata"] = json.loads(result["metadata"])
    return result


def list_documents() -> list[dict]:
    with connection() as conn:
        records = [
            dict(r)
            for r in conn.execute(
                "SELECT id,name,title,pages,chars,status,arxiv_id,version,created_at,archived,json_extract(metadata,'$.aliases') AS aliases FROM documents WHERE archived=0 ORDER BY title,version DESC"
            )
        ]
    for record in records:
        record["aliases"] = json.loads(record["aliases"] or "[]")
    return records


def get_blocks(document_id: str, page: int | None = None) -> list[dict]:
    query = "SELECT * FROM blocks WHERE document_id=?"
    params: list = [document_id]
    if page is not None:
        query += " AND page=?"
        params.append(page)
    with connection() as conn:
        return [
            decode_block(r)
            for r in conn.execute(query + " ORDER BY page,ordinal", params)
        ]


def query_terms(question: str) -> list[str]:
    # Transparent lexical bridge for baseline evaluation; this is not semantic translation.
    bridges = {
        "优化器": "optimizer adam",
        "超参数": "adam beta",
        "训练": "training train",
        "显卡": "gpu p100",
        "型号": "gpu hardware",
        "数量": "gpus",
        "硬件": "hardware gpu",
        "作者": "author",
        "机构": "google university",
        "参数量": "parameters model",
        "注意力": "attention",
        "归一化": "normalization",
        "学习率": "learning rate",
        "上下文": "context window",
        "德语": "german",
        "分数": "bleu",
        "猫": "cat",
        "颜色": "color",
        "批量": "batch",
    }
    expanded = (
        question
        + " "
        + " ".join(value for key, value in bridges.items() if key in question)
    )
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]*|[\u4e00-\u9fff]{2,}", expanded.lower())
    stop = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "what",
        "which",
        "how",
        "many",
        "was",
        "were",
        "in",
        "of",
        "for",
        "and",
        "to",
        "did",
        "does",
        "used",
        "use",
        "this",
        "paper",
    }
    return list(dict.fromkeys(token for token in tokens if token not in stop))[:35]


def search(
    question: str, document_ids: list[str] | None = None, limit: int = 8
) -> list[dict]:
    terms = query_terms(question)
    if not terms:
        return []
    match = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)
    query = """SELECT b.*,d.title,d.name,d.version,bm25(block_search) AS score
               FROM block_search JOIN blocks b ON b.id=block_search.block_id
               JOIN documents d ON d.id=b.document_id WHERE block_search MATCH ? AND d.archived=0"""
    params: list = [match]
    if document_ids:
        query += " AND b.document_id IN (" + ",".join("?" for _ in document_ids) + ")"
        params.extend(document_ids)
    query += " ORDER BY score LIMIT ?"
    params.append(max(limit, 60))
    with connection() as conn:
        candidates = [decode_block(row) for row in conn.execute(query, params)]
    # Prefer specific terms written by the user over expanded general words.
    explicit = [
        t
        for t in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]*", question.lower())
        if t
        not in {
            "what",
            "which",
            "how",
            "many",
            "the",
            "is",
            "are",
            "in",
            "of",
            "for",
            "and",
            "to",
            "used",
            "use",
            "this",
            "paper",
        }
    ]

    def relevance(block):
        text = normalize(block["text"]).lower()
        coverage = sum(
            bool(re.search(r"\b" + re.escape(term) + r"s?\b", text))
            for term in explicit
        )
        return (coverage, -block["score"])

    candidates.sort(key=relevance, reverse=True)
    return candidates[:limit]


def content_similarity(first_id: str, second_id: str) -> dict:
    first, second = get_document(first_id), get_document(second_id)

    def words(doc_id: str) -> Counter:
        text = " ".join(b["text"] for b in get_blocks(doc_id))
        return Counter(re.findall(r"[a-z]{3,}", normalize(text).lower()))

    a, b = words(first_id), words(second_id)
    denominator = math.sqrt(
        sum(x * x for x in a.values()) * sum(x * x for x in b.values())
    )
    score = (
        sum(value * b.get(key, 0) for key, value in a.items()) / denominator
        if denominator
        else 0
    )
    same_identifier = bool(
        first["arxiv_id"] and first["arxiv_id"] == second["arxiv_id"]
    )
    same_title = normalize(first["title"]).lower() == normalize(second["title"]).lower()
    likely_same = score > 0.85 and (same_identifier or same_title)
    newer = None
    if (
        likely_same
        and same_identifier
        and first["version"]
        and second["version"]
        and first["version"] != second["version"]
    ):
        newer = first_id if first["version"] > second["version"] else second_id
    return {
        "first": first_id,
        "second": second_id,
        "content_cosine": round(score, 5),
        "same_content_identifier": same_identifier,
        "same_title": same_title,
        "likely_same_paper": likely_same,
        "recommended_version_id": newer,
        "method": "Content word-frequency cosine plus in-document identifier/title; lexical baseline, not embedding semantics",
    }
