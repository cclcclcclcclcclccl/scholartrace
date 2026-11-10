"""Bounded body-vector alignment for review candidates, never automatic deletion."""

from functools import lru_cache
import numpy as np
from . import retrieval, store

MAX_CHUNKS = 48
CHUNK_CHARS = 600
CANDIDATE_THRESHOLD = 0.92
VERSION_THRESHOLD = 0.94


def chunks(identifier):
    all_chunks = []
    for block in store.get_blocks(identifier):
        text = store.normalize(block["text"])
        for offset in range(0, len(text), CHUNK_CHARS):
            part = text[offset:offset + CHUNK_CHARS]
            if len(part.strip()) >= 20:
                all_chunks.append({"block_id": block["id"], "page": block["page"], "text": part})
    total = len(all_chunks)
    if total > MAX_CHUNKS:
        indices = np.linspace(0, total - 1, MAX_CHUNKS, dtype=int)
        all_chunks = [all_chunks[int(i)] for i in indices]
    return all_chunks, total


@lru_cache(maxsize=128)
def _vectors(database, identifier, model_signature, texts):
    # Database identity and exact texts prevent cross-account/stale OCR cache reuse.
    return np.vstack([retrieval.embed(list(texts[i:i + 16])) for i in range(0, len(texts), 16)])


def compare(first, second):
    a, a_total = chunks(first)
    b, b_total = chunks(second)
    result = {
        "semantic_status": "needs_text", "semantic_content_cosine": None,
        "semantic_model": retrieval.MODEL, "semantic_evidence": [],
        "semantic_sample": {"first_used": len(a), "first_total": a_total,
                            "second_used": len(b), "second_total": b_total,
                            "max_chunks": MAX_CHUNKS, "chunk_chars": CHUNK_CHARS},
        "semantic_candidate_threshold": CANDIDATE_THRESHOLD,
        "semantic_alignment_mean": None,
        "semantic_notice": "正文分段向量均值的余弦相似度，另列双向片段对齐分数；抽样相似度不是重复概率，也不能证明结论一致。请逐页核对，不会自动删除文献。",
    }
    if not a or not b:
        return result
    if not retrieval.available():
        result["semantic_status"] = "unavailable"
        return result
    try:
        model_file = retrieval.FOLDER / "model_quint8_avx2.onnx"
        signature = (retrieval.MODEL, model_file.stat().st_mtime_ns if model_file.exists() else 0, id(retrieval.embed))
        database = str(store.database_path().resolve())
        av = _vectors(database, first, signature, tuple(c["text"] for c in a))
        bv = _vectors(database, second, signature, tuple(c["text"] for c in b))
        matrix = np.clip(av @ bv.T, -1, 1)
        if not np.isfinite(matrix).all():
            raise ValueError("Nonfinite embedding")
        alignment = float((matrix.max(axis=1).mean() + matrix.max(axis=0).mean()) / 2)
        ac = av.mean(axis=0)
        bc = bv.mean(axis=0)
        score = float(np.clip(ac @ bc / max(float(np.linalg.norm(ac) * np.linalg.norm(bc)), 1e-9), -1, 1))
        pairs = sorted(((float(matrix[i, j]), i, int(j)) for i, j in enumerate(matrix.argmax(axis=1))), reverse=True)
        seen = set()
        for similarity, i, j in pairs:
            if j in seen:
                continue
            seen.add(j)
            result["semantic_evidence"].append({
                "first_block_id": a[i]["block_id"], "first_page": a[i]["page"], "first_quote": a[i]["text"],
                "second_block_id": b[j]["block_id"], "second_page": b[j]["page"], "second_quote": b[j]["text"],
                "cosine": round(similarity, 5),
            })
            if len(seen) == 3:
                break
        result.update(semantic_status="ready", semantic_content_cosine=round(score, 5), semantic_alignment_mean=round(alignment, 5))
    except (RuntimeError, ValueError, OSError):
        result["semantic_status"] = "error"
    return result
