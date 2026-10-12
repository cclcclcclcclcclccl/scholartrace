from decimal import Decimal

import pytest

from backend.numeric_evidence import quantities, unsupported_numbers
from backend.research import valid_claims


@pytest.mark.parametrize(
    "claim,quote",
    [
        ("隐藏宽度为128", "H=768, A=12, Total Parameters=110M"),
        ("BERT LARGE 隐藏宽度为256", "L=24, H=1024, A=16, Total Parameters=340M"),
        ("分数为41.8", "The score was 41.0."),
        ("共1000步", "100 steps"),
        ("变化为0.5", "The change was -0.5."),
    ],
)
def test_absent_numbers_are_rejected(claim, quote):
    assert unsupported_numbers(claim, quote)


@pytest.mark.parametrize(
    "claim,quote",
    [
        ("GPT-3 参数为1750亿", "GPT-3 175.0B"),
        ("参数110M", "110 million parameters"),
        ("词数为25亿", "2,500M words"),
        ("预热2,000步，学习率0.00025", "2000 updates, rate 2.5e-4"),
        ("学习率2.5 × 10^{-4}", "max learning rate 2.5e-4"),
        ("训练100轮，批大小64", "100 epochs with minibatches of 64 sequences"),
        ("使用2个模型", "We use two models."),
        ("概率为0.8", "80% probability"),
    ],
)
def test_explicit_numeric_notations_and_units_are_preserved(claim, quote):
    assert not unsupported_numbers(claim, quote)


def test_model_alias_number_is_not_a_measurement():
    assert quantities("GPT-1 使用12层，GPT3 总参数175B") == {
        Decimal(12),
        Decimal("175e9"),
    }
    assert quantities("GPT-1预训练100轮") == {Decimal(100)}
    assert quantities("模型GPT3的维度是12288") == {Decimal(12288)}


def test_a_real_quote_does_not_legitimize_fabricated_numbers():
    text = "BERTBASE contains 110M parameters and BERTLARGE contains 340M parameters."
    blocks = [{"id": "b", "document_id": "doc", "text": text, "page": 8}]
    value = {
        "claims": [
            {
                "text": "BERT BASE 有12层，隐藏宽度128，总参数110M。",
                "evidence_id": "E1",
                "quote": text,
            }
        ]
    }
    assert valid_claims(value, blocks) == []
