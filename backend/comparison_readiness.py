"""Audit a curated comparison snapshot, without judging scientific comparability."""

import re

NOTICE = "仅检查当前已整理格及其摘录中的线索；空格是待补查，相同单位不证明可比，不同单位也可能可以换算。"
UNITS = {
    "%": r"%|percent\b|百分比",
    "ms": r"\d\s*ms\b|\bmilliseconds?\b|毫秒",
    "s": r"\d\s*s\b|\bseconds?\b|(?<!毫)秒",
    "hours": r"\bhours?\b|小时",
    "GB": r"(?<![A-Za-z])GB\b|\bgigabytes?\b",
    "tokens": r"\btokens?\b|词元",
    "samples": r"\bsamples?\b|样本",
}
STAGES = {
    "预训练": r"pre[- ]?train|预训练",
    "微调": r"fine[- ]?tun|微调",
    "推理": r"inference|推理",
}


def audit(content):
    papers = []
    for paper in content["papers"]:
        cells = paper["cells"]
        metric = (cells.get("metric") or {}).get("quote", "")
        conditions = (cells.get("conditions") or {}).get("quote", "")
        units = [
            name
            for name, pattern in UNITS.items()
            if re.search(pattern, metric, re.IGNORECASE)
        ]
        papers.append(
            {
                "document_id": paper["document_id"],
                "title": paper["title"],
                "missing": [key for key in content["fields"] if not cells.get(key)],
                "units": units,
                "stages": [
                    name
                    for name, pattern in STAGES.items()
                    if re.search(pattern, conditions, re.IGNORECASE)
                ],
            }
        )
    hints = []
    for key, label in (
        ("units", "指标摘录中的单位线索不同，请核对量纲、定义与换算"),
        ("stages", "实验条件摘录中的阶段线索不同，请核对是否在比较同一训练或推理阶段"),
    ):
        known = [frozenset(p[key]) for p in papers if p[key]]
        if len(known) >= 2 and len(set(known)) > 1:
            hints.append(label)
    return {
        "notice": NOTICE,
        "papers": papers,
        "hints": hints,
        "missing_cells": sum(len(p["missing"]) for p in papers),
        "questions": [
            "研究对象、数据集及划分是否一致？",
            "指标定义、优劣方向和单位是否一致？",
            "训练／推理阶段、硬件与计算预算是否一致？",
            "适用条件与限制是否允许当前比较？",
        ],
    }
