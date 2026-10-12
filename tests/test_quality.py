"""Failure-oriented regressions for evidence alignment and editable extraction."""

import csv
import io
import json

import pytest
from fastapi.testclient import TestClient

from backend import alignment, database, research, store, tables
from backend.app import app


def block(text, number=0, page=1):
    return {
        "id": str(number),
        "document_id": "target",
        "text": text,
        "page": page,
        "bbox": [0, 0, 100, 20],
        "width": 600,
        "height": 800,
    }


@pytest.mark.parametrize(
    "quote,parts,expected",
    [
        (
            "The model uses 12 layers and 768 dimensions.",
            ["The model uses 12 layers", "and 768 dimensions."],
            "retained",
        ),
        (
            "The model uses 12 layers.",
            ["New introduction. The model uses 12 layers. Further discussion."],
            "retained",
        ),
        (
            "This attention mechanism is parallelizable.",
            ["This attention mechanism is paral-", "lelizable."],
            "retained",
        ),
        ("The model uses 12 layers.", ["The model uses 24 layers."], "review_required"),
        (
            "The result is -0.5 on this task.",
            ["The result is +0.5 on this task."],
            "review_required",
        ),
        (
            "The model improves performance.",
            ["The model does not improve performance."],
            "review_required",
        ),
        ("The batch size is 100", ["The batch size is 1000"], "review_required"),
        ("x is the state variable.", ["X is the state variable."], "review_required"),
        (
            "The mass of the moon was measured.",
            ["We report transformer architecture training experiments."],
            "unlocated",
        ),
        (" ", ["A valid paragraph."], "unlocated"),
    ],
)
def test_alignment_distinguishes_source_survival_from_similarity(
    quote, parts, expected
):
    result = alignment.SourceAligner([block(t, i) for i, t in enumerate(parts)]).locate(
        quote
    )
    assert result["status"] == expected
    if expected == "retained":
        assert [s["text"] for s in result["candidate"]["segments"]] == parts


def test_almost_identical_long_paragraph_with_one_changed_digit_is_not_retained():
    quote = (
        "The experiment repeats the following procedure carefully. " * 40
        + "The result is 5."
    )
    result = alignment.SourceAligner([block(quote[:-2] + "6.")]).locate(quote)
    assert result["status"] == "review_required"


def test_alignment_keeps_cross_page_anchors_and_moved_paragraph():
    parts = [
        block("Unrelated front matter.", 0),
        block("The training batch", 1, 6),
        block("contains 128 samples.", 2, 7),
    ]
    result = alignment.SourceAligner(parts).locate(
        "The training batch contains 128 samples."
    )
    assert result["status"] == "retained"
    assert [p["page"] for p in result["candidate"]["segments"]] == [6, 7]


def test_cross_page_float_is_exposed_without_rewriting_original_blocks():
    old = "We evaluate the system with the same parameters. The beam size is 21."
    blocks = [
        block("We evaluate the system with the same parameters.", 0, 1),
        {**block("1", 1, 1), "bbox": [295, 760, 310, 775]},
        block("Table 2: Evaluation results", 2, 2),
        block("Model\nScore\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10", 3, 2),
        block("The beam size is 21.", 4, 2),
    ]
    result = alignment.SourceAligner(blocks).locate(old)
    assert result["status"] == "retained"
    assert [b["id"] for b in result["candidate"]["segments"]] == ["0", "4"]
    assert [b["id"] for b in result["candidate"]["skipped_context"]] == ["1", "2", "3"]


def test_alignment_does_not_skip_changed_prose_between_sentences():
    blocks = [
        block("The model uses dense attention.", 0, 1),
        block("This is no longer the default configuration.", 1, 2),
        block("It has 12 layers.", 2, 2),
    ]
    assert (
        alignment.SourceAligner(blocks).locate(
            "The model uses dense attention. It has 12 layers."
        )["status"]
        != "retained"
    )


def test_sparse_table_does_not_shift_values_into_empty_columns():
    tokens = []
    for r, row in enumerate(
        [
            ["Model", "DE", "FR"],
            ["Base", "27.3", "38.1"],
            ["Big", "28.4", "41.0"],
            ["French", "", "39.2"],
        ]
    ):
        for c, text in enumerate(row):
            if text:
                tokens.append(
                    {
                        "text": text,
                        "bbox": [c * 100 + 5, r * 20 + 5, c * 100 + 65, r * 20 + 15],
                        "confidence": 0.98,
                    }
                )
    grid = tables.grid_from_tokens(tokens, [0, 0, 300, 80])
    assert grid["rows"][-1] == ["French", "", "39.2"]
    assert grid["rows"][2] == ["Big", "28.4", "41.0"]
    assert len(grid["column_bounds"]) == 2


