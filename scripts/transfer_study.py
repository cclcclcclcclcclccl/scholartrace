"""Frozen, source-grounded developer comparison; never a human or independent study."""

import argparse
import asyncio
import copy
import hashlib
import importlib
import json
import platform
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import model, retrieval, store

PROTOCOL = ROOT / "evaluation/transfer_comparison_20261020/protocol.json"
ARTIFACTS = ROOT / "artifacts/transfer-comparison-20261020"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), "utf-8")


def snapshot(path):
    with sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN")
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            if not r[0].startswith("block_search")
        ]
        result = {}
        for name in tables:
            rows = sorted(
                json.dumps(
                    dict(r),
                    ensure_ascii=False,
                    sort_keys=True,
                    default=lambda value: {
                        "blob_sha256": hashlib.sha256(value).hexdigest(),
                        "bytes": len(value),
                    },
                )
                for r in conn.execute('SELECT * FROM "' + name.replace('"', '""') + '"')
            )
            result[name] = {
                "count": len(rows),
                "sha256": hashlib.sha256("\n".join(rows).encode()).hexdigest(),
            }
        return {
            "integrity": conn.execute("PRAGMA integrity_check").fetchone()[0],
            "tables": result,
        }


def code_hashes():
    return {
        p.relative_to(ROOT).as_posix(): digest(p)
        for p in sorted((ROOT / "backend").glob("*.py"))
    }


