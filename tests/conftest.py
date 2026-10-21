"""Declare optional official-paper fixtures instead of requiring private local data."""

from pathlib import Path

import pytest

CORPUS = Path(__file__).resolve().parents[1] / "data/competition/pdf"
REQUIRED_PDFS = {
    "test_document_alias_edit_is_bounded_and_preserves_original_metadata": ["language_understanding_paper.pdf"],
    "test_native_table_rows_match_real_source_geometry": ["1706.03762v1.pdf"],
    "test_table_header_is_real_source_and_disambiguates_model_and_head_dimensions": ["2005.14165v4.pdf"],
    "test_two_accounts_isolate_document_access_and_preferences": ["1706.03762v1.pdf"],
    "test_reranked_definition_recovers_adjacent_specification": ["N19-1423.pdf"],
    "test_matrix_enters_version_impact_without_duplicating_cells": ["1706.03762v1.pdf", "1706.03762v7.pdf"],
}


def pytest_collection_modifyitems(items):
    for item in items:
        missing = [name for name in REQUIRED_PDFS.get(item.name, []) if not (CORPUS / name).exists()]
        if missing:
            item.add_marker(pytest.mark.skip(reason="Official corpus absent: " + ", ".join(missing) + "; see docs/测试资料准备.md"))
