"""Conservative, inspectable rejection rules, not a semantic accuracy score."""

import re
from difflib import SequenceMatcher


def semantic_overreach(claim, quote):
    """Training sequences do not establish the model's supported context limit."""
    window_claim = re.search(
        r"上下文(?:窗口|长度|上限)|最大(?:输入|序列)长度|context\s+(?:window|length|limit)",
        claim,
        re.IGNORECASE,
    )
    training_source = re.search(
        r"(?:train\w*|mini.?batch)[\s\S]{0,250}(?:sequence|token)|sequences?\s+of\s+\d+",
        quote,
        re.IGNORECASE,
    )
    context_source = re.search(
        r"context|n.ctx|maximum\s+(?:sequence|input)\s+length|上下文|最大序列长度",
        quote,
        re.IGNORECASE,
    )
    return bool(window_claim and training_source and not context_source)


def duplicate_claim(text, block_id, accepted):
    normalized = re.sub(r"[^\w]", "", text).casefold()
    numbers = re.findall(r"\d+(?:\.\d+)?", text)
    for old in accepted:
        # Never merge claims with distinct sources, numbers or polarities.
        if (
            old["block_id"] != block_id
            or re.findall(r"\d+(?:\.\d+)?", old["text"]) != numbers
        ):
            continue
        polarity = r"不|无|未|没有|not|never|without"
        if bool(re.search(polarity, text, re.IGNORECASE)) != bool(
            re.search(polarity, old["text"], re.IGNORECASE)
        ):
            continue
        previous = re.sub(r"[^\w]", "", old["text"]).casefold()
        if (
            normalized == previous
            or SequenceMatcher(None, normalized, previous).ratio() >= 0.92
        ):
            return True
    return False


def prune_repeated_facts(claims):
    """Drop only narrow numeric restatements from the same evidence and named variant.

    Richer experimental conditions and different model names are never collapsed.
    This deliberately handles simple architecture restatements, not arbitrary prose.
    """
    aliases = [
        ("layers", r"层数|层"),
        ("hidden", r"隐藏(?:状态)?(?:维度|大小)|隐藏层维度"),
        ("heads", r"注意力头(?:数|数量)?"),
    ]

    def facts(text):
        output = set()
        for key, names in aliases:
            for m in re.finditer(
                rf"(?:{names})(?:分别)?(?:是|为|有|：|:)?\s*(\d[\d,]*)", text
            ):
                output.add((key, m[1].replace(",", "")))
            if key == "layers":
                output.update((key, m[1]) for m in re.finditer(r"(\d+)\s*层", text))
        return output

    def entities(text):
        return set(re.findall(r"[A-Za-z][A-Za-z0-9_-]*", text.lower())) - {
            "transformer",
            "only",
            "decoder",
            "decoder-only",
            "encoder",
            "encoder-only",
        }

    def simple(text):
        value = re.sub(r"本论文的|该模型的|模型的|本模型的", "", text)
        value = re.sub(r"[A-Za-z][A-Za-z0-9_-]*", "", value)
        for _, names in aliases:
            value = re.sub(names, "", value)
        value = re.sub(
            r"分别|是|为|有|个|和|以及|且|的|\d|[\s,，。；;：:、-]", "", value
        )
        return not value

    def roles(value):
        return set(re.findall(r"encoder|decoder", value.lower()))

    result = []
    for i, claim in enumerate(claims):
        own = facts(claim["text"])
        redundant = False
        if own and simple(claim["text"]):
            for j, other in enumerate(claims):
                if i == j or claim["block_id"] != other["block_id"]:
                    continue
                if entities(claim["text"]) != entities(other["text"]):
                    continue
                if roles(claim["text"]) and roles(claim["text"]) != roles(
                    other["text"]
                ):
                    continue
                if re.search(
                    r"不|未|没有|假设|若|如果|训练|推理|编码器|解码器", claim["text"]
                ):
                    continue
                if re.search(r"不|未|没有|假设|若|如果|训练时|推理时", other["text"]):
                    continue
                other_facts = facts(other["text"])
                if own < other_facts or (own == other_facts and j < i):
                    redundant = True
                    break
        if not redundant:
            result.append(claim)
    return result
