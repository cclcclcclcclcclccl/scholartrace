"""Reject numeric values absent from the cited evidence; this is not semantic proof."""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from .store import quote_normalize

SCALES = {
    "k": "1e3",
    "thousand": "1e3",
    "千": "1e3",
    "m": "1e6",
    "million": "1e6",
    "百万": "1e6",
    "b": "1e9",
    "billion": "1e9",
    "十亿": "1e9",
    "万": "1e4",
    "亿": "1e8",
    "%": "0.01",
}
NUMBER = re.compile(
    r"(?<![A-Za-z0-9_.])([+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:e[+-]?\d+)?)"
    r"(?:\s*(billion|million|thousand|十亿|百万|万|亿|千|%|[kmb](?![a-z])))?",
    re.IGNORECASE,
)


def quantities(text):
    value = unicodedata.normalize("NFKC", quote_normalize(text)).replace("−", "-")
    value = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", value)
    value = re.sub(
        r"(\d+(?:\.\d+)?)\s*[×x*]\s*10\s*\^?\s*\{?\s*([+-]?\d+)\}?", r"\1e\2", value
    )
    # Names such as GPT-3, GPT3 and v7 identify sources, not measured quantities.
    value = re.sub(
        r"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z_]*-?\d+[A-Za-z0-9]*(?![A-Za-z0-9_])",
        " ",
        value,
    )
    result = set()
    for match in NUMBER.finditer(value):
        try:
            result.add(
                Decimal(match[1]) * Decimal(SCALES.get((match[2] or "").lower(), "1"))
            )
        except InvalidOperation:
            continue
    # English prose often spells out small counts.
    for i, word in enumerate(
        [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
        ]
    ):
        if re.search(r"\b" + word + r"\b", value, re.IGNORECASE):
            result.add(Decimal(i))
    return result


def unsupported_numbers(claim, quote, context=()):
    evidence = quote + "\n" + "\n".join(context)
    return quantities(claim) - quantities(evidence)
