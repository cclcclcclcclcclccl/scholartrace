"""Create a labelled protocol before any inference; refuses to overwrite frozen inputs."""

import ast
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import store

folder = ROOT / "evaluation/proof_v1"
assert not (folder / "freeze.json").exists(), "Already frozen"
papers = {d["name"]: d for d in store.list_documents()}


def source(file, block):
    d = papers[file]
    b = next(b for b in store.get_blocks(d["id"]) if b["id"] == block)
    return {**b, "file": file}


qa = []


def question(id, files, text, blocks, expected, patterns=None, negative=False):
    qa.append(
        {
            "id": id,
            "files": files,
            "question": text,
            "sources": [source(f, b) for f, b in blocks],
            "expected": expected,
            "required_patterns": patterns or [],
            "unanswerable": negative,
        }
    )


question(
    "whisper_scale",
    ["2212.04356v1.pdf"],
    "Whisper 论文所说的弱监督音频训练数据总量是多少小时？请保留单位，并指出原文。",
    [("2212.04356v1.pdf", "ca9667652d039fc80df64d02")],
    "680,000 hours labelled audio; not 680000 samples.",
    [r"680[，,]?000|68\s*万", r"小时|hours"],
)
question(
    "whisper_segments",
    ["2212.04356v1.pdf"],
    "Whisper 的训练音频被切成多长的片段？没有语音的片段是否完全排除？",
    [("2212.04356v1.pdf", "a8945a76aad15d6ff66009db")],
    "30-second segments; non-speech segments retained with subsampled probability and used for VAD.",
    [r"30", r"秒|second", r"无语音|没有语音|非语音|静音", r"采样|抽样|概率|sub.?sampl"],
)
question(
    "clip_pairs",
    ["2103.00020v1.pdf"],
    "CLIP 预训练数据的规模和组成是什么？请区分图文对数量与 ImageNet 训练图片数量。",
    [("2103.00020v1.pdf", "60b0f0e07cbb3cfbea7da34f")],
    "400 million image-text pairs from internet; 1.28 million is referenced ImageNet examples, not CLIP pretraining count.",
    [r"4\s*亿|400\s*(?:million|M|百万)", r"图文|图像.{0,8}文本|image.{0,8}text"],
)
mistral = next(
    b
    for b in store.get_blocks(papers["2310.06825v1.pdf"]["id"])
    if "W = 4096" in b["text"]
)
question(
    "mistral_window",
    ["2310.06825v1.pdf"],
    "Mistral 7B 文中滑动注意力窗口 W 是多少？这个窗口和文中最后一层约 131K 的理论注意力跨度是否是同一个概念？",
    [("2310.06825v1.pdf", mistral["id"])],
    "W=4096; last-layer theoretical receptive span about131K from stacked layers, not single-layer window or proven usable context length.",
    [r"4[，,]?096", r"131", r"层|layer"],
)
question(
    "qlora_training",
    ["2305.14314v1.pdf"],
    "QLoRA 摘要中单张 48GB GPU 对应多大参数模型？这里描述的是微调还是仅推理？",
    [("2305.14314v1.pdf", "9030af7fe782f0686185942a")],
    "65B parameters; fine-tuning on one48GB GPU, not merely inference and not general full16bit training.",
    [r"65\s*[Bb]|650\s*亿", r"微调|finetun|fine.?tun", r"48"],
)
question(
    "dpo_objective",
    ["2305.18290v3.pdf"],
    "DPO 是否需要先单独拟合一个显式奖励模型，再用强化学习训练策略？请根据论文说明它实际直接优化什么。",
    [("2305.18290v3.pdf", "7103691d3deb6d12c59a9dc7")],
    "No explicit reward model training/RL pipeline; policy directly optimized with preference loss/binary cross entropy, implicit reward interpretation still exists.",
    [r"不|无需|避免|without", r"偏好|preference", r"策略|policy"],
)
question(
    "cross_modal_units",
    ["2212.04356v1.pdf", "2103.00020v1.pdf"],
    "请分别说明 Whisper 与 CLIP 的预训练数据规模及计量单位，不要把音频小时和图文对数量混在一起。",
    [
        ("2212.04356v1.pdf", "ca9667652d039fc80df64d02"),
        ("2103.00020v1.pdf", "60b0f0e07cbb3cfbea7da34f"),
    ],
    "Whisper680000hours; CLIP400million image-text pairs, each tied to its own paper.",
    [r"680[，,]?000|68\s*万", r"4\s*亿|400\s*(?:million|M|百万)"],
)
question(
    "invented_run",
    ["2305.14314v1.pdf"],
    "请只根据这份 QLoRA 论文，给出“蔡晨霖在 2026 年 10 月 14 日用随机种子 314159 进行的独立复现实验”的实测峰值显存。论文没有记录这次实验就明确说明，不能用论文中的 48GB 代替。",
    [],
    "No evidence for this invented later personal experiment; no numeric peak-memory claim for it.",
    negative=True,
)
question(
    "future_run",
    ["2212.04356v1.pdf"],
    "只依据这份 Whisper 论文，2026 年 10 月 14 日西安交通大学 AI2501 班自行录制测试集的词错误率实测值是多少？原文未记录就不要推算。",
    [],
    "No evidence for this invented later local evaluation; abstain from reporting WER.",
    negative=True,
)
review = []


