"""Narrow contradiction checks on selected source sentences, not semantic proof."""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from .store import quote_normalize

NUMBER = re.compile(
    r"(?<![\w.])[+-]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?(?!\w)"
)
NEGATION = re.compile(r"\b(?:not|never|no)\b", re.IGNORECASE)


def signature(text):
    text = unicodedata.normalize("NFKC", quote_normalize(text)).lower()
    values = []

    def replace(match):
        try:
            value = Decimal(match[0].replace(",", ""))
            values.append(str(value.normalize()))
        except InvalidOperation:
            values.append(match[0])
        return " <number> "

    skeleton = NUMBER.sub(replace, text)
    return re.sub(r"\s+", " ", skeleton).strip(), values


def consistency_warnings(old, new):
    old_key, old_values = signature(old)
    new_key, new_values = signature(new)
    warnings = []
    # Keep citation numbers visible: without reference mapping, they could be math.
    if old_key == new_key and old_values != new_values:
        warnings.append(
            {
                "kind": "numeric_difference",
                "old": old_values,
                "new": new_values,
                "reason": "两侧比较引文句式相同但数值不同，不能直接认定论断未变；需核对这些数字是否属于笔记关注的条件、指标或引用编号。",
            }
        )

    def without_negation(text):
        text = quote_normalize(text).lower()
        text = text.replace("n't", " not")
        return re.sub(r"\s+", " ", NEGATION.sub("", text)).strip()

    if without_negation(old) == without_negation(new) and bool(
        NEGATION.search(quote_normalize(old).replace("n't", " not"))
    ) != bool(NEGATION.search(quote_normalize(new).replace("n't", " not"))):
        warnings.append(
            {
                "kind": "negation_difference",
                "reason": "两侧比较引文存在明确否定词差异，不能直接认定论断未变；需人工核对适用范围。",
            }
        )
    return warnings


# Only explicit observable concepts; unknown observations are left to review.
FOCUS = [
    (r"GPU|显卡|图形处理器", r"\bGPUs?\b|显卡|图形处理器"),
    (r"批大小|批量大小|batch\s+size", r"\bbatch\s+size\b|批大小|批量大小"),
    (r"学习率|learning\s+rate", r"\blearning\s+rate\b|学习率"),
    (r"层数|多少层|几层|number\s+of\s+layers", r"\blayers?\b|层数"),
    (r"BLEU", r"\bBLEU\b"),
    (r"参数量|parameter\s+count", r"\bparameters?\b|参数量"),
]


def observation_warning(observation, old, new, selected_old, selected_new):
    def focused(text, pattern):
        sentences = re.split(r"(?<=[.!?。！？])\s+", quote_normalize(text))
        return [s for s in sentences if re.search(pattern, s, re.IGNORECASE)]

    for observation_pattern, source_pattern in FOCUS:
        if not re.search(observation_pattern, observation, re.IGNORECASE):
            continue
        if not focused(selected_old, source_pattern) or not focused(
            selected_new, source_pattern
        ):
            return {
                "kind": "observation_mismatch",
                "reason": "笔记明确关注的指标没有同时出现在两侧比较引文中；不能把其他内容的差异归为这条笔记的变化。",
            }
        old_focus, new_focus = (
            focused(old, source_pattern),
            focused(new, source_pattern),
        )
        if old_focus and old_focus == new_focus:
            return {
                "kind": "observation_mismatch",
                "reason": "笔记所关注指标的句子在两侧原文中相同；段落中其他内容的变化不足以证明这条笔记受影响，需核对上下文。",
            }
    return None


def canonical_durations(text):
    """Normalize explicit duration units, retaining order, denominator and context."""
    normalized = quote_normalize(text).lower()
    factors = {
        "ms": "0.001",
        "millisecond": "0.001",
        "milliseconds": "0.001",
        "s": "1",
        "second": "1",
        "seconds": "1",
        "min": "60",
        "minute": "60",
        "minutes": "60",
        "h": "3600",
        "hour": "3600",
        "hours": "3600",
    }

    def convert(match):
        value = Decimal(match[1]) * Decimal(factors[match[2]])
        return format(value.normalize(), "f") + " duration_seconds"

    return re.sub(
        r"(?<![\w.])(\d+(?:\.\d+)?)\s*(milliseconds?|seconds?|minutes?|hours?|ms|min|s|h)\b",
        convert,
        normalized,
    )


