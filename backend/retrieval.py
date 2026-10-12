"""Local multilingual embeddings + BM25; reciprocal-rank fusion and coverage rerank."""

import asyncio
from collections import defaultdict
import threading
import numpy as np
from . import store, jobs

MODEL = "paraphrase-multilingual-MiniLM-L12-v2/quint8-avx2"
FOLDER = store.ROOT / "models/multilingual-minilm"
_runtime = None
_lock = threading.Lock()


def available():
    return (FOLDER / "model_quint8_avx2.onnx").exists() and (
        FOLDER / "tokenizer.json"
    ).exists()


def embed(texts):
    global _runtime
    import onnxruntime as ort
    from tokenizers import Tokenizer

    with _lock:
        if _runtime is None:
            options = ort.SessionOptions()
            options.intra_op_num_threads = 4
            options.inter_op_num_threads = 1
            runtime = ort.InferenceSession(
                str(FOLDER / "model_quint8_avx2.onnx"),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
            tokenizer = Tokenizer.from_file(str(FOLDER / "tokenizer.json"))
            tokenizer.enable_truncation(max_length=256)
            tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
            _runtime = (runtime, tokenizer)
        runtime, tokenizer = _runtime
        encoded = tokenizer.encode_batch(texts)
        arrays = {
            "input_ids": np.array([e.ids for e in encoded], dtype=np.int64),
            "attention_mask": np.array(
                [e.attention_mask for e in encoded], dtype=np.int64
            ),
            "token_type_ids": np.array([e.type_ids for e in encoded], dtype=np.int64),
        }
        result = runtime.run(
            None, {i.name: arrays[i.name] for i in runtime.get_inputs()}
        )[0]
        if result.ndim == 3:
            mask = arrays["attention_mask"][..., None]
            result = (result * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1)
        result = np.asarray(result, dtype=np.float32)
        return result / np.maximum(np.linalg.norm(result, axis=1, keepdims=True), 1e-9)


def index_batch(rows):
    values = embed([row["text"] for row in rows])
    with store.connection() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO vectors VALUES(?,?,?)",
            [(row["id"], MODEL, vector.tobytes()) for row, vector in zip(rows, values)],
        )


@jobs.register("index")
async def index(ctx, payload):
    if not available():
        raise ValueError("请先安装本地多语言向量模型")
    ids = payload.get("document_ids", [])
    query = "SELECT b.id,b.text FROM blocks b JOIN documents d ON b.document_id=d.id LEFT JOIN vectors v ON v.block_id=b.id AND v.model=? WHERE v.block_id IS NULL AND d.archived=0"
    params = [MODEL]
    if ids:
        query += " AND b.document_id IN (" + ",".join("?" for _ in ids) + ")"
        params += ids
    with store.connection() as conn:
        rows = [dict(r) for r in conn.execute(query, params)]
    for offset in range(0, len(rows), 16):
        ctx.progress(offset / max(1, len(rows)), f"语义索引 {offset}/{len(rows)} 段")
        await asyncio.to_thread(index_batch, rows[offset : offset + 16])
    return {"indexed": len(rows), "model": MODEL}


def dense(question, document_ids, limit=35):
    if not available():
        return []
    query = "SELECT b.*,d.title,d.name,d.version,v.vector FROM vectors v JOIN blocks b ON b.id=v.block_id JOIN documents d ON d.id=b.document_id WHERE v.model=? AND d.archived=0"
    params = [MODEL]
    if document_ids:
        query += " AND b.document_id IN (" + ",".join("?" for _ in document_ids) + ")"
        params += document_ids
    with store.connection() as conn:
        rows = list(conn.execute(query, params))
    if not rows:
        return []
    vector = embed([question])[0]
    matrix = np.vstack([np.frombuffer(r["vector"], dtype=np.float32) for r in rows])
    scores = matrix @ vector
    order = np.argsort(scores)[-limit:][::-1]
    result = []
    for i in order:
        value = store.decode_block(rows[i])
        value.pop("vector")
        value["dense_score"] = round(float(scores[i]), 5)
        result.append(value)
    return result


def search(question, document_ids=None, limit=10):
    ids = document_ids or []
    if len(ids) > 1:
        lexical = [
            b
            for identifier in ids
            for b in store.search(question, [identifier], limit=8)
        ]
        semantic = [
            b for identifier in ids for b in dense(question, [identifier], limit=8)
        ]
        semantic.sort(key=lambda b: b["dense_score"], reverse=True)
        lexical.sort(key=lambda b: b.get("score", 0))
    else:
        lexical = store.search(question, ids, limit=35)
        semantic = dense(question, ids)
    scores = defaultdict(float)
    blocks = {}
    for weight, ranked in [(1, lexical), (1, semantic)]:
        for rank, block in enumerate(ranked):
            blocks.setdefault(block["id"], {}).update(block)
            scores[block["id"]] += weight / (40 + rank)
    terms = store.query_terms(question)
    for identifier, block in blocks.items():
        explicit = sum(t.lower() in block["text"].lower() for t in terms if t.isascii())
        scores[identifier] += min(explicit, 6) * 0.0005
        block["retrieval_score"] = round(scores[identifier], 6)
    ranked = sorted(blocks.values(), key=lambda b: scores[b["id"]], reverse=True)
    if len(ids) > 1:
        balanced = []
        for identifier in ids:
            balanced.extend(
                [b for b in ranked if b["document_id"] == identifier][
                    : max(1, limit // len(ids))
                ]
            )
        seen = {b["id"] for b in balanced}
        ranked = balanced + [b for b in ranked if b["id"] not in seen]
    return ranked[:limit]


def status():
    with store.connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM vectors WHERE model=?", (MODEL,)
        ).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
    return {
        "available": available(),
        "indexed_blocks": count,
        "total_blocks": total,
        "model": MODEL,
        "method": "BM25 + multilingual embeddings + reciprocal rank fusion + term coverage",
    }
