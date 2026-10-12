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
