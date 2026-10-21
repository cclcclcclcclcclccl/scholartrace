"""Conservative duplicate detection and honest answer coverage notices."""

import re

from . import store


def reordered_key(text):
    """Recognize only exact clause permutations with the same leading named subject.

    Keep every word, condition, number and negation. Do not use fuzzy similarity
    or bag-of-words, which could erase changed relations between values and roles.
    """
    text = store.quote_normalize(text)
    subject = re.match(r"[A-Z][A-Za-z0-9_-]{1,}", text)
    if not subject or re.search(r"分别|依次|respectively", text, re.IGNORECASE):
        return None
    subject = subject[0]
    clauses = []
    for clause in re.split(r"[，；。;]|(?<!\d),(?!\d)", text):
        clause = clause.strip()
        if not clause:
            continue
        clause = re.sub(r"^而(?=在|训练|推理)", "", clause)
        clause = re.sub(r"^" + re.escape(subject) + r"(?=在|训练|推理)", "", clause)
        clause = re.sub(r"^在(?=训练时|推理时)", "", clause)
        value = re.sub(r"\s+", "", clause).casefold()
        if len(value) < 12:
            return None
        clauses.append(value)
    return (subject.casefold(), tuple(sorted(clauses))) if len(clauses) >= 2 else None


def duplicate_candidate(candidate, previous):
    for old in previous:
        if candidate.get("evidence_id") != old.get("evidence_id"):
            continue
        first = store.quote_normalize(candidate["text"])
        second = store.quote_normalize(old["text"])
        if first == second:
            return True
        key = reordered_key(first)
        if key is not None and key == reordered_key(second):
            return True
    return False


def answer_limitations(model_limitations, parts, candidate_count, retained_count):
    """A nonempty single-question answer must not hide dropped candidates."""
    notes = []
    if model_limitations or any(
        p["status"] == "unresolved" or p.get("omitted_candidate_count", 0) > 0
        for p in parts
    ):
        notes.append(
            "模型提示可能存在未覆盖内容；这未经全文核验，不能据此认定论文未报告。请结合下方原文复核。"
        )
    if not parts and candidate_count > retained_count:
        notes.append(
            f"另有 {candidate_count - retained_count} 条候选未进入最终回答（可能未通过核验或被去重）。当前回答不代表问题已完整覆盖，请核对下方原文。"
        )
    return " ".join(notes)