def pair(id, old, new, note, label, category):
    review.append(
        {
            "id": id,
            "kind": "controlled_synthetic",
            "category": category,
            "observation": note,
            "old": old,
            "new": new,
            "expected": label,
            "label_basis": "Explicit scoped statement comparison; developer-authored before inference; independent human review pending.",
        }
    )


S = "same_claim"
C = "claim_changed"
U = "unclear"
pair(
    "s01",
    "Training uses 12 devices.",
    "Training uses 12 devices.",
    "训练设备数量是多少？",
    S,
    "exact",
)
pair(
    "s02",
    "We use a batch\nsize of 48.",
    "We use a batch size of 48.",
    "批大小是否改变？",
    S,
    "layout",
)
pair(
    "s03",
    "The dropout probability is 0.2.",
    "The dropout probability is 20%.",
    "dropout 概率是否变化？",
    S,
    "equivalent_notation",
)
pair(
    "s04",
    "Training lasts 120 seconds.",
    "Training lasts 2 minutes.",
    "训练持续时间是否变化？",
    S,
    "unit_conversion",
)
pair(
    "s05",
    "The learning rate is 0.0002.",
    "The learning rate is 2e-4.",
    "学习率是否变化？",
    S,
    "scientific_notation",
)
pair(
    "s06",
    "The encoder has 10 layers. The decoder has 4 layers.",
    "The encoder has 10 layers. The decoder has 6 layers.",
    "编码器有多少层？",
    S,
    "distractor",
)
pair(
    "s07",
    "The model was trained with eight attention heads.",
    "Eight attention heads were used to train the model.",
    "注意力头数是否变化？",
    S,
    "paraphrase",
)
pair(
    "s08",
    "The test accuracy is 91%. Training uses 3 GPUs.",
    "The test accuracy is 94%. Training uses 3 GPUs.",
    "训练 GPU 数量是否变化？",
    S,
    "distractor",
)
pair(
    "s09",
    "We exclude validation samples from training.",
    "Validation samples are not included in training.",
    "训练是否包含验证集样本？",
    S,
    "negation_paraphrase",
)
pair(
    "s10",
    "Evaluation uses dataset A. Batch size is 24.",
    "Batch size is 24. Evaluation uses dataset A.",
    "评估数据集是否改变？",
    S,
    "reorder",
)
pair(
    "c01",
    "The optimizer uses weight decay 0.01.",
    "The optimizer uses weight decay 0.1.",
    "权重衰减系数是否改变？",
    C,
    "numeric",
)
pair(
    "c02",
    "We evaluate only on English.",
    "We evaluate on English and German.",
    "评估语言范围是否扩大？",
    C,
    "scope",
)
pair(
    "c03",
    "The pretrained weights are frozen.",
    "The pretrained weights are updated.",
    "预训练权重是否保持冻结？",
    C,
    "training_condition",
)
pair(
    "c04",
    "The method is faster than the baseline.",
    "The method is slower than the baseline.",
    "方法相对基线的速度关系是否改变？",
    C,
    "comparison_direction",
)
pair(
    "c05",
    "We report the mean across 5 runs.",
    "We report the best of 5 runs.",
    "报告值是多次均值还是最佳值？",
    C,
    "aggregation",
)
pair(
    "c06",
    "The error rate decreases by 2 percentage points.",
    "The error rate decreases by 2 percent relative to baseline.",
    "误差降低的绝对百分点与相对比例是否改变？",
    C,
    "metric_semantics",
)
pair(
    "c07",
    "The latency is 40 ms per batch.",
    "The latency is 40 ms per sample.",
    "延迟的计量对象是否改变？",
    C,
    "denominator",
)
pair(
    "c08",
    "No test images are used for training.",
    "Test images are used for training.",
    "训练是否使用测试集图片？",
    C,
    "negation",
)
pair(
    "c09",
    "The encoder has 6 layers and the decoder has 12 layers.",
    "The encoder has 12 layers and the decoder has 6 layers.",
    "编码器层数是否变化？",
    C,
    "entity_binding",
)
pair(
    "c10",
    "We will release the code.",
    "The code is available at https://example.org/research.",
    "代码发布状态是否变化？",
    C,
    "known_rule_family",
)
pair(
    "u01",
    "Training uses 6 GPUs.",
    "The paper describes a new tokenizer.",
    "新版本训练 GPU 数量是多少？",
    U,
    "missing_evidence",
)
pair(
    "u02",
    "The score is 88 on benchmark A.",
    "The score is 91 on benchmark B.",
    "同一基准 A 的得分是否提高？",
    U,
    "incomparable",
)
pair(
    "u03",
    "The model may converge under condition X.",
    "The model converges under condition Y.",
    "在条件 X 下是否必然收敛？",
    U,
    "missing_condition",
)
pair(
    "u04",
    "The evaluation used private dataset Z.",
    "Dataset Z is no longer described.",
    "新版是否一定不再使用数据集 Z？",
    U,
    "absence_not_negation",
)
# Existing real-paper cases are deliberately marked as exposed regression, never holdout.
tree = ast.parse(
    (ROOT / "scripts/evaluate_version_alignment.py").read_text(encoding="utf-8")
)
old = next(
    ast.literal_eval(n.value)
    for n in tree.body
    if isinstance(n, ast.Assign)
    and any(isinstance(t, ast.Name) and t.id == "CASES" for t in n.targets)
)
real = [
    {
        "id": "real_" + id,
        "kind": "exposed_real_regression",
        "source": source(f, b),
        "target_file": t,
        "observation": o,
        "expected": e,
    }
    for id, f, t, b, o, e in old
]
protocol = {
    "created_at": datetime.now(UTC).isoformat(),
    "notice": "Developer-authored frozen diagnostic, not independent human acceptance. Synthetic cases, new question phrasing, and exposed real regressions reported separately. No product tuning during first run.",
    "qa": qa,
    "controlled_review": review,
    "real_review": real,
    "scoring": {
        "review": "Exact three-way label agreement on all rows; operational abstention and false-safe counts separately. Never exclude unavailable from denominator. Unclear is not correct on known changed/same labels.",
        "qa": "Mechanical completeness and citation existence are screens only. Agent source audit separately labelled; independent human correctness pending. Sources are labelled anchors, not exhaustive relevant sets.",
        "baselines": "Review: normalized exact text difference (not a semantic classifier); strict safety triage means all non-same rows require manual review. Retrieval: existing lexical bridge vs hybrid, same Chinese query and document scope, top10. No arbitrary ratio threshold tuning.",
        "time": "Single first-pass wall time, model warm, vector session initially cold; no hardware benchmark or user time claim. Human study must measure correct decisions as well as time.",
    },
}
raw = json.dumps(protocol, ensure_ascii=False, indent=2).encode("utf-8")
(folder / "protocol.json").write_bytes(raw)
files = {
    str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted((ROOT / "backend").glob("*.py"))
}
freeze = {
    "created_at": datetime.now(UTC).isoformat(),
    "protocol_sha256": hashlib.sha256(raw).hexdigest(),
    "code_sha256": files,
    "counts": {
        "qa": len(qa),
        "controlled_review": len(review),
        "exposed_real_regression": len(real),
    },
    "rule": "Never edit protocol after first inference; any revised dataset gets a new version. No selective omission of failed cases.",
}
(folder / "freeze.json").write_text(
    json.dumps(freeze, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(freeze["counts"]))