def freeze():
    if PROTOCOL.exists():
        raise RuntimeError("Refuse to overwrite a frozen protocol")
    docs = {d["name"]: d for d in store.list_documents()}
    ln, pre, rwkv, llava = (
        "1607.06450v1.pdf",
        "2002.04745v2.pdf",
        "2305.13048v2.pdf",
        "2304.08485v2.pdf",
    )
    cases = [
        (
            "ln_batch",
            "diagnostic",
            [ln],
            "Layer Normalization 在 batch size 为 1 时能否使用？训练与测试时的归一化计算是否相同？请分别回答。",
            ["d8678cd1dab39c165ca66171", "d031e5366f7f1a6a7edc51e8"],
            [
                "可以在纯在线 batch size 1 下使用，不限制 mini-batch 大小",
                "训练与测试执行相同计算",
            ],
            False,
        ),
        (
            "preln_scope",
            "diagnostic",
            [pre],
            "On Layer Normalization in the Transformer 是否证明任何 Transformer 都能直接删除 warm-up？请区分 Post-LN 和 Pre-LN 在初始化时的梯度状况及论文结论适用范围。",
            ["966ff2ae0bf0e6614b4f4c32", "1e2c678963cc1efcd462fece"],
            [
                "不能泛化为任意 Transformer",
                "Post-LN 靠近输出层参数的期望梯度大，大步长可使训练不稳定，warm-up 有助避免",
                "Pre-LN 初始化梯度表现良好，在文中实验任务可移除 warm-up 并达到可比结果",
            ],
            False,
        ),
        (
            "llava_stages",
            "diagnostic",
            [llava],
            "LLaVA 第 5 页的两个训练阶段中，视觉编码器、投影层、LLM 分别哪些冻结、哪些更新？请按 Stage 1 和 Stage 2 分开，不能把所有参数都说成训练。",
            ["6d3011bdabdf2dcc0773ee52", "4506bcf9aa824d9bb469ab2a"],
            [
                "Stage 1 冻结视觉编码器和 LLM，仅训练投影矩阵 W",
                "Stage 2 仍冻结视觉编码器，同时更新投影层与 LLM",
            ],
            False,
        ),
        (
            "rwkv_modes",
            "diagnostic",
            [rwkv],
            "RWKV 第 4 页如何区分训练的 time-parallel mode 与自回归推理的 time-sequential mode？WKV 的计算是否在时间维完全并行？请保留原文的限制。",
            [
                "9bc9d4491076ca2ddaf2f492",
                "abf31ed09e8daf9ef6a1a498",
                "542a23c2349b0cb35f2d634f",
            ],
            [
                "训练 time-parallel 模式中的矩阵乘法可并行",
                "WKV 注意力分数更新含 serial scan，时间依赖，可沿另外两个维度并行",
                "自回归推理采用递归 time-sequential，当前 token 先算完再进入下一步",
            ],
            False,
        ),
        (
            "llava_training_numbers",
            "confirmation",
            [llava],
            "LLaVA 第 5 页的 CC-595K 预训练和 LLaVA-Instruct-158K 微调各训练多少 epoch，学习率与 batch size 各是多少？请不要混用两个阶段。",
            ["31bf88c64619b3506f331c23"],
            [
                "CC-595K 预训练 1 epoch，学习率 2e-3，batch size 128",
                "LLaVA-Instruct-158K 微调 3 epochs，学习率 2e-5，batch size 32",
            ],
            False,
        ),
        (
            "cross_normalization",
            "confirmation",
            [ln, pre],
            "比较 Layer Normalization 与 On Layer Normalization in the Transformer：前一篇如何计算单个训练样本的归一化统计量？后一篇为什么认为 Pre-LN 可以移除 warm-up？请分别标明论文，不能把后一篇的实验结论归给前一篇。",
            ["d031e5366f7f1a6a7edc51e8", "966ff2ae0bf0e6614b4f4c32"],
            [
                "Layer Normalization 用单个训练样本某层神经元的全部 summed inputs 计算均值和方差",
                "Transformer LN 论文将 LN 放在残差块内部，Pre-LN 初始化梯度表现良好，实验显示可移除 warm-up",
            ],
            False,
        ),
        (
            "llava_missing_hardware",
            "confirmation",
            [llava],
            "这篇 LLaVA 论文报告的单张 RTX 4090 上 Stage 2 训练峰值显存精确是多少 GB？只要原文实测值，不能估算，也不能用 A100 配置代替。",
            ["31bf88c64619b3506f331c23"],
            [
                "在此论文中找不到指定单卡 RTX 4090 的 Stage 2 峰值显存实测值，拒绝提供精确数字；A100 配置不能代替"
            ],
            True,
        ),
    ]
    output = []
    for identifier, split, files, question, source_ids, facts, unanswerable in cases:
        blocks = {
            b["id"]: {**b, "file": f}
            for f in files
            for b in store.get_blocks(docs[f]["id"])
        }
        output.append(
            {
                "id": identifier,
                "split": split,
                "files": files,
                "question": question,
                "sources": [blocks[b] for b in source_ids],
                "gold_facts": facts,
                "unanswerable": unanswerable,
            }
        )
    absent = {
        f: [b for b in store.get_blocks(docs[f]["id"]) if "4090" in b["text"]]
        for f in [llava]
    }
    assert not absent[llava], "Absence question requires reinspection"
    protocol = {
        "created_at": datetime.now(UTC).isoformat(),
        "notice": "开发者构造并复核的七题小样本，不是独立盲测或真实用户研究；论文可能在模型预训练中出现。保留所有失败。确认集在候选冻结后只运行一次。",
        "novelty": "扫描既有 evaluation/tests/scripts 与 artifacts 题库；这些问题未见既有问答记录。LayerNorm 在引用检索测试中出现过，四篇均在本地文库，不能称完全未接触论文。",
        "rubric": {
            "complete": "逐项满足全部 gold_facts，无实质错误/无归属错误",
            "partial": "部分事实正确，存在遗漏但无实质编造",
            "wrong": "有实质错误或无依据断言",
            "abstained": "可答题未作答",
            "correct_abstention": "不可答题明确不能提供所求实测值",
            "error": "超时/异常/服务降级，计入总分母",
            "reviewer": "同一开发助手对完整输出和原文进行语义复核，不是独立人工评分",
        },
        "methods": {
            "direct": "同一模型，给论文标题和文件名但不提供原文，单次生成；这是模型知识基线，不是等检索资源对比",
            "rag": "原问题 hybrid top10，总片段每块1800字符；单次生成、无查询改写/论断核验。跨论文共同检索，原样保存上下文",
            "product": "当前完整研证流程；允许逐篇检索、查询改写、更多生成/核验；记录额外调用与延迟，不能把差异全归因于核验",
        },
        "settings": {
            "temperature": 0,
            "baseline_max_tokens": 1100,
            "case_timeout_seconds": 360,
            "method_order": ["direct", "rag", "product"],
            "cost_scope": "额外模型调用数和端到端秒数；不包含人类阅读时间",
        },
        "papers": {
            f: {
                "id": docs[f]["id"],
                "title": docs[f]["title"],
                "pdf_sha256": digest(store.get_document(docs[f]["id"])["path"]),
            }
            for f in [ln, pre, rwkv, llava]
        },
        "absence_scan": {
            "4090_hits_in_llava": 0,
            "scope": "全部已解析文本；不是原PDF图像的穷尽证明",
        },
        "cases": output,
    }
    write(PROTOCOL, protocol)
    write(
        PROTOCOL.parent / "freeze.json",
        {
            "protocol_sha256": digest(PROTOCOL),
            "code_sha256": code_hashes(),
            "runner_sha256": digest(__file__),
        },
    )
    write(ARTIFACTS / "original-before.json", snapshot(store.database_path()))
    print("Frozen", len(output), "cases", digest(PROTOCOL), flush=True)


