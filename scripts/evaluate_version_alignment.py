"""Small source-labelled diagnostic, comparing prior block alignment to current alignment."""

import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import alignment, model, store
from backend.review import review_change

CASES = [
    (
        "code_release",
        "1706.03762v1.pdf",
        "1706.03762v7.pdf",
        "7bb0f16dd5cd6401381edad1",
        "代码尚未发布，计划近期公开。",
        "claim_changed",
    ),
    (
        "abstract_bleu",
        "1706.03762v1.pdf",
        "1706.03762v7.pdf",
        "4246819b6aba05c2b952ec10",
        "摘要报告英法翻译的 BLEU 为 41.0。",
        "claim_changed",
    ),
    (
        "hardware",
        "1706.03762v1.pdf",
        "1706.03762v7.pdf",
        "639c9c52efd933249ef96ecb",
        "使用一台带有八块 NVIDIA P100 GPU 的机器训练。",
        "same_claim",
    ),
    (
        "label_smoothing",
        "1706.03762v1.pdf",
        "1706.03762v7.pdf",
        "0e8e41cdab79517355b79981",
        "标签平滑为 0.1，会损害困惑度但改善 BLEU。",
        "same_claim",
    ),
    (
        "decoder_settings",
        "1706.03762v1.pdf",
        "1706.03762v7.pdf",
        "fc9fce7b872d2fb06fee760d",
        "大模型平均最后 20 个检查点，beam size 为 4。",
        "same_claim",
    ),
    (
        "split_parsing",
        "1706.03762v1.pdf",
        "1706.03762v7.pdf",
        "22e83366fd0c4d70becc3e63",
        "句法分析的最大输出长度为输入长度加 300，beam size 为 21。",
        "same_claim",
    ),
    (
        "encoder",
        "1706.03762v1.pdf",
        "1706.03762v7.pdf",
        "43a91c1dd80d649f28c83e2e",
        "编码器由 6 层组成，输出维度为 512。",
        "same_claim",
    ),
    (
        "body_bleu",
        "1706.03762v1.pdf",
        "1706.03762v7.pdf",
        "52403cee5118549b7cb67ab5",
        "这一正文段落报告英法 BLEU 为 41.0。",
        "same_claim",
    ),
    (
        "warmup",
        "1706.03762v1.pdf",
        "1706.03762v7.pdf",
        "b32f0516ff243ae2920a2e8e",
        "学习率预热步数为 4000。",
        "same_claim",
    ),
    (
        "emergence_abstract",
        "2206.07682v2.pdf",
        "209_Emergent_Abilities_of_Larg.pdf",
        "2daa9ab23e87c96df5099a5d",
        "涌现能力在较小模型中不存在，但在较大模型中存在。",
        "same_claim",
    ),
    (
        "emergence_definition",
        "2206.07682v2.pdf",
        "209_Emergent_Abilities_of_Larg.pdf",
        "2309efe795440349d6ed9013",
        "涌现能力在较小模型中不存在，但在较大模型中存在。",
        "same_claim",
    ),
    (
        "emergence_arithmetic",
        "2206.07682v2.pdf",
        "209_Emergent_Abilities_of_Larg.pdf",
        "a3a8960410e048af0332066d",
        "所述算术基准测试三位数加减及两位数乘法。",
        "same_claim",
    ),
]


def legacy(quote, blocks):
    text = store.normalize(quote).lower()
    words = set(re.findall(r"\w+", text))
    ranked = sorted(
        blocks,
        key=lambda b: (
            len(words & set(re.findall(r"\w+", store.normalize(b["text"]).lower())))
            / max(
                1,
                len(
                    words | set(re.findall(r"\w+", store.normalize(b["text"]).lower()))
                ),
            )
        ),
        reverse=True,
    )[:8]
    score = max(
        (
            SequenceMatcher(
                None, text, store.normalize(b["text"]).lower(), autojunk=False
            ).ratio()
            for b in ranked
        ),
        default=0,
    )
    return (
        "retained"
        if score >= 0.999
        else "review_required"
        if score >= 0.4
        else "unlocated"
    )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", default="artifacts/quality-round2/version-diagnostic.json"
    )
    path = ROOT / parser.parse_args().output
    if path.exists():
        raise SystemExit("Do not overwrite existing version evidence")
    papers = {p["name"]: p for p in store.list_documents()}
    report = {
        "notice": "12 deliberately selected, agent-labelled real-pair cases. Not random, independent human review, or general accuracy. Text survival is distinct from semantic claim stability. Body vs abstract BLEU conflict is explicitly preserved.",
        "dataset_sha256": hashlib.sha256(
            json.dumps(CASES, ensure_ascii=False).encode()
        ).hexdigest(),
        "code_sha256": {
            name: hashlib.sha256((ROOT / "backend" / name).read_bytes()).hexdigest()
            for name in ["alignment.py", "review.py"]
        },
        "cases": [],
    }
    indexes = {}
    async with httpx.AsyncClient(timeout=100, trust_env=False) as client:
        for name, old, new, block_id, claim, label in CASES:
            old_doc = papers[old]
            new_doc = papers[new]
            source = next(
                b for b in store.get_blocks(old_doc["id"]) if b["id"] == block_id
            )
            if new not in indexes:
                indexes[new] = alignment.SourceAligner(store.get_blocks(new_doc["id"]))
            start = time.monotonic()
            result = indexes[new].locate(source["text"])
            item = {
                **result,
                "note": {
                    "quote": source["text"],
                    "note": claim,
                    "document_id": old_doc["id"],
                },
            }
            async with model.gate:
                semantic = await review_change(item, client, model.URL, model.NAME)
            row = {
                "id": name,
                "source_file": old,
                "target_file": new,
                "source": source,
                "claim": claim,
                "expected": label,
                "legacy_status": legacy(source["text"], indexes[new].blocks),
                "alignment": result,
                "semantic": semantic,
                "seconds": round(time.monotonic() - start, 2),
            }
            report["cases"].append(row)
            path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8"
            )
            print(
                name,
                row["legacy_status"],
                result["status"],
                semantic.get("decision", semantic["status"]),
                label,
                flush=True,
            )
    report["legacy_alert_count"] = sum(
        r["legacy_status"] != "retained" for r in report["cases"]
    )
    report["current_alignment_alert_count"] = sum(
        r["alignment"]["status"] != "retained" for r in report["cases"]
    )
    report["semantic_exact_decisions"] = sum(
        r["semantic"].get("decision") == r["expected"] for r in report["cases"]
    )
    report["semantic_confusion"] = dict(
        Counter(
            r["expected"]
            + " -> "
            + r["semantic"].get("decision", r["semantic"]["status"])
            for r in report["cases"]
        )
    )
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")


asyncio.run(main())
