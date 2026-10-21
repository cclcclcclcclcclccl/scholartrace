"""Frozen cross-module developer diagnostics with original-data preservation."""

import argparse
import asyncio
import hashlib
import json
import runpy
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pymupdf

from backend import diagrams, parsing, store, translation

parser = argparse.ArgumentParser()
parser.add_argument("--repair", action="store_true")
args = parser.parse_args()
round_suffix = "-repair" if args.repair else ""
FOLDER = ROOT / ("artifacts/module-quality-20261015" + round_suffix)
PROTOCOL = ROOT / ("evaluation/module_quality_20261015" + round_suffix)

TRANSLATIONS = [
    {
        "id": "t01",
        "source": "We did not observe improvements under this experimental setting.",
        "language": "zh",
        "expected": "保留未观察到及本实验设置，不写成绝对没有增益。",
    },
    {
        "id": "t02",
        "source": "The method may reduce memory, but this does not establish a causal relationship.",
        "language": "zh",
        "expected": "保留可能、不能确立因果关系。",
    },
    {
        "id": "t03",
        "source": "Accuracy increased from 72.5% to 74.0% on dataset A; dataset B was not evaluated.",
        "language": "zh",
        "expected": "72.5%、74.0%、A上提升；B未评估，不把B写成表现差。",
    },
    {
        "id": "t04",
        "source": "Keep `x = 2` and $y=x^2$ unchanged; the implementation is at https://example.org/method [12].",
        "language": "zh",
        "expected": "代码、公式、URL、引用12保留。",
    },
    {
        "id": "t05",
        "source": "The encoder has 8 layers, whereas the decoder has 4 layers. This is an illustrative configuration, not the default.",
        "language": "zh",
        "expected": "编码器8、解码器4；示例配置而非默认。",
    },
    {
        "id": "t06",
        "source": "在数据集甲上，我们观察到误差从5%下降到3%，但尚未验证其他数据集。",
        "language": "en",
        "expected": "保留数据集甲、5到3、尚未验证其他数据集。",
    },
    {
        "id": "t07",
        "source": "Literal identifier ZXQKEEP1QXZ must remain unchanged; there are 24 samples.",
        "language": "zh",
        "expected": "保留用户原有标识ZXQKEEP1QXZ及24，不能与系统占位混淆。",
    },
    {
        "id": "t08",
        "source": "Only samples matching one of the 500 queries are retained; not every sample matches all queries.",
        "language": "zh",
        "expected": "500个查询中任意一个，不是每个样本匹配全部查询。",
    },
]
DIAGRAMS = [
    {
        "id": "g01",
        "topic": "从上到下绘制数据分析流程：数据输入进入质量校验；合格则进入统计分析，再生成报告；不合格则进入人工修正，修正后返回质量校验。保留合格和不合格两条分支，不加入模型训练。",
        "expected": "TB，校验判断节点、合格/不合格分支、修正回环；无模型训练。",
    },
    {
        "id": "g02",
        "topic": "从左到右绘制检索流程：文献库同时进入词法检索和语义检索，两路均汇入融合排序，最后进入证据问答。不要把两种检索串联，也不要添加外部网络步骤。",
        "expected": "LR，两路并行汇入融合，末尾问答；无外部步骤。",
    },
    {
        "id": "g03",
        "topic": "绘制论文写作流程：研究问题进入证据整理，再进入草稿写作，最终人工审阅。只要这四个模块，从左到右，不要声称自动保证论文正确。",
        "expected": "LR四模块顺序，不加入保证正确结论。",
    },
]


def write(name, value):
    (FOLDER / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), "utf-8")


class Context:
    def progress(self, *args):
        pass

    def check(self):
        pass

    def log(self, *args):
        pass