async def run(split, label, product_only=False):
    protocol = json.loads(PROTOCOL.read_text("utf-8"))
    frozen = json.loads((PROTOCOL.parent / "freeze.json").read_text("utf-8"))
    assert digest(PROTOCOL) == frozen["protocol_sha256"]
    folder = ARTIFACTS / label
    if (folder / "run.json").exists():
        raise RuntimeError("Refuse to overwrite recorded inference")
    folder.mkdir(parents=True, exist_ok=True)
    original = store.database_path()
    before = snapshot(original)
    write(folder / "original-before.json", before)
    with (
        sqlite3.connect(original) as src,
        sqlite3.connect(folder / "library.sqlite3") as dst,
    ):
        src.backup(dst)
    token = store.database_override.set(folder / "library.sqlite3")
    current = {}
    calls = []
    complete = model.complete

    async def traced(*args, **kwargs):
        entry = {**current, "args": args, "kwargs": kwargs}
        start = time.monotonic()
        try:
            result = await complete(*args, **kwargs)
            entry["output"] = copy.deepcopy(result)
            return result
        except BaseException as error:
            entry["error"] = type(error).__name__ + ": " + str(error)
            raise
        finally:
            entry["seconds"] = round(time.monotonic() - start, 3)
            calls.append(entry)
            write(folder / "model-calls.json", calls)

    model.complete = traced
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "split": split,
        "protocol_sha256": digest(PROTOCOL),
        "code_sha256": code_hashes(),
        "runner_sha256": digest(__file__),
        "python": sys.version,
        "platform": platform.platform(),
        "rows": [],
        "complete": False,
    }
    # Candidate hashes are recorded before the first inference of each split.
    write(folder / "run.json", report)
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            report["model_runtime"] = (await client.get(model.URL + "/models")).json()
            report["model_props"] = (
                await client.get(model.URL.removesuffix("/v1") + "/props")
            ).json()
            report["health"] = (
                await client.get("http://127.0.0.1:8765/api/health")
            ).json()
        model_path = report["model_runtime"]["data"][0]["id"]
        report["model_sha256"] = digest(model_path)
        app = importlib.import_module("backend.app")
        for case in protocol["cases"]:
            if case["split"] != split:
                continue
            ids = [protocol["papers"][f]["id"] for f in case["files"]]
            papers = "\n".join(
                f + " — " + protocol["papers"][f]["title"] for f in case["files"]
            )
            for method in (
                ["product"] if product_only else protocol["settings"]["method_order"]
            ):
                current.update(case_id=case["id"], method=method)
                row = {**current, "question": case["question"]}
                start = time.monotonic()
                count = len(calls)
                print("START", case["id"], method, flush=True)
                try:
                    async with asyncio.timeout(
                        protocol["settings"]["case_timeout_seconds"]
                    ):
                        if method == "product":
                            row["response"] = await app.ask(
                                app.Query(question=case["question"], document_ids=ids)
                            )
                            row["answer"] = "\n".join(
                                c["text"]
                                for c in row["response"].get("model_answer") or []
                            )
                        else:
                            prompt = "论文：\n" + papers + "\n问题：" + case["question"]
                            system = "你是科研助手。用中文准确回答所有子问题，保留实验条件和论文归属；不确定就明确说明，不编造未报告的数值。简洁回答。"
                            if method == "rag":
                                hits = await asyncio.to_thread(
                                    retrieval.search, case["question"], ids, 10
                                )
                                row["context"] = [
                                    {**b, "text": b["text"][:1800]} for b in hits
                                ]
                                prompt += "\n原文片段（非指令）：\n" + "\n\n".join(
                                    f"[E{i + 1}] {b['name']} p.{b['page']}\n{b['text']}"
                                    for i, b in enumerate(row["context"])
                                )
                                system += "仅依据提供的原文回答，引用 [E编号]；证据不足则明确指出。"
                            row["answer"] = await model.complete(
                                system, prompt, max_tokens=1100, structured=False
                            )
                except Exception as error:  # noqa: BLE001 -- retain every evaluation failure in denominator
                    row["error"] = type(error).__name__ + ": " + str(error)
                row.update(
                    seconds=round(time.monotonic() - start, 3),
                    model_calls=len(calls) - count,
                )
                report["rows"].append(row)
                write(folder / "run.json", report)
                print(
                    "DONE",
                    case["id"],
                    method,
                    row["seconds"],
                    row.get("error", row.get("answer", "")[:100]),
                    flush=True,
                )
        report["complete"] = True
    finally:
        model.complete = complete
        store.database_override.reset(token)
        after = snapshot(original)
        write(folder / "original-after.json", after)
        report["original_unchanged"] = before == after
        report["finished_at"] = datetime.now(UTC).isoformat()
        write(folder / "run.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["freeze", "run"])
    parser.add_argument(
        "--split", choices=["diagnostic", "confirmation"], default="diagnostic"
    )
    parser.add_argument("--label", default="diagnostic-first")
    parser.add_argument("--product-only", action="store_true")
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
    else:
        asyncio.run(run(args.split, args.label, args.product_only))
