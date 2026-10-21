"""Bilingual concept hints and bounded lexical coverage, without paper-specific answers."""

import re

from . import store

CONCEPTS = [
    (
        r"数据.{0,15}(?:规模|数量)|预训练数据|training data|dataset size|图文对",
        "training dataset million hours pairs examples",
        r"\b(?:million|billion|hours|pairs|examples)\b",
    ),
    (
        r"输入|输出|\binputs?\b|\boutputs?\b",
        "inputs outputs",
        r"\binputs?\b.{0,500}\boutputs?\b|\boutputs?\b.{0,500}\binputs?\b",
    ),
    (r"初始化|initiali[sz]", "initialization", r"initiali[sz]"),
    (r"合并|merge", "merge weights", r"merge|W\s*=|absorb"),
    (
        r"不同任务|混合处理|multiple tasks|different tasks",
        "batch different tasks limitations",
        r"batch.{0,100}(?:different|tasks)|different.{0,80}batch",
    ),
    (
        r"精确|近似|exact|approximate",
        "exact approximate attention",
        r"exact|approximate",
    ),
]


def concept_evidence(question, identifiers, maximum=4):
    if not identifiers:
        return []
    found = []
    seen = set()
    for trigger, query, required in CONCEPTS:
        if not re.search(trigger, question, re.IGNORECASE):
            continue
        candidates = store.search(
            query,
            identifiers,
            limit=60
            if query
            in {
                "exact approximate attention",
                "training dataset million hours pairs examples",
            }
            else 12,
        )
        if query == "training dataset million hours pairs examples":
            # Prefer passages covering the explicitly named datasets/model names.
            # Units and counts still come from source text, never from this rule.
            entities = set(re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", question.lower()))
            candidates.sort(
                key=lambda b: (
                    -sum(
                        bool(
                            re.search(
                                r"\b" + re.escape(term) + r"\b",
                                b["text"],
                                re.IGNORECASE,
                            )
                        )
                        for term in entities
                    ),
                    b.get("page", 0),
                )
            )
        if query == "inputs outputs":
            # Capability definitions must compete with long prompt/response examples.
            # This selects source prose, never substitutes a model name or an answer.
            candidates.sort(
                key=lambda b: (
                    not bool(
                        re.search(
                            r"\b(?:accept|process|take)\w*\b.{0,180}\binputs?\b.{0,120}\b(?:produc|generat|return)\w*\b.{0,80}\boutputs?\b",
                            store.quote_normalize(b["text"]),
                            re.IGNORECASE,
                        )
                    )
                )
            )
        if query == "exact approximate attention":
            # A definition is a better first anchor for a method-category question
            # than a timing paragraph comparing many method categories.
            candidates.sort(
                key=lambda b: (
                    not bool(
                        re.search(
                            r"we (?:propose|present|introduce)|an? (?:\w+[- ]+){0,3}exact attention algorithm",
                            store.quote_normalize(b["text"]),
                            re.IGNORECASE,
                        )
                    ),
                    b.get("page", 0),
                )
            )
        accepted = 0
        for block in candidates:
            text = store.quote_normalize(block["text"])
            if (
                block["id"] in seen
                or len(text) < 70
                or not re.search(required, text, re.IGNORECASE)
            ):
                continue
            # Bibliography/title mentions are not methodological evidence.
            if not re.search(
                r"\b(?:we|our|when|uses?|using|is|are|can|however)\b",
                text,
                re.IGNORECASE,
            ):
                continue
            found.append(
                {**block, "retrieval_context": "explicit question concept: " + query}
            )
            seen.add(block["id"])
            accepted += 1
            if len(found) >= maximum:
                return found
            if accepted >= 1:
                break
    return found
