"""Trace saved artifact claims into later paper versions without rewriting history."""

import asyncio
import json
import re
from difflib import SequenceMatcher
import httpx
from . import store, jobs, research, audit, model
from .review import review_change


def claims_in(value):
    if isinstance(value, dict):
        if all(k in value for k in ["block_id", "text", "quote", "document_id"]):
            yield value
        for child in value.values():
            yield from claims_in(child)
    elif isinstance(value, list):
        for child in value:
            yield from claims_in(child)


def align(claim, target_id):
    candidates = store.get_blocks(target_id)
    quote = store.quote_normalize(claim["quote"]).lower()
    tokens = set(re.findall(r"\w+", quote))
    ranked = sorted(
        candidates,
        key=lambda b: (
            len(tokens & set(re.findall(r"\w+", b["text"].lower())))
            / max(1, len(tokens | set(re.findall(r"\w+", b["text"].lower()))))
        ),
        reverse=True,
    )[:8]
    scores = [
        (
            1.0
            if store.quote_in_source(claim["quote"], b["text"])
            else SequenceMatcher(
                None, quote, store.normalize(b["text"]).lower(), autojunk=False
            ).ratio(),
            b,
        )
        for b in ranked
    ]
    best = max(scores, key=lambda x: x[0]) if scores else (0, None)
    status = (
        "retained"
        if best[0] > 0.999
        else "review_required"
        if best[0] >= 0.4
        else "unlocated"
    )
    note = {
        **claim,
        "note": claim["text"],
        "id": claim.get("block_id"),
        "title": store.get_document(claim["document_id"])["title"],
    }
    return {
        "note": note,
        "status": status,
        "similarity": best[0],
        "candidate": best[1],
        "explanation": "原文块保留"
        if status == "retained"
        else "找到变化候选，请检查该成果中的论断是否仍成立"
        if status == "review_required"
        else "未可靠定位对应原文；不等于已删除",
    }


@jobs.register("impact")
async def impact(ctx, payload):
    target = store.get_document(payload["document_id"])
    sources = {}
    for doc in store.list_documents():
        if doc["id"] != target["id"] and (
            (target["arxiv_id"] and doc["arxiv_id"] == target["arxiv_id"])
            or research.normalized_title(doc["title"])
            == research.normalized_title(target["title"])
        ):
            sources[doc["id"]] = doc
    with store.connection() as conn:
        items = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM artifacts WHERE kind IN ('answer','review','writing','future','agent') ORDER BY created_at DESC"
            )
        ]
    dependencies = []
    seen = set()
    for item in items:
        for claim in claims_in(json.loads(item["content"])):
            key = (item["id"], claim["block_id"], claim["text"])
            if claim["document_id"] not in sources or key in seen:
                continue
            seen.add(key)
            dependencies.append((item, claim))
    results = []
    for i, (item, claim) in enumerate(dependencies[:30]):
        ctx.progress(
            i / max(1, min(30, len(dependencies))),
            f"复核成果依赖 {i + 1}/{min(30, len(dependencies))}",
        )
        aligned = await asyncio.to_thread(align, claim, target["id"])
        if aligned["candidate"]:
            async with model.gate:
                async with httpx.AsyncClient(timeout=80, trust_env=False) as client:
                    aligned["semantic_review"] = await review_change(
                        aligned, client, model.URL, model.NAME
                    )
        results.append(
            {"artifact_id": item["id"], "artifact_title": item["title"], **aligned}
        )
    return research.save_artifact(
        "impact",
        "论文更新对已有成果的影响",
        {
            "target": {
                "id": target["id"],
                "title": target["title"],
                "version": target["version"],
            },
            "impact": results,
            "total_dependencies": len(dependencies),
            "checked": len(results),
            "notice": "复核保存过的综述、方案与 Agent 成果中的引用依赖。历史成果不改写；一次最多核验 30 条，模型含义判断仍需人工确认。",
        },
    )


def version_diff(first, second):
    relation = store.content_similarity(first, second)
    if not relation["likely_same_paper"]:
        raise ValueError("请选择同一论文的两个版本")
    old = store.get_blocks(first)
    new = store.get_blocks(second)
    old_text = [store.quote_normalize(b["text"]) for b in old]
    new_text = [store.quote_normalize(b["text"]) for b in new]
    matcher = SequenceMatcher(None, old_text, new_text, autojunk=False)
    changes = []
    for tag, a, b, c, d in matcher.get_opcodes():
        if tag == "equal":
            continue
        # Joining adjacent PDF blocks avoids reporting a mere split/merge as a content change.
        before = store.normalize(" ".join(old_text[a:b]))
        after = store.normalize(" ".join(new_text[c:d]))
        if before == after:
            continue
        changes.append(
            {
                "kind": tag,
                "before": old[a:b],
                "after": new[c:d],
                "similarity": SequenceMatcher(
                    None, before, after, autojunk=False
                ).ratio()
                if len(before) + len(after) < 30000
                else None,
            }
        )
    return {
        "first": first,
        "second": second,
        "changes": changes,
        "notice": "以规范化文字块比较，保留两侧出处；拆段、改写和重排仍可能混合出现，不能把所有差异等同于科研结论变化。",
    }
