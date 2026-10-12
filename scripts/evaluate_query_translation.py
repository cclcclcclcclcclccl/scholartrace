"""Same disclosed development cases, adding local query translation before fusion."""

import asyncio, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import store, model, retrieval
from scripts.evaluate_retrieval import CASES, V1


async def main():
    rows = []
    for question, expected in CASES:
        value = await model.complete(
            'Translate the research question into a concise English search query. Keep meaning and technical terms; do not answer or guess numerical values. Return JSON {"query":"English search query"}.',
            question,
            max_tokens=180,
        )
        query = question + " " + value["query"]
        blocks = retrieval.search(query, [V1], 5)
        rank = next(
            (
                i + 1
                for i, b in enumerate(blocks)
                if expected.lower() in store.normalize(b["text"]).lower()
            ),
            None,
        )
        rows.append(
            {
                "question": question,
                "rewritten_query": query,
                "expected_substring": expected,
                "rank": rank,
                "blocks": [{"id": b["id"], "page": b["page"]} for b in blocks],
            }
        )
    report = {
        "scope": "Same 10 development cases as retrieval-ablation.json. Query translation was added after examining this development set; not a held-out metric.",
        "hit_at_5": sum(r["rank"] is not None for r in rows) / len(rows),
        "results": rows,
    }
    (store.ROOT / "artifacts/full-workbench/query-translation-eval.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(report["hit_at_5"], flush=True)


if __name__ == "__main__":
    asyncio.run(main())
