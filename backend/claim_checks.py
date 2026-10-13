"""Conservative, inspectable rejection rules, not a semantic accuracy score."""

import re
import unicodedata
from difflib import SequenceMatcher

from . import store


def support_passages(quote, maximum=1600):
    """Offer source-only spans so a reviewer cannot rewrite a table or quotation."""
    source = store.quote_normalize(quote)
    sentences = re.split(r"(?<=[.!?。！？])\s+(?=[A-Z\u4e00-\u9fff])", source)
    candidates = [source] if len(source) <= maximum else []
    for start in range(len(sentences)):
        for size in range(1, min(4, len(sentences) - start) + 1):
            candidates.append(" ".join(sentences[start : start + size]))
    # Long unpunctuated PDF paragraphs still get overlapping, exact passages.
    if len(source) > maximum:
        candidates.extend(
            source[i : i + maximum] for i in range(0, len(source), maximum // 2)
        )
    return [""] + list(dict.fromkeys(s for s in candidates if 12 <= len(s) <= maximum))


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
    return bool(
        window_claim and training_source and not context_source
    ) or negative_result_mismatch(claim, quote)


def negative_result_mismatch(claim, quote):
    """Reject narrow, observable swaps of a negative result's dimensional variant.

    This is a conservative guard for explicit 1D/2D/3D mentions, not a general
    semantic verifier. A claim of missing proof also needs explicit source support.
    """
    source = unicodedata.normalize("NFKC", quote)
    if re.search(r"部署时|during deployment", claim, re.IGNORECASE) and not re.search(
        r"deploy|production|merge|absorb|inference|部署|推理", source, re.IGNORECASE
    ):
        return True
    if re.search(
        r"(?:可以|能够).{0,65}(?:不同任务|different tasks).{0,65}(?:一次|single|one forward)",
        claim,
        re.IGNORECASE,
    ) and not re.search(r"batch|混合", source, re.IGNORECASE):
        return True
    for maximum in re.finditer(
        r"up\s+to\s+(\d+(?:\.\d+)?)\s*[×x]", source, re.IGNORECASE
    ):
        if re.search(rf"{re.escape(maximum[1])}\s*倍", claim) and not re.search(
            r"最高|最多|至多|可达|上限|高达", claim
        ):
            return True
    # Explicit hardware levels must occur in the cited passage, not just elsewhere
    # in the model's context. This does not establish relationships between them.
    for term in ("HBM", "SRAM"):
        if re.search(
            rf"(?<![A-Za-z0-9_]){term}(?![A-Za-z0-9_])", claim, re.IGNORECASE
        ) and not re.search(rf"\b{term}\b", source, re.IGNORECASE):
            return True
    if (
        re.search(
            r"not\s+observed|did\s+not\s+observe|have\s+not\s+found",
            source,
            re.IGNORECASE,
        )
        and re.search(
            r"(?:没有|不会|并无|不)(?:带来|产生|存在).{0,12}(?:提升|增益|改善)", claim
        )
        and not re.search(r"观察|观测|发现|实验中|实验下|该设置|这些设置", claim)
    ):
        return True
    if re.search(r"最优", claim) and not re.search(
        r"optimal|optimum|最优", source, re.IGNORECASE
    ):
        return True
    if re.search(r"(?:运行时间|耗时|时间复杂度).{0,35}线性", claim) and not re.search(
        r"linear|O\s*\(\s*N\s*\)|线性", source, re.IGNORECASE
    ):
        return True
    if re.search(r"(?<!不)(?:可以|能够|能)直接.{0,25}(?:混合|不同任务)", claim) and (
        not re.search(r"batch|mix", source, re.IGNORECASE)
        or re.search(r"not straightforward|cannot|not possible", source, re.IGNORECASE)
    ):
        return True
    if (
        re.search(
            r"we\s+(?:speculate|hypothesize|conjecture)\s+that", source, re.IGNORECASE
        )
        and re.search(r"由于|因为|导致|证明|因此", claim)
        and not re.search(r"推测|猜测|假设|可能|或许|尚未|未证明", claim)
    ):
        return True
    if re.search(
        r"(?:未|没有|并未)[^，。；]{0,18}(?:证明|比较)", claim
    ) and not re.search(r"\bnot\b|\bno\b|without|fail|未|没有", source, re.IGNORECASE):
        return True
    negative = re.search(
        r"(?:not\s+observed|no)[^.]{0,100}(?:gains?|improvements?)[^.]{0,40}(?:using|with)\s+([^.]{1,100})",
        source,
        re.IGNORECASE,
    )
    if not negative:
        return False
    expected = set(re.findall(r"\b[123]D\b", negative[1], re.IGNORECASE))
    normalized = claim.replace("一维", "1D").replace("二维", "2D").replace("三维", "3D")
    for clause in re.split(r"[，。；]", normalized):
        if re.search(
            r"未观察|没有观察|无.{0,8}(?:增益|提升)|未.{0,8}(?:增益|提升)", clause
        ):
            targets = set(re.findall(r"[123]D", clause, re.IGNORECASE))
            if (
                expected
                and targets
                and {x.upper() for x in targets} != {x.upper() for x in expected}
            ):
                return True
    return False


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
