"""Transparent proposal checks: expose missing choices, never certify scientific merit."""

import re


def fixed_attention_dimensions(text):
    """Flag positive instructions fixing both dimensions, not warnings against doing so."""
    fixed_model = fixed_head = False
    for clause in re.split(r"[，。；;\n]", text):
        if not re.search(r"固定|不变", clause) or re.search(
            r"不能|不得|不要|不可|不应|不再|无需|不固定|并非固定", clause
        ):
            continue
        fixed_model |= bool(re.search(r"\bd_?model\b", clause, re.IGNORECASE))
        fixed_head |= bool(re.search(r"\bd_?(?:k|v|head)\b", clause, re.IGNORECASE))
    return fixed_model and fixed_head


def assess_plan(fields):
    text = "\n".join(fields.values())
    evaluation = fields.get("evaluation_plan", "")
    section = re.search(r"数据及训练测试划分[:：]\s*([\s\S]*?)(?:\n\n|$)", evaluation)
    split = section.group(1) if section else evaluation
    issues = []
    if re.search(r"待选择|待确定|待测|需核对许可|待选", text):
        issues.append("冻结任务、数据集及许可、硬件实测和判定阈值；文中仍有待定项。")
    if re.search(r"划分|小数据集", split) and not re.search(
        r"\d+\s*%|\d+\s*[:：/]\s*\d+|官方.*划分|官方.*split", split, re.IGNORECASE
    ):
        issues.append(
            "明确训练/验证/测试划分或沿用官方划分；只写按比例或小数据集不足以复现。"
        )
    if re.search(r"WikiText|语言建模", text, re.IGNORECASE) and re.search(
        r"BLEU", evaluation, re.IGNORECASE
    ):
        issues.append(
            "候选任务含语言建模，但指标写了 BLEU；先确定任务。语言建模通常核对困惑度或交叉熵，翻译任务才考虑 BLEU。"
        )
    if re.search(r"GLUE", text, re.IGNORECASE) and re.search(
        r"BLEU", evaluation, re.IGNORECASE
    ):
        issues.append(
            "GLUE 候选任务与 BLEU 可能不匹配；逐项核对所选任务的官方指标，不能直接沿用翻译论文指标。"
        )
    if re.search(r"注意力头", text) and fixed_attention_dimensions(text):
        issues.append(
            "检查注意力维度约束：标准多头注意力通常要求 d_model = h × d_head；不能在同时固定 d_model、d_k、d_v 时任意改变头数。先验证实现、整除条件和投影形状。"
        )
    planned = fields.get("method_plan", "") + "\n" + evaluation
    pretrained_use = any(
        "预训练" in clause
        and not re.search(
            r"不(?:使用|涉及|依赖|修改)|不能|不得|不要|不可|不应|不外推|不能外推|不自动外推|无需|避免",
            clause,
        )
        for clause in re.split(r"[。；;\n]", planned)
    )
    if pretrained_use and re.search(r"调整注意力头|改变.*头数|注意力头数量", planned):
        issues.append(
            "改变预训练模型头数不能只修改配置文件：需明确权重如何重组、是否重新训练，以及比较是否保持相同训练条件。先运行最小形状与前向检查。"
        )
    if re.search(r"耗时|延迟|latency", text, re.IGNORECASE) and not all(
        re.search(p, evaluation, re.IGNORECASE)
        for p in [r"预热|warm.?up", r"批|batch", r"重复|重复次数|中位|分位"]
    ):
        issues.append(
            "补齐计时预热、固定批大小与序列长度、重复次数及波动统计；GPU 计时还需同步。"
        )
    positive_significance = any(
        "显著" in clause
        and not re.search(r"不(?:宣称|预设|代表|证明)|不能|不得|未证明", clause)
        for clause in re.split(r"[，。；;\n]", evaluation)
    )
    if positive_significance and not re.search(
        r"置信区间|统计检验|confidence|bootstrap|p.?value", evaluation, re.IGNORECASE
    ):
        issues.append(
            "若使用显著性表述，需预先确定统计检验、重复运行及不确定性报告；不能凭均值变化宣称显著。"
        )
    if not re.search(r"(?:种子|seeds?)[^\n。]{0,40}\d", planned, re.IGNORECASE):
        issues.append(
            "明确独立完整运行的随机种子和次数（例如拟议 11、23、47），不能把同次训练的 batch 当作独立重复。"
        )
    if re.search(r"从零|从头|训练模型|模型训练", planned) and not re.search(
        r"\d+\s*(?:步|轮|epochs?|steps?)|(?:epoch|step)[^\n。]{0,15}\d",
        planned,
        re.IGNORECASE,
    ):
        issues.append(
            "填写各对照组相同的训练步数或轮数、优化器与批大小；先实测试跑预算，未指定训练量无法公平复现。"
        )
    if (
        re.search(r"失败|异常", planned)
        and re.search(r"重复运行|重试", planned)
        and not re.search(
            r"保留.{0,8}(?:失败|异常)|记录.{0,8}(?:失败|异常)|(?:失败|异常).{0,8}(?:记录|保留)",
            planned,
        )
    ):
        issues.append(
            "失败重跑必须保留失败原因、次数及原始日志，区分无效运行和有效负结果，不能只选成功重跑结果。"
        )
    return issues