async def main():
    FOLDER.mkdir(parents=True, exist_ok=True)
    PROTOCOL.mkdir(parents=True, exist_ok=True)
    assert not (FOLDER / "run.json").exists()
    protocol = {
        "notice": "Developer diagnostics; --repair reuses exposed cases after fixes and is development regression. Not independent human validation. Structure and literal checks do not establish semantic quality.",
        "translations": TRANSLATIONS,
        "diagrams": DIAGRAMS,
        "parsing": [
            {"file": "1706.03762v1.pdf", "page": 3},
            {"file": "1706.03762v1.pdf", "page": 8},
            {"file": "1706.03762v1_img.pdf", "page": 3},
            {"file": "UnderstandingDeepLearning_02_09_26_C.pdf", "page": 500},
        ],
    }
    raw = json.dumps(protocol, ensure_ascii=False, indent=2).encode()
    (PROTOCOL / "protocol.json").write_bytes(raw)
    freeze = {
        "created_at": datetime.now(UTC).isoformat(),
        "protocol_sha256": hashlib.sha256(raw).hexdigest(),
        "code_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "backend").glob("*.py"))
        },
    }
    (PROTOCOL / "freeze.json").write_text(json.dumps(freeze, indent=2), "utf-8")
    saved_args = sys.argv
    sys.argv = [sys.argv[0]]
    helper = runpy.run_path(str(ROOT / "scripts/run_proof_v1.py"), run_name="helpers")
    sys.argv = saved_args
    original = store.database_path()
    before = helper["snapshot"](original)
    write("original-before.json", before)
    isolated = FOLDER / "evaluation.sqlite3"
    with sqlite3.connect(original) as src, sqlite3.connect(isolated) as dst:
        src.backup(dst)
    token = store.database_override.set(isolated)
    result = {
        "started_at": datetime.now(UTC).isoformat(),
        "freeze": freeze,
        "translations": [],
        "diagrams": [],
        "parsing": [],
        "complete": False,
    }
    try:
        for case in TRANSLATIONS:
            row = {**case}
            start = time.monotonic()
            try:
                async with asyncio.timeout(180):
                    row["translation"] = await translation.translate_text(
                        case["source"], case["language"]
                    )
                row["signals"] = translation.quality_signals(
                    case["source"], row["translation"], case["language"]
                )
            except Exception as exc:  # noqa: BLE001 -- retain every diagnostic failure
                row["error"] = type(exc).__name__ + ": " + str(exc)
            row["seconds"] = round(time.monotonic() - start, 3)
            result["translations"].append(row)
            write("run.json", result)
            print(case["id"], row.get("translation", row.get("error")), flush=True)
        for case in DIAGRAMS:
            row = {**case}
            start = time.monotonic()
            try:
                async with asyncio.timeout(180):
                    row["artifact"] = await diagrams.generate(
                        Context(), {"topic": case["topic"]}
                    )
                row["code"] = row["artifact"]["code"]
                row["plan"] = row["artifact"]["plan"]
            except Exception as exc:  # noqa: BLE001 -- retain every diagnostic failure
                row["error"] = type(exc).__name__ + ": " + str(exc)
            row["seconds"] = round(time.monotonic() - start, 3)
            result["diagrams"].append(row)
            write("run.json", result)
            print(case["id"], row.get("plan", row.get("error")), flush=True)
        papers = {d["name"]: d for d in store.list_documents()}
        for case in protocol["parsing"]:
            row = {**case}
            d = store.get_document(papers[case["file"]]["id"])
            try:
                row["structure"] = parsing.page_structure(d, case["page"])
                blocks = store.get_blocks(d["id"], case["page"])
                row["block_count"] = len(blocks)
                row["text"] = "\n".join(b["text"] for b in blocks)
                row["methods"] = sorted({b["method"] for b in blocks})
                with pymupdf.open(d["path"]) as pdf:
                    row["total_pages"] = len(pdf)
                    pdf[case["page"] - 1].get_pixmap(
                        matrix=pymupdf.Matrix(1.2, 1.2)
                    ).save(FOLDER / f"{case['file']}-{case['page']}.png")
                row["source_sha256"] = hashlib.sha256(
                    Path(d["path"]).read_bytes()
                ).hexdigest()
            except Exception as exc:  # noqa: BLE001 -- retain every diagnostic failure
                row["error"] = type(exc).__name__ + ": " + str(exc)
            result["parsing"].append(row)
            write("run.json", result)
            print(
                "parse", case["file"], case["page"], row.get("block_count"), flush=True
            )
        result["complete"] = True
    finally:
        store.database_override.reset(token)
        after = helper["snapshot"](original)
        write("original-after.json", after)
        result["original_data_unchanged"] = before == after
        result["finished_at"] = datetime.now(UTC).isoformat()
        write("run.json", result)


if __name__ == "__main__":
    asyncio.run(main())
