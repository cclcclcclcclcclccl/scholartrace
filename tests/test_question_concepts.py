from backend import query_facets


def test_input_output_prefers_capability_prose_and_keeps_document_scope(monkeypatch):
    calls = []
    example = {
        "id": "example",
        "page": 5,
        "text": "We show examples of inputs and outputs. The input is a question, and the output is the response in this example.",
    }
    definition = {
        "id": "definition",
        "page": 8,
        "text": "Our model can accept sensor inputs and produce categorical outputs. These are the input and output types evaluated in this study.",
    }

    def search(query, ids, limit):
        calls.append((query, ids))
        return [example, definition]

    monkeypatch.setattr(query_facets.store, "search", search)
    result = query_facets.concept_evidence("模型输入和输出分别是什么？", ["chosen"])
    assert calls == [("inputs outputs", ["chosen"])]
    assert [b["id"] for b in result] == ["definition"]
    assert result[0]["text"] == definition["text"]
    assert query_facets.concept_evidence("输入是什么？", []) == []
