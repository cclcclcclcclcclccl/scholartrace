from pathlib import Path
import json
import numpy as np
import pytest
from backend import store, database, retrieval

@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'DB_PATH', tmp_path / 'semantic.sqlite3')
    database.initialize()
    def add(identifier, title, text, arxiv=None, version=None):
        with store.connection() as c:
            c.execute('INSERT INTO documents(id,name,title,path,pages,chars,status,arxiv_id,version,metadata) VALUES(?,?,?,?,?,?,?,?,?,?)', (identifier, identifier+'.pdf', title, '/unused.pdf', 1, len(text), 'ready', arxiv, version, '{}'))
            c.execute('INSERT INTO blocks VALUES(?,?,?,?,?,?,?,?,?)', (identifier+'-b', identifier, 1, 0, text, '[0,0,100,100]', 200, 200, 'native'))
    return add

def vectors(texts):
    # Controlled embedding boundary; integration runner separately uses real ONNX.
    return np.array([[1.,0.] if 'cat' not in t else [0.,1.] for t in texts], dtype=np.float32)

def test_body_paraphrases_are_review_candidates_without_title_match(library, monkeypatch):
    library('a', 'A new architecture', 'Attention mechanisms process tokens in parallel without recurrence.')
    library('b', '并行序列计算', '序列通过注意力并行计算，不再依赖循环结构。')
    monkeypatch.setattr(retrieval, 'available', lambda: True)
    monkeypatch.setattr(retrieval, 'embed', vectors)
    result = store.content_similarity('a', 'b')
    assert result.get('semantic_status') == 'ready'
    assert result['semantic_content_cosine'] > .99
    assert result['review_candidate'] is True
    assert result['likely_same_paper'] is False
    assert result['semantic_evidence'][0]['first_block_id'] == 'a-b'

def test_conflicting_identifiers_never_merge_even_when_embedding_matches(library, monkeypatch):
    library('a', 'Shared title', 'The same words repeated about an attention model.', '1706.03762', 1)
    library('b', 'Shared title', 'The same words repeated about an attention model.', '1810.04805', 2)
    monkeypatch.setattr(retrieval, 'available', lambda: True)
    monkeypatch.setattr(retrieval, 'embed', vectors)
    result = store.content_similarity('a', 'b')
    assert result['likely_same_paper'] is False
    assert result['recommended_version_id'] is None
    assert result.get('identifier_conflict') is True

def test_unavailable_model_is_not_reported_as_zero_semantic_score(library, monkeypatch):
    library('a', 'First title', 'Some actual body text about attention and sequences.')
    library('b', 'Second title', 'Another body text about graphs and optimization.')
    monkeypatch.setattr(retrieval, 'available', lambda: False)
    result = store.content_similarity('a', 'b')
    assert result.get('semantic_status') == 'unavailable'
    assert result['semantic_content_cosine'] is None

def test_empty_scans_require_ocr_and_cannot_be_recommended(library, monkeypatch):
    library('a', 'Same', '', '1706.03762', 1)
    library('b', 'Same', '', '1706.03762', 7)
    monkeypatch.setattr(retrieval, 'available', lambda: True)
    result = store.content_similarity('a', 'b')
    assert result.get('semantic_status') == 'needs_text'
    assert not result['likely_same_paper']
    assert result['recommended_version_id'] is None