def source_scope_warning(observation, old, new):
    """Missing direct evidence cannot establish either stability or a change."""
    for trigger, concept in FOCUS:
        if re.search(trigger, observation, re.IGNORECASE) and (
            not re.search(concept, old, re.IGNORECASE)
            or not re.search(concept, new, re.IGNORECASE)
        ):
            return {
                "kind": "missing_observation_evidence",
                "reason": "观察明确要求的指标未同时出现在两版原文中；缺失不能证明未变或改变。",
            }
    # The question's explicit condition must remain available on both sides.
    conditions = re.findall(
        r"(?:条件\s*|condition\s+)([A-Za-z][A-Za-z0-9_-]*)", observation, re.IGNORECASE
    )
    for condition in conditions:
        pattern = (
            r"(?:condition\s+|条件\s*)" + re.escape(condition) + r"(?![A-Za-z0-9_-])"
        )
        if not re.search(pattern, old, re.IGNORECASE) or not re.search(
            pattern, new, re.IGNORECASE
        ):
            return {
                "kind": "condition_not_comparable",
                "reason": "观察指定的条件没有在两版证据中同时成立，不能用其他条件下的描述作确定判断。",
            }
    datasets = re.findall(
        r"(?:数据集|基准|dataset|benchmark)\s+([A-Za-z][A-Za-z0-9_-]*)",
        observation,
        re.IGNORECASE,
    )
    for name in datasets:
        pattern = (
            r"(?:dataset|benchmark|数据集|基准)\s+"
            + re.escape(name)
            + r"(?![A-Za-z0-9_-])"
        )
        if not re.search(pattern, old, re.IGNORECASE) or not re.search(
            pattern, new, re.IGNORECASE
        ):
            return {
                "kind": "dataset_not_comparable",
                "reason": "观察指定的数据集或基准未在两侧同时出现，不能跨基准判断同一测量是否变化。",
            }
    # Text explicitly describes a reporting omission, not a negative experiment.
    omission = r"(?:no longer|not|never)\s+(?:describ(?:e|es|ed)|report(?:s|ed)?|mention(?:s|ed)?|specif(?:y|ies|ied))\b|未(?:再)?(?:描述|报告|提及|说明)"
    if re.search(omission, old + "\n" + new, re.IGNORECASE) and not re.search(
        r"是否.{0,8}(?:描述|报告|提及)|reporting|documentation",
        observation,
        re.IGNORECASE,
    ):
        return {
            "kind": "reporting_absence",
            "reason": "证据只说明未再描述或报告，不能据此推断实验行为、使用情况或数值发生改变。",
        }
    return None


def identical_focused_fact(observation, old, new):
    """Recognize identical standalone numeric facts; avoid shared-condition changes."""
    if re.search(
        r"however|unless|except|only|condition|provided|限定|条件|仅|除非",
        old + " " + new,
        re.IGNORECASE,
    ):
        return None
    patterns = [
        concept
        for trigger, concept in FOCUS
        if re.search(trigger, observation, re.IGNORECASE)
    ]
    for entity, pattern in [
        (r"编码器|encoder", r"\bencoder\b"),
        (r"解码器|decoder", r"\bdecoder\b"),
    ]:
        if re.search(entity, observation, re.IGNORECASE):
            patterns = [pattern] if patterns else []
    if not patterns:
        return None
    pairs = []
    for pattern in patterns:

        def sentences(text, source_pattern=pattern):
            return [
                s
                for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", quote_normalize(text))
                if re.search(source_pattern, s, re.IGNORECASE)
            ]

        a, b = sentences(old), sentences(new)
        if not a or a != b or not all(re.search(r"\d", s) for s in a):
            return None
        pairs.extend(a)
    return list(dict.fromkeys(pairs))