def test_table_edits_preserve_initial_values_and_reject_stale_writes(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "quality.sqlite3")
    database.initialize()
    data = {
        "rows": [["Model", "Score"], ["Base", "27.3"]],
        "original_rows": [["Model", "Score"], ["Base", "27.3"]],
        "cells": [{"row": 1, "column": 1, "bbox": [10, 20, 50, 30]}],
        "column_bounds": [100],
        "revision": 0,
    }
    result = research.save_artifact("table", "source", data)
    with TestClient(app) as client:
        corrected = [["Model", "Score"], ["Base", "28.4"]]
        response = client.patch(
            "/api/tables/" + result["id"], json={"rows": corrected, "revision": 0}
        )
        assert response.status_code == 200
        content = response.json()["content"]
        assert content["original_rows"][1][1] == "27.3"
        assert content["edits"][0]["rows"][1][1] == "27.3"
        assert content["revision"] == 1 and content["rows"] == corrected
        assert content["cells"] == data["cells"]
        assert (
            client.patch(
                "/api/tables/" + result["id"], json={"rows": corrected, "revision": 0}
            ).status_code
            == 409
        )
        assert (
            client.patch(
                "/api/tables/" + result["id"],
                json={"rows": [["broken"], ["ragged", "row"]], "revision": 1},
            ).status_code
            == 422
        )
        downloaded = client.get("/api/tables/" + result["id"] + "/export").text.lstrip(
            "\ufeff"
        )
        assert list(csv.reader(io.StringIO(downloaded))) == corrected
        saved = json.loads(
            client.get("/api/artifacts/" + result["id"] + "/export?format=json").text
        )
        assert saved["content"]["original_rows"][1][1] == "27.3"


def test_document_alias_edit_is_bounded_and_preserves_original_metadata(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "aliases.sqlite3")
    database.initialize()
    paper = store.import_pdf(
        store.ROOT / "data/competition/pdf/language_understanding_paper.pdf"
    )
    original = store.get_document(paper["id"])
    with TestClient(app) as client:
        response = client.patch(
            "/api/documents/" + paper["id"],
            json={"aliases": [" GPT-1 ", "GPT-1", "", "GPT1"]},
        )
        assert response.status_code == 200
        assert response.json()["metadata"] == {
            **original["metadata"],
            "aliases": ["GPT-1", "GPT1"],
        }
        assert response.json()["title"] == original["title"]
        assert store.list_documents()[0]["aliases"] == ["GPT-1", "GPT1"]
        assert (
            client.patch(
                "/api/documents/" + paper["id"], json={"aliases": ["x" * 101]}
            ).status_code
            == 422
        )
        assert (
            client.patch(
                "/api/documents/" + paper["id"],
                json={"aliases": [str(i) for i in range(13)]},
            ).status_code
            == 422
        )
        assert store.get_document(paper["id"])["metadata"]["aliases"] == [
            "GPT-1",
            "GPT1",
        ]


def test_table_header_is_tracked_as_a_separate_version_dependency():
    from backend.impact import claims_in

    claim = {
        "document_id": "paper",
        "block_id": "row",
        "text": "Hidden dimension is 12288.",
        "quote": "GPT3 175B 96 12288 128",
        "page": 8,
        "source_context": [
            {
                "document_id": "paper",
                "id": "header",
                "text": "model parameters layers dmodel dhead",
                "page": 8,
            }
        ],
    }
    dependencies = list(claims_in({"claims": [claim]}))
    assert len(dependencies) == 2
    assert dependencies[0] == claim
    assert dependencies[1]["block_id"] == "header"
    assert dependencies[1]["quote"] == claim["source_context"][0]["text"]
    assert dependencies[1]["dependency_role"] == "table_header"


def test_csv_keeps_negative_numbers_and_quotes_potential_formulas():
    result = list(
        csv.reader(
            io.StringIO(
                tables.csv_text(
                    [["=1+1", "-0.5", "@run", "-2e-3", 'comma,quote"']]
                ).lstrip("\ufeff")
            )
        )
    )
    assert result == [["'=1+1", "-0.5", "'@run", "-2e-3", 'comma,quote"']]


def test_native_table_rows_match_real_source_geometry():
    import pymupdf

    path = store.ROOT / "data/competition/pdf/1706.03762v1.pdf"
    with pymupdf.open(path) as pdf:
        area = pymupdf.Rect(143, 412, 468, 547)
        result = tables.grid_from_tokens(tables.native_tokens(pdf[8], area), list(area))
    assert len(result["rows"]) == 12
    assert result["rows"][5] == [
        "Transformer (4 layers)",
        "WSJ only, discriminative",
        "91.3",
    ]
    assert result["rows"][10] == ["Transformer (4 layers)", "semi-supervised", "92.7"]


def test_table_header_is_real_source_and_disambiguates_model_and_head_dimensions(
    tmp_path, monkeypatch
):
    from backend.evidence_context import attach_table_headers

    monkeypatch.setattr(store, "DB_PATH", tmp_path / "headers.sqlite3")
    database.initialize()
    paper = store.import_pdf(store.ROOT / "data/competition/pdf/2005.14165v4.pdf")
    row = next(
        b
        for b in store.get_blocks(paper["id"], 8)
        if b["text"].startswith("GPT-3 175B")
    )
    annotated = attach_table_headers([row])[0]
    fields = {pair["field"]: pair["value"] for pair in annotated["table_fields"]}
    assert fields["dmodel"] == "12288"
    assert fields["dhead"] == "128"
    assert fields["nheads"] == "96"
    header = annotated["source_context"][0]
    assert any(
        b["id"] == header["id"] and b["text"] == header["text"]
        for b in store.get_blocks(paper["id"], 8)
    )
    assert annotated["text"] == row["text"]
