"""Narrow rejection of explicit named-variant update-count swaps, not entailment."""

import re

from .numeric_evidence import NUMBER, quantities
from .store import quote_normalize

NAME = re.compile(
    r"(?<![A-Za-z0-9_-])(?:[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+|[A-Z]{2,}[0-9]*)(?![A-Za-z0-9_-])"
)
UPDATE = re.compile(
    NUMBER.pattern + r"\s*(?:updates?\b|次(?:参数)?更新|更新次数|更新步数)",
    re.IGNORECASE,
)


def update_assignments(text, names):
    """Only bind a count after an explicit name within the same short clause.

    Comparisons, negations, alternatives, ranges and respectively lists are
    deliberately unassigned. Missing assignments are not evidence of support.
    """
    text = quote_normalize(text)
    pattern = re.compile(
        r"(?<![A-Za-z0-9_-])(?:"
        + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
        + r")(?![A-Za-z0-9_-])",
        re.IGNORECASE,
    )
    mentions = list(pattern.finditer(text))
    result = {name: set() for name in names}
    for index, mention in enumerate(mentions):
        end = mentions[index + 1].start() if index + 1 < len(mentions) else len(text)
        clause = text[mention.end() : end]
        clause = re.split(r"[;；。!?！？]|(?<!\d)\.(?!\d)", clause)[0]
        if len(clause) > 160 or re.search(
            r"\b(?:not|no|never|or|between|respectively|than|versus|vs)\b|不|未|并非|或者|分别|相比|相较|而非|至|到\s*\d|\d\s*[-–~]",
            clause,
            re.IGNORECASE,
        ):
            continue
        counts = list(UPDATE.finditer(clause))
        if len(counts) != 1:
            continue
        result[mention[0].casefold()].update(quantities(counts[0][0]))
    return result


def named_update_count_mismatch(claim, source):
    """Reject only contradictory singleton assignments for a shared named pair.

    Preserve source wording even if its interpretation seems counterintuitive;
    this rule never silently repairs the paper or asserts the paper is correct.
    """
    names = {m[0].casefold() for m in NAME.finditer(quote_normalize(source))}
    claimed_names = {m[0].casefold() for m in NAME.finditer(quote_normalize(claim))}
    shared = names & claimed_names
    if len(shared) < 2:
        return False
    # Unshared variants still delimit clauses. Otherwise a third model's count
    # could be assigned to the preceding shared model simply because that third
    # name is absent from the answer.
    boundaries = names | claimed_names
    asked = update_assignments(claim, boundaries)
    cited = update_assignments(source, boundaries)
    return any(
        len(asked[name]) == len(cited[name]) == 1 and asked[name] != cited[name]
        for name in shared
    )
