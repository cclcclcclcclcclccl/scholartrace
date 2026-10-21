from backend.quantity_roles import named_update_count_mismatch

SOURCE = (
    "The Pre-LN model can be trained faster. For example, the Post-LN model "
    "achieves 1.69 validation loss at 500k updates while the Pre-LN model "
    "achieves similar validation loss at 700k updates, which suggests there "
    "is a 40% speed-up rate."
)


def test_observed_swap_is_rejected_even_when_both_numbers_exist():
    assert named_update_count_mismatch(
        "Pre-LN 模型在500k更新次数时达到的验证损失与Post-LN模型在700k更新次数时的验证损失相似。",
        SOURCE,
    )


def test_literal_source_is_preserved_without_correcting_apparent_contradiction():
    assert not named_update_count_mismatch(
        "Post-LN 在50万次更新时达到相应损失，Pre-LN 在70万次更新时达到相似损失。",
        SOURCE,
    )
    assert not named_update_count_mismatch(SOURCE, SOURCE)


def test_generalizes_to_other_names_and_scaled_counts():
    source = (
        "Alpha-A reaches the target at 2000 updates; Beta-B reaches it at 4000 updates."
    )
    assert named_update_count_mismatch(
        "Alpha-A在4k次更新时达标；Beta-B在2k次更新时达标。", source
    )
    assert not named_update_count_mismatch(
        "Beta-B在4千次更新时达标；Alpha-A在2千次更新时达标。", source
    )


def test_ambiguous_assignments_are_not_guessed():
    source = (
        "Alpha-A uses 2000 or 4000 updates; Beta-B uses between 2000 and 4000 updates."
    )
    assert not named_update_count_mismatch(
        "Alpha-A uses 4000 updates; Beta-B uses 2000 updates.", source
    )
    assert not named_update_count_mismatch(
        "Alpha-A does not use 4000 updates; Beta-B does not use 2000 updates.",
        "Alpha-A uses 2000 updates; Beta-B uses 4000 updates.",
    )
    assert not named_update_count_mismatch(
        "Alpha-A和Beta-B分别使用4000、2000次更新。",
        "Alpha-A and Beta-B use 2000 and 4000 updates respectively.",
    )


def test_unrelated_metrics_and_other_paper_context_do_not_supply_update_counts():
    assert not named_update_count_mismatch(
        "Alpha-A得分4，Beta-B得分2。",
        "Alpha-A uses 2000 updates; Beta-B uses 4000 updates.",
    )
    assert not named_update_count_mismatch(
        "Alpha-A uses 4000 updates; Beta-B uses 2000 updates.",
        "Gamma-C uses 2000 updates; Delta-D uses 4000 updates.",
    )


def test_guard_runs_at_real_claim_validation_boundary():
    from backend.research import valid_claims

    block = {"id": "b", "document_id": "p", "page": 1, "title": "Paper", "text": SOURCE}
    claim = {
        "evidence_id": "E1",
        "quote": SOURCE,
        "text": "Pre-LN 模型在500k更新次数时达到的验证损失与Post-LN模型在700k更新次数时的验证损失相似。",
    }
    assert valid_claims({"claims": [claim]}, [block]) == []
    claim["text"] = (
        "Post-LN在500k次更新时达到对应损失，Pre-LN在700k次更新时达到相似损失。"
    )
    assert len(valid_claims({"claims": [claim]}, [block])) == 1


def test_third_model_not_mentioned_in_answer_still_delimits_ownership():
    source = "Alpha-A is a baseline for Gamma-C at 2000 updates; Beta-B uses 4000 updates."
    # Source supplies no unambiguous Alpha-A update count. This rule must not
    # borrow Gamma-C's count to invent a contradiction (nor claim support).
    assert not named_update_count_mismatch(
        "Alpha-A uses 4000 updates; Beta-B uses 4000 updates.", source
    )
    assert named_update_count_mismatch(
        "Alpha-A uses 4000 updates; Beta-B uses 2000 updates.", source
    )
