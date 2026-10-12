"""Development retrieval ablation with explicit source targets, never benchmark claims."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import store, retrieval

V1 = "0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476"
CASES = [
    ("训练用了哪些 GPU？", "NVIDIA P100"),
    ("Adam 优化器的两个 beta 参数是多少？", "0.98"),
    ("位置编码如何表示序列位置？", "sin"),
    ("模型怎样防止过拟合？", "dropout"),
    ("用了多少个注意力头？", "h = 8"),
    ("德语翻译 BLEU 分数是多少？", "28.4"),
    ("训练文本采用什么分词方式？", "word-piece"),
    ("编码器由多少层组成？", "N = 6"),
    ("作者未来希望将注意力机制用于什么模态？", "other modalities"),
    ("如何避免自回归解码看到未来的词？", "mask"),
]


def main():
    rows = []
    for question, expected in CASES:
        methods = {
            "bm25": store.search(question, [V1], limit=5),
            "dense": retrieval.dense(question, [V1], limit=5),
            "hybrid": retrieval.search(question, [V1], limit=5),
        }
        row = {
            "question": question,
            "expected_source_substring": expected,
            "methods": {},
        }
        for method, blocks in methods.items():
            hit = next(
                (
                    i + 1
                    for i, b in enumerate(blocks)
                    if expected.lower() in store.normalize(b["text"]).lower()
                ),
                None,
            )
            row["methods"][method] = {
                "rank": hit,
                "hit_at_5": hit is not None,
                "blocks": [{"id": b["id"], "page": b["page"]} for b in blocks],
            }
        rows.append(row)
    report = {
        "dataset": "10 hand-authored development questions on official Transformer v1; not held-out, not an official acceptance score",
        "embedding": retrieval.MODEL,
        "document": V1,
        "results": rows,
        "hit_at_5": {
            method: sum(r["methods"][method]["hit_at_5"] for r in rows) / len(rows)
            for method in ["bm25", "dense", "hybrid"]
        },
    }
    folder = store.ROOT / "artifacts/full-workbench"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "retrieval-ablation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["hit_at_5"]))


if __name__ == "__main__":
    main()
