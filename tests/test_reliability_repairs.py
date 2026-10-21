"""Behavior regressions for scope, units and source-specific answer validation."""

import pytest
from test_review import run_response

from backend.claim_checks import duplicate_claim, semantic_overreach
from backend.numeric_evidence import unsupported_numbers
from backend.review_checks import (
    canonical_durations,
    identical_focused_fact,
    source_scope_warning,
)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("Duration is 180 seconds.", "Duration is 3 minutes."),
        ("Latency is 500 ms per sample.", "Latency is 0.5 seconds per sample."),
        ("Training lasts 2 hours.", "Training lasts 120 minutes."),
    ],
)
def test_explicit_duration_equivalence(old, new):
    result = run_response(
        {},
        {
            "status": "review_required",
            "note": {"note": "Duration change", "quote": old},
            "candidate": {"text": new},
        },
    )
    assert (
        result["decision"] == "same_claim"
        and result["method"] == "explicit_duration_equivalence"
    )


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("Latency is 500 ms per batch.", "Latency is 0.5 seconds per sample."),
        ("Duration is 180 seconds.", "Duration is 180 minutes."),
        ("Duration is at most 60 seconds.", "Duration is 1 minute."),
    ],
)
def test_duration_never_erases_denominator_or_bound(old, new):
    assert canonical_durations(old) != canonical_durations(new)


@pytest.mark.parametrize(
    ("note", "old", "new"),
    [
        ("GPU数量是否变化", "We use 4 GPUs.", "We use a different tokenizer."),
        (
            "条件 Q 下是否收敛",
            "The model converges under condition Q.",
            "The model converges under condition R.",
        ),
        (
            "基准 Alpha 的分数是否提高",
            "The score is 2 on benchmark Alpha.",
            "The score is 3 on benchmark Beta.",
        ),
        (
            "是否继续使用数据集",
            "We use dataset Delta.",
            "Dataset Delta is not reported.",
        ),
    ],
)
def test_missing_or_incomparable_evidence_stays_unclear_even_if_model_says_same(
    note, old, new
):
    result = run_response(
        {"decision": "same_claim"},
        {
            "status": "review_required",
            "note": {"note": note, "quote": old},
            "candidate": {"text": new},
        },
    )
    assert result["decision"] == "unclear" and result["method"] == "source_scope_guard"


def test_actual_negative_experiment_not_treated_as_reporting_omission():
    assert (
        source_scope_warning(
            "是否使用测试数据", "We use test samples.", "We do not use test samples."
        )
        is None
    )
    assert (
        source_scope_warning(
            "条件 Q 下是否收敛",
            "The model converges under condition Q.",
            "The model does not converge under condition Q.",
        )
        is None
    )


def test_unchanged_focus_preserves_separate_source_sentences_and_scope():
    assert identical_focused_fact(
        "编码器层数",
        "The encoder has 4 layers. The decoder has 8 layers.",
        "The encoder has 4 layers. The decoder has 9 layers.",
    ) == ["The encoder has 4 layers."]
    assert (
        identical_focused_fact(
            "GPU数量",
            "We use 4 GPUs. This applies only to inference.",
            "We use 4 GPUs. This applies only to training.",
        )
        is None
    )


def test_source_title_identity_not_measured_value_whitelist():
    assert not unsupported_numbers(
        "Orion 13B 的窗口为2048", "The window is 2048.", source_title="Orion 13B"
    )
    assert unsupported_numbers(
        "Orion 30B 的窗口为2048", "The window is 2048.", source_title="Orion 13B"
    )
    assert unsupported_numbers(
        "Orion 13B 的窗口为8192", "The window is 2048.", source_title="Orion 13B"
    )
    assert unsupported_numbers(
        "模型有13B参数", "The window is 2048.", source_title="Orion 13B"
    )


def test_similar_numbers_do_not_merge_different_named_subjects():
    old = [{"text": "Atlas的数据集规模为900 million pairs。", "block_id": "one"}]
    assert not duplicate_claim("Boreal的数据集规模为900 million pairs。", "one", old)
    assert duplicate_claim("Atlas 的数据集规模为900 million pairs。", "one", old)


@pytest.mark.parametrize(
    ("claim", "source"),
    [
        ("数据未经筛选", "We collected data from the Internet."),
        ("采用随机抽样", "We collected samples."),
        ("结果统计显著", "The score is higher."),
    ],
)
def test_source_local_qualifiers_rejected(claim, source):
    assert semantic_overreach(claim, source)


def test_explicit_qualifiers_preserved():
    assert not semantic_overreach(
        "图文数据未经筛选和整理", "These image-text pairs are unfiltered and uncurated."
    )


def test_layer_question_with_quantity_word_is_scoped():
    assert identical_focused_fact(
        "编码器有多少层？",
        "The encoder has 8 layers. The decoder has 3 layers.",
        "The encoder has 8 layers. The decoder has 5 layers.",
    ) == ["The encoder has 8 layers."]


@pytest.mark.parametrize(
    "omission",
    [
        "The paper does not report the accuracy.",
        "The paper never specifies its teacher.",
        "We no longer describe the dataset.",
    ],
)
def test_active_reporting_omission_is_not_an_experiment(omission):
    assert (
        source_scope_warning("结果是否发生变化？", "The accuracy is 90%.", omission)[
            "kind"
        ]
        == "reporting_absence"
    )


def test_illustrative_values_cannot_be_default_configuration():
    source = "Figure 2: For illustration, here, W = 5."
    assert semantic_overreach("默认窗口大小为5", source)
    assert semantic_overreach("窗口W的值为5", source)
    assert not semantic_overreach("图中示例窗口大小为5", source)
    assert not semantic_overreach("默认窗口大小为5", "The default window size is 5.")


def test_cross_paper_subject_guard_never_treats_shared_mentions_as_ownership():
    from backend.claim_checks import foreign_paper_subject, named_paper_owners

    owners = named_paper_owners(
        "Atlas 与 Boreal 比较",
        {"a": "Atlas. Atlas. Atlas.", "b": "Boreal. Boreal. Atlas."},
    )
    assert owners == {"Boreal": "b"}  # Atlas is not dominant enough.
    assert foreign_paper_subject("Boreal的数据量为3", "a", owners)
    assert not foreign_paper_subject("Boreal的数据量为3", "b", owners)
    assert not foreign_paper_subject("比较对象是Boreal", "a", owners)
    assert not foreign_paper_subject("BorealPlus的数据量为3", "a", owners)
