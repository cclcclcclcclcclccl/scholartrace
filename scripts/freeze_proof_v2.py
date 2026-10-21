"""Freeze repaired-code regression separately from new, developer-authored diagnostic items."""

import copy
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import store

base = json.loads(
    (ROOT / "evaluation/proof_v1/protocol.json").read_text(encoding="utf-8")
)
papers = {d["name"]: d for d in store.list_documents()}


def freeze(name, p):
    folder = ROOT / "evaluation" / name
    folder.mkdir(parents=True, exist_ok=True)
    assert not (folder / "freeze.json").exists()
    raw = json.dumps(p, ensure_ascii=False, indent=2).encode()
    (folder / "protocol.json").write_bytes(raw)
    f = {
        "created_at": datetime.now(UTC).isoformat(),
        "protocol_sha256": hashlib.sha256(raw).hexdigest(),
        "code_sha256": {
            str(x.relative_to(ROOT)): hashlib.sha256(x.read_bytes()).hexdigest()
            for x in sorted((ROOT / "backend").glob("*.py"))
        },
        "notice": p["notice"],
    }
    (folder / "freeze.json").write_text(
        json.dumps(f, ensure_ascii=False, indent=2), encoding="utf-8"
    )


p = copy.deepcopy(base)
p["notice"] = (
    "Post-fix development regression on ALL exposed proof-v1 items, not independent validation. First-run v1 preserved."
)
freeze("proof_v2_regression", p)
p = {
    "created_at": datetime.now(UTC).isoformat(),
    "notice": "New developer-authored frozen diagnostic after repair design but before seeing regression results. Not independently human-labelled or guaranteed absent from model pretraining. Do not tune this run or overwrite failures.",
    "qa": [],
    "controlled_review": [],
    "real_review": [],
    "scoring": base["scoring"],
}


def q(id, files, question, refs, expected, patterns=None, negative=False):
    sources = []
    for file, block in refs:
        sources.append(
            {
                **next(
                    b for b in store.get_blocks(papers[file]["id"]) if b["id"] == block
                ),
                "file": file,
            }
        )
    p["qa"].append(
        {
            "id": id,
            "files": files,
            "question": question,
            "sources": sources,
            "expected": expected,
            "required_patterns": patterns or [],
            "unanswerable": negative,
        }
    )


q(
    "bloom_languages",
    ["2211.05100v4.pdf"],
    "BLOOM 的 ROOTS 语料包含多少种自然语言和多少种编程语言？请分别给出数量。",
    [("2211.05100v4.pdf", "3edb94d8a273c04147792457")],
    "46 natural languages and13 programming languages, not59 natural languages.",
    [r"46", r"13", r"自然", r"编程"],
)
q(
    "switch_routing",
    ["2101.03961v3.pdf"],
    "Switch Transformer 的一个 token 会路由到多少个专家？请不要把每个 token 选中的数量和模型拥有的专家总数混淆。",
    [("2101.03961v3.pdf", "5deeb3d1c9e336250f33bdef")],
    "One expert per token (k=1); not total model expert count.",
    [r"一个|1|单个|one"],
)
q(
    "zero_states",
    ["1910.02054v3.pdf"],
    "ZeRO-DP 的三个主要优化阶段分别对哪三类模型状态进行分区？",
    [("1910.02054v3.pdf", "4e0d20bde7b3103e1d2f64c3")],
    "optimizer states, gradients, parameters; do not substitute activation/residual states.",
    [r"优化器", r"梯度", r"参数"],
)
q(
    "instruct_preference_scope",
    ["2203.02155v1.pdf"],
    "InstructGPT 摘要中，1.3B 模型相对 175B GPT-3 的优势是在什么评价条件下观察到的？请保留“人的偏好”和提示分布范围，不能说所有任务都更强。",
    [("2203.02155v1.pdf", "2fade9625734ccdea83cc898")],
    "Human evaluations on authors prompt distribution prefer1.3B InstructGPT outputs over175B GPT3; not universal task superiority.",
    [r"人|human", r"偏好|更喜欢|prefer", r"分布|distribution"],
)
q(
    "bloom_qlora_entities",
    ["2211.05100v4.pdf", "2305.14314v1.pdf"],
    "BLOOM 论文所介绍模型的参数量是多少？QLoRA 摘要中单张 48GB GPU 微调的模型参数量又是多少？请逐篇回答，不要交换数字。",
    [
        ("2211.05100v4.pdf", "3edb94d8a273c04147792457"),
        ("2305.14314v1.pdf", "9030af7fe782f0686185942a"),
    ],
    "BLOOM176B; QLoRA example65B fine-tuning, with paper-specific citations.",
    [r"176\s*B|1760\s*亿", r"65\s*B|650\s*亿"],
)
q(
    "absent_local_speed",
    ["2101.03961v3.pdf"],
    "只根据这份 Switch Transformer 论文，蔡晨霖在 2026 年 10 月 15 日的私人电脑上运行该模型的实测每秒 token 数是多少？没有该次实验原文记录则不要用论文的其他速度代替。",
    [],
    "No evidence for invented later personal measurement; no throughput fabricated.",
    negative=True,
)


