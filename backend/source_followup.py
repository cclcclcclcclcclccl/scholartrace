"""Explicit one-block followup with full source validation and no retrieval fallback."""

import hashlib

from fastapi import HTTPException

from . import research, store
from .answer_contract import checklist

NOTICE = "本次只依据你选中的这一段原文，不检索全文或其他论文；段落未说明的内容不能据此认定整篇论文未报告。"


def selected_block(document_ids, block_id, quote):
    if len(document_ids) != 1 or not block_id or not quote:
        raise HTTPException(422, "限定原文补问须选择一篇论文和一段完整原文")
    record = store.get_document(document_ids[0])
    block = next(
        (b for b in store.get_blocks(document_ids[0]) if b["id"] == block_id), None
    )
    if not block:
        raise HTTPException(422, "选中原文不属于当前论文，请重新选择")
    if record.get("archived"):
        raise HTTPException(409, "文献已归档，请恢复后重新选择原文")
    if block["text"] != quote:
        raise HTTPException(409, "原文已变化，请重新选择，避免使用过期摘录")
    if not 12 <= len(quote) <= 4000:
        raise HTTPException(422, "请选择12—4000字的原文段落；过长原文不会被静默截断")
    return {
        **block,
        "title": record["title"],
        "name": record["name"],
        "version": record.get("version"),
    }


def scope(block):
    return {
        "kind": "selected_block",
        "block_id": block["id"],
        "document_id": block["document_id"],
        "page": block["page"],
        "title": block["title"],
        "sha256": hashlib.sha256(block["text"].encode()).hexdigest(),
        "notice": NOTICE,
    }


async def answer(question, block):
    evidence = f"[E1] {block['title']} (p.{block['page']})\n{block['text']}"
    generated = await research.single_answer(
        question, [block["document_id"]], [block], block["title"], evidence
    )
    result = await research.validate_answer(
        question, [block], [], generated, block["title"], original_question=question
    )
    result["source_scope"] = scope(block)
    result["limitations"] = NOTICE + " " + result.get("limitations", "")
    result["answer_checklist"] = checklist(question, result["claims"])
    return result
