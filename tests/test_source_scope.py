from backend import source_scope, subquestions


def block(id, text, box):
    return {"id": id, "text": text, "bbox": box, "page": 1, "document_id": "doc"}


def test_abstract_uses_geometry_not_interleaved_pdf_order():
    rows = [
        block("heading", "Abstract", [100, 100, 160, 115]),
        block("other", "Right column introduction. " * 5, [300, 120, 550, 220]),
        block(
            "abstract",
            "This is the original abstract paragraph. " * 5,
            [60, 120, 260, 220],
        ),
        block("intro", "1. Introduction", [60, 230, 260, 245]),
        block("body", "This is ordinary body text. " * 5, [60, 250, 260, 340]),
    ]
    assert [b["id"] for b in source_scope.abstract_blocks(rows)] == ["abstract"]
    assert source_scope.abstract_blocks(rows[1:]) == []


def test_explicit_scope_stays_in_selected_document(monkeypatch):
    calls = []
    monkeypatch.setattr(
        source_scope.store,
        "get_document",
        lambda id: {"title": "Test", "name": "test.pdf"},
    )

    def get_blocks(id, page):
        calls.append((id, page))
        return [
            {
                **block(
                    "p",
                    "Controlled comparison of context windows. " * 3,
                    [10, 20, 200, 50],
                ),
                "page": page,
            }
        ]

    monkeypatch.setattr(source_scope.store, "get_blocks", get_blocks)
    assert (
        source_scope.explicit_scope_evidence("第47页 context", ["chosen"])[0]["page"]
        == 47
    )
    assert calls == [("chosen", 47)]
    assert source_scope.explicit_scope_evidence("训练了多少？", ["chosen"]) == []
    assert source_scope.explicit_scope_evidence("第47页", ["a", "b"]) == []


def test_comparison_instruction_is_not_an_extra_fact_question():
    parts = subquestions.split_question(
        "方法A是精确还是近似？其稀疏扩展是精确还是近似？请区分两者。"
    )
    assert len(parts) == 2
    assert "请区分两者" in parts[1]["question"]
    resolved = subquestions.contextual_question(parts, 1)
    assert "方法A" in resolved


def test_comparison_followup_carries_page_and_original_context():
    parts = subquestions.split_question(
        "附录第47页窗口从多少扩到多少？比较两种窗口时，两组模型各训练多少？"
    )
    assert "第47页" in subquestions.contextual_question(parts, 1)
    assert "第47页" not in parts[1]["question"]
