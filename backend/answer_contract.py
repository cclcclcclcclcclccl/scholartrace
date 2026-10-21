"""Observable request-to-answer reading aids; never automatic completeness scores."""

import re

NOTICE = "按原问题中的明确要求整理；相关表述仅按词语定位，不代表已答全或已证实。未定位到表述也不代表论文未报告。"
FACETS = (
    (
        "mechanism",
        "机制与原因",
        r"为什么|为何|原因|机制|如何|怎样|\bwhy\b|\bhow\b",
        r"因为|由于|通过|梯度|机制|因此|because|gradient|mechanism|by\b",
    ),
    (
        "conditions",
        "实验与适用条件",
        r"条件|初始化|硬件|配置|\bconditions?\b|initialization|hardware",
        r"条件|初始化|硬件|GPU|配置|initialization|condition|hardware",
    ),
    (
        "limits",
        "范围与限制",
        r"限制|范围|任何|所有|边界|limitations?|scope|any\b|all\b",
        r"限制|范围|仅|不能|未|不|只|limit|scope|only|not\b",
    ),
    ("epochs", "训练轮数", r"epoch|轮数|多少轮", r"epoch|轮"),
    ("learning_rate", "学习率", r"学习率|learning.rate", r"学习率|learning.rate"),
    ("batch", "批大小", r"batch|批大小|批次大小", r"batch|批大小|批次"),
    (
        "parameters",
        "参数冻结与更新",
        r"冻结|哪些更新|哪些.*训练|freeze|frozen|trainable",
        r"冻结|更新|参数|frozen|trainable|update",
    ),
    (
        "data",
        "数据与样本",
        r"数据集|语料|样本|dataset|corpus|samples?",
        r"数据|语料|样本|dataset|corpus|sample",
    ),
    (
        "units",
        "数值与单位",
        r"单位|多少|数值|精确|\bGB\b|\bunits?\b|how many",
        r"\d|单位|million|billion|thousand|unit",
    ),
)


def checklist(question, claims):
    items = []
    for key, label, requested, related in FACETS:
        terms = list(
            dict.fromkeys(m[0] for m in re.finditer(requested, question, re.IGNORECASE))
        )
        if not terms:
            continue
        matches = [
            {
                "text": c["text"],
                "block_id": c.get("block_id", ""),
                "document_id": c.get("document_id", ""),
            }
            for c in claims
            if re.search(related, c.get("text", ""), re.IGNORECASE)
        ]
        items.append(
            {
                "id": key,
                "label": label,
                "requested_terms": terms,
                "related": matches,
                "status": "candidate" if matches else "unlocated",
                "followup": f"原问题：{question}\n本次仅补查原问题中的“{label}”（原词：{'、'.join(terms)}）。请给出对应原文和适用边界；证据不足时说明本轮不能回答，不推断论文未报告。",
            }
        )
    return {"question": question, "notice": NOTICE, "items": items}
