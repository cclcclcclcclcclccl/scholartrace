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


PAGE_LOCATOR = re.compile(r"第\s*(\d+)\s*页|\b(?:PDF\s+)?page\s+(\d+)\b", re.IGNORECASE)
MONTHS = {
    name.lower(): i
    for i, name in enumerate(
        (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        start=1,
    )
}
YEAR_MONTH = re.compile(
    r"(?<!\d)(?P<year>\d{4})\s*年\s*(?P<month>\d{1,2})\s*月"
    r"|\b(?P<english>" + "|".join(MONTHS) + r")\s+(?P<en_year>\d{4})\b",
    re.IGNORECASE,
)


def year_month_pair(match):
    if match["english"]:
        return int(match["en_year"]), MONTHS[match["english"].lower()]
    return int(match["year"]), int(match["month"])


def without_verified_page_locators(text, page):
    """Only trusted source metadata can exempt a page locator, never a measured value."""
    if type(page) is not int or page < 1:
        return text
    return PAGE_LOCATOR.sub(lambda m: "" if int(m[1] or m[2]) == page else m[0], text)


def unsupported_numbers(claim, quote, context=(), source_title="", source_page=None):
    if type(source_page) is int and source_page > 0:
        wrong_pages = {
            Decimal(m[1] or m[2])
            for m in PAGE_LOCATOR.finditer(claim)
            if int(m[1] or m[2]) != source_page
        }
        if wrong_pages:
            return wrong_pages
        claim = without_verified_page_locators(claim, source_page)
    # A literal model designation from this source's title is identity, not a new
    # measurement. Never whitelist a naked number or a different-sized variant.
    for name in re.findall(
        r"[A-Za-z][A-Za-z-]*(?: +[A-Za-z][A-Za-z-]*){0,2} +\d+(?:\.\d+)?[BM](?![A-Za-z0-9])",
        source_title,
    ):
        claim = re.sub(
            r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])",
            " ",
            claim,
            flags=re.IGNORECASE,
        )
    evidence = quote + "\n" + "\n".join(context)
    # A translated month is supported only by the SAME year/month pair in the
    # citation. Do not whitelist a naked month number or mix dates across years.
    dates = {year_month_pair(m) for m in YEAR_MONTH.finditer(evidence)}
    claim_dates = list(YEAR_MONTH.finditer(claim))
    for match in claim_dates:
        year, month = year_month_pair(match)
        if not 1 <= month <= 12 or (year, month) not in dates:
            return {Decimal(year), Decimal(month)}
    # Multiple dates often belong to different experimental variants or ranges.
    # Keep those under the existing strict numeric check until scoped date-range
    # validation is available; equivalence alone cannot establish attribution.
    if len(claim_dates) == 1 and len(dates) == 1:
        claim = YEAR_MONTH.sub(" ", claim)
    return quantities(claim) - quantities(evidence)