def pair(id, old, new, note, label, category):
    p["controlled_review"].append(
        {
            "id": id,
            "kind": "controlled_synthetic",
            "old": old,
            "new": new,
            "observation": note,
            "expected": label,
            "category": category,
        }
    )


S = "same_claim"
C = "claim_changed"
U = "unclear"
pair(
    "n01",
    "The latency is 750 milliseconds per sample.",
    "The latency is 0.75 seconds per sample.",
    "每个样本的延迟是否变化？",
    S,
    "duration",
)
pair(
    "n02",
    "The decoder has 9 layers. The encoder has 5 layers.",
    "The decoder has 9 layers. The encoder has 7 layers.",
    "解码器层数是否变化？",
    S,
    "entity_scope",
)
pair(
    "n03",
    "We use 12 GPUs. Validation accuracy is 72%.",
    "Validation accuracy is 76%. We use 12 GPUs.",
    "GPU 数量是否变化？",
    S,
    "reordering_distractor",
)
pair(
    "n04",
    "The dropout probability is 0.125.",
    "The dropout probability is 12.5%.",
    "dropout 概率是否变化？",
    S,
    "probability",
)
pair(
    "n05",
    "We average scores from four independent runs.",
    "The reported score is the mean of four independent runs.",
    "报告统计量是否变化？",
    S,
    "paraphrase",
)
pair(
    "n06",
    "No auxiliary labels are needed.",
    "Auxiliary labels are not required.",
    "是否需要辅助标签？",
    S,
    "negative_paraphrase",
)
pair(
    "n07",
    "The embedding width is 320.",
    "The embedding\nwidth is 320.",
    "嵌入宽度是否变化？",
    S,
    "layout",
)
pair(
    "n08",
    "The learning rate is 0.00006.",
    "The learning rate is 6e-5.",
    "学习率是否变化？",
    S,
    "notation",
)
pair(
    "n09",
    "The latency is 0.75 seconds per sample.",
    "The latency is 0.75 seconds per batch.",
    "延迟计量对象是否改变？",
    C,
    "denominator",
)
pair("n10", "We use 12 GPUs.", "We use 24 GPUs.", "GPU 数量是否变化？", C, "number")
pair(
    "n11",
    "The model uses a fixed embedding.",
    "The model uses a trainable embedding.",
    "嵌入是否可学习？",
    C,
    "parameter_status",
)
pair(
    "n12",
    "The score is the median of six runs.",
    "The score is the maximum of six runs.",
    "跨运行统计量是否变化？",
    C,
    "aggregation",
)
pair(
    "n13",
    "The method requires auxiliary labels.",
    "The method does not require auxiliary labels.",
    "是否需要辅助标签？",
    C,
    "negation",
)
pair(
    "n14",
    "Evaluation is restricted to clean images.",
    "Evaluation includes clean and noisy images.",
    "评估样本范围是否变化？",
    C,
    "scope",
)
pair(
    "n15",
    "The learning rate is 6e-5.",
    "The learning rate is 6e-4.",
    "学习率是否变化？",
    C,
    "numeric_magnitude",
)
pair(
    "n16",
    "The model is twice as slow as the baseline.",
    "The model is twice as fast as the baseline.",
    "相对基线的速度关系是否变化？",
    C,
    "comparison",
)
pair(
    "n17",
    "The learning rate is 0.002.",
    "We use momentum optimization.",
    "学习率是否变化？",
    U,
    "missing_metric",
)
pair(
    "n18",
    "The encoder has 11 layers.",
    "We redesigned the tokenizer.",
    "编码器层数是否变化？",
    U,
    "missing_structure",
)
pair(
    "n19",
    "The score is 80 on benchmark Delta.",
    "The score is 85 on benchmark Gamma.",
    "基准 Delta 上的得分是否提高？",
    U,
    "incomparable_dataset",
)
pair(
    "n20",
    "The algorithm converges under condition P.",
    "The algorithm converges under condition R.",
    "条件 P 下是否仍收敛？",
    U,
    "incomparable_condition",
)
pair(
    "n21",
    "The system uses a teacher network.",
    "A teacher network is not specified.",
    "新版是否一定不使用教师网络？",
    U,
    "absence_not_negation",
)
pair(
    "n22",
    "The error rate is 4% in test split A.",
    "The paper does not report the error rate.",
    "错误率是否变化？",
    U,
    "missing_measurement",
)
pair(
    "n23",
    "The metric is 73 on dataset North.",
    "The metric is 73 on dataset South.",
    "数据集 North 的指标是否未变？",
    U,
    "equal_number_different_dataset",
)
pair(
    "n24",
    "Runtime is bounded under condition S.",
    "Runtime is not bounded under condition T.",
    "条件 S 下运行时间是否失去上界？",
    U,
    "conditional_negation",
)
freeze("proof_v2_new", p)
print(
    "Frozen regression45 and new30; no model outputs inspected for these versions yet."
)
