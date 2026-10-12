"""Locate source quotes across PDF block boundaries without changing stored evidence."""

import re
from difflib import SequenceMatcher

from . import store


def exact_span(quote, text):
    # A number/word prefix is not an unchanged quote: 100 must not match 1000.
    start = 0
    while quote and (index := text.find(quote, start)) >= 0:
        end = index + len(quote)
        if not (
            (index and text[index - 1].isalnum() and quote[0].isalnum())
            or (end < len(text) and text[end].isalnum() and quote[-1].isalnum())
        ):
            return True
        start = index + 1
    return False


class SourceAligner:
    def __init__(self, blocks):
        self.blocks = blocks
        self.windows = []
        # Keep every original anchor, including when a sentence crosses a page.
        for size in range(1, 5):
            for index in range(len(blocks) - size + 1):
                parts = blocks[index : index + size]
                if parts[-1]["page"] - parts[0]["page"] > 1:
                    continue
                raw = "\n".join(p["text"] for p in parts)
                if len(raw) > 10000:
                    continue
                text = store.quote_normalize(raw)
                self.windows.append(
                    (parts, raw, text, set(re.findall(r"\w+", text.lower())))
                )
        # Across a page break, floats and page numbers can interrupt a continuing
        # paragraph. Try a second path only when those omissions are identified
        # from geometry/text; expose all skipped source blocks to the reviewer.
        self.skipped = {}
        positions = {b["id"]: i for i, b in enumerate(blocks)}
        body = [b for b in blocks if not self.layout_block(b)]
        for size in range(2, 5):
            for index in range(len(body) - size + 1):
                parts = body[index : index + size]
                if parts[-1]["page"] - parts[0]["page"] != 1:
                    continue
                before = positions[parts[0]["id"]]
                after = positions[parts[-1]["id"]]
                omitted = [b for b in blocks[before : after + 1] if b not in parts]
                if (
                    not omitted
                    or len(omitted) > 5
                    or any(not self.layout_block(b) for b in omitted)
                ):
                    continue
                raw = "\n".join(p["text"] for p in parts)
                if len(raw) > 10000:
                    continue
                text = store.quote_normalize(raw)
                self.windows.append(
                    (parts, raw, text, set(re.findall(r"\w+", text.lower())))
                )
                self.skipped[tuple(p["id"] for p in parts)] = omitted

    @staticmethod
    def layout_block(block):
        text = block["text"].strip()
        lines = text.splitlines()
        is_footer = (
            bool(re.fullmatch(r"\d{1,4}", text))
            and block["bbox"][1] > block["height"] * 0.9
        )
        is_caption = bool(re.match(r"^(?:Table|Figure|Fig\.)\s+\d+[.:]?", text))
        is_table = (
            len(lines) >= 12
            and sum(bool(re.match(r"^[+−-]?\d", line)) for line in lines)
            >= len(lines) * 0.3
        )
        return is_footer or is_caption or is_table

    def candidate(self, parts, raw):
        first = parts[0]
        return {
            **first,
            "text": raw,
            "segments": parts,
            "skipped_context": self.skipped.get(tuple(p["id"] for p in parts), []),
            "alignment_method": "single_block"
            if len(parts) == 1
            else "adjacent_blocks",
        }

    def locate(self, source):
        quote = store.quote_normalize(source)
        if not quote:
            return {"candidate": None, "similarity": 0.0, "status": "unlocated"}
        for parts, raw, text, _ in self.windows:
            if exact_span(quote, text):
                return {
                    "candidate": self.candidate(parts, raw),
                    "similarity": 1.0,
                    "status": "retained",
                    "matched_quote": quote,
                }
        tokens = set(re.findall(r"\w+", quote.lower()))
        ranked = sorted(
            self.windows,
            key=lambda w: len(tokens & w[3]) / max(1, len(tokens | w[3])),
            reverse=True,
        )[:24]
        best, score = None, 0.0
        for parts, raw, text, _ in ranked:
            # Similarity ranks candidates only. It never establishes that a quote survived.
            similarity = min(
                0.998,
                SequenceMatcher(
                    None, quote.lower(), text.lower(), autojunk=False
                ).ratio(),
            )
            if similarity > score:
                best, score = self.candidate(parts, raw), similarity
        return {
            "candidate": best,
            "similarity": score,
            "status": "review_required" if score >= 0.4 else "unlocated",
        }


EXPLANATIONS = {
    "retained": "引用原文在新版本中仍存在，已兼容拆段、合段与位置移动；适用条件仍需结合上下文核对。",
    "review_required": "找到变化候选，请检查数字、条件和论断；文字相近不等于结论不变。",
    "unlocated": "未可靠定位对应原文；可能有改写、重排或删除，不等于已删除。",
}
