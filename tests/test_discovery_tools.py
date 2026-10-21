import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import accounts, database, discovery, store
from backend import discovery_tools as dt
from backend.app import app


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "main.sqlite3")
    monkeypatch.setattr(accounts, "AUTH_PATH", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(
        accounts, "path", lambda identifier: tmp_path / identifier / "library.sqlite3"
    )
    database.initialize()
    with store.connection() as c:
        for identifier, title, arxiv, version, archived in [
            ("seed", "Attention Is All You Need", "1706.03762", 1, 0),
            ("version", "Attention Is All You Need", "1706.03762", 7, 0),
            ("related", "Efficient attention for transformers", None, None, 0),
            ("other", "Cell biology", None, None, 0),
            ("archived", "Sparse attention", None, None, 1),
        ]:
            c.execute(
                "INSERT INTO documents(id,name,title,path,pages,chars,status,metadata,arxiv_id,version,archived) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    identifier + ".pdf",
                    title,
                    "test.pdf",
                    1,
                    30,
                    "ready",
                    "{}",
                    arxiv,
                    version,
                    archived,
                ),
            )


@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://arxiv.org/pdf/1706.03762v7.pdf", ("arxiv", "id:1706.03762v7")),
        ("arXiv:1706.03762", ("arxiv", "id:1706.03762")),
        (
            "https://doi.org/10.1038/NATURE14539",
            ("crossref", "doi:10.1038/nature14539"),
        ),
        ("doi:10.1000/a(b)", ("crossref", "doi:10.1000/a(b)")),
    ],
)
def test_identifier_normalization(value, expected):
    assert dt.identifier(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com/10.1038/a",
        "Attention Is All You Need",
        "https://arxiv.org/abs/not-a-paper",
    ],
)
def test_invalid_identifier(value):
    with pytest.raises(ValueError):
        dt.identifier(value)


def test_related_excludes_versions_archived_and_preserves_local_on_network_failure(
    workspace, monkeypatch
):
    async def unavailable(*args, **kwargs):
        raise httpx.ConnectError("unavailable")

    monkeypatch.setattr(discovery, "search_cached", unavailable)
    result = asyncio.run(dt.related(document_id="seed", online=True))
    assert [p["id"] for p in result["local"]] == ["related"]
    assert result["local"][0]["shared_terms"] == ["attention"]
    assert result["warnings"] and not result["papers"]
    with pytest.raises(ValueError):
        asyncio.run(dt.related(document_id="archived"))
    with pytest.raises(KeyError):
        asyncio.run(dt.related(document_id="missing"))


def test_lookup_routes_exact_identifier_and_preserves_version_matches(
    workspace, monkeypatch
):
    calls = []

    async def search(query, **kwargs):
        calls.append((query, kwargs))
        return [
            {
                "id": "arxiv:1706.03762v7",
                "title": "Attention Is All You Need",
                "arxiv_id": "1706.03762v7",
            }
        ]

    monkeypatch.setattr(discovery, "search_cached", search)
    result = asyncio.run(
        dt.lookup(
            "https://arxiv.org/abs/1706.03762v7",
            mode="identifier",
            source="crossref",
            year_from=2020,
            start=12,
        )
    )
    assert calls[0][0] == "id:1706.03762v7"
    assert (
        calls[0][1]["source"] == "arxiv"
        and calls[0][1]["start"] == 0
        and calls[0][1]["year_from"] is None
    )
    assert {p["id"]: p["different_version"] for p in result[0]["library_matches"]} == {
        "seed": True,
        "version": False,
    }
    with TestClient(app) as client:
        assert client.post("/api/discover/related", json={}).status_code == 422
        assert (
            client.post(
                "/api/discover/search", json={"query": "nonsense", "mode": "identifier"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/discover/search", json={"query": "attention", "mode": "title"}
            ).status_code
            == 200
        )
        assert calls[-1][0] == 'ti:"attention"'


def test_actual_provider_request_shapes_and_not_found(workspace, monkeypatch):
    real_client = httpx.AsyncClient
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.host == "api.crossref.org":
            if "missing" in request.url.path:
                return httpx.Response(404)
            return httpx.Response(
                200,
                json={
                    "message": {
                        "DOI": "10.1038/nature14539",
                        "title": ["Deep learning"],
                        "published": {"date-parts": [[2015]]},
                    }
                },
            )
        return httpx.Response(
            200,
            text='<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/1706.03762v7</id><title>Attention Is All You Need</title><summary>test</summary></entry></feed>',
        )

    monkeypatch.setattr(
        discovery.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(discovery, "last_arxiv", -100)

    async def exercise():
        assert (await discovery.search("doi:10.1038/nature14539", "crossref"))[0][
            "doi"
        ] == "10.1038/nature14539"
        assert await discovery.search("doi:10.1000/missing", "crossref") == []
        assert (await discovery.search("id:1706.03762v7"))[0][
            "arxiv_id"
        ] == "1706.03762v7"

    asyncio.run(exercise())
    assert requests[0].url.path.endswith("10.1038/nature14539")
    assert requests[-1].url.params.get("id_list") == "1706.03762v7"
    assert "search_query" not in requests[-1].url.params


def test_account_scoped_library_and_external_seed(workspace, tmp_path):
    token = store.database_override.set(tmp_path / "second.sqlite3")
    try:
        database.initialize()
        assert (
            dt.annotate(
                [{"title": "Attention Is All You Need", "arxiv_id": "1706.03762v7"}]
            )[0]["library_matches"]
            == []
        )
        with pytest.raises(KeyError):
            asyncio.run(dt.related(document_id="seed"))
        with pytest.raises(ValueError):
            asyncio.run(dt.related(paper_id="unseen"))
    finally:
        store.database_override.reset(token)


def test_abstract_context_filters_ambiguous_word_matches(workspace, monkeypatch):
    discovery.persist(
        [
            {
                "id": "seed-remote",
                "title": "Attention Is All You Need",
                "abstract": "Transformer translation encoder. Translation encoder transformer.",
            }
        ]
    )

    async def candidates(query, **kwargs):
        assert "translation" in query and "transformer" in query
        return [
            {
                "id": "figure",
                "title": "Transformer attention",
                "abstract": "encoder translation",
                "record_type": "component",
            },
            {
                "id": "bad",
                "title": "Conscious attention",
                "abstract": "Human attention",
                "authors": [],
            },
            {
                "id": "good",
                "title": "Efficient transformer attention",
                "abstract": "Encoder translation",
                "authors": [],
            },
        ]

    monkeypatch.setattr(discovery, "search_cached", candidates)
    result = asyncio.run(dt.related(paper_id="seed-remote", online=True))
    assert [p["id"] for p in result["papers"]] == ["good"]
    assert set(result["context_terms"]) == {"transformer", "translation", "encoder"}
    assert result["context_origin"] == "种子摘要元数据"


def test_discovery_history_api_restores_without_search(workspace, monkeypatch):
    from backend import discovery_history

    calls = []

    async def lookup(**kwargs):
        calls.append(kwargs)
        return [
            {
                "id": "doi:test",
                "title": "Attention Is All You Need",
                "arxiv_id": "1706.03762v7",
                "retrieval_status": "live",
                "authors": [],
            }
        ]

    monkeypatch.setattr(dt, "lookup", lookup)
    with TestClient(app) as client:
        spec = {
            "query": "attention",
            "mode": "title",
            "source": "crossref",
            "year_from": 2020,
            "start": 12,
        }
        assert client.post("/api/discover/search", json=spec).status_code == 200
        listing = client.get("/api/discover/history").json()
        entry = listing["items"][0]
        assert entry["spec"]["year_from"] == 2020 and entry["spec"]["start"] == 12
        saved = client.get(f"/api/discover/history/{entry['id']}").json()
        assert len(calls) == 1
        assert saved["result"][0]["retrieval_status"] == "live"
        assert saved["view"][0]["retrieval_status"] == "snapshot"
        assert len(saved["view"][0]["library_matches"]) == 2
        with store.connection() as c:
            c.execute("UPDATE documents SET archived=1 WHERE id='version'")
        restored = discovery_history.get(entry["id"])
        assert len(restored["view"][0]["library_matches"]) == 1
        assert restored["result"] == saved["result"]
        assert client.get("/api/discover/history?before=-1").status_code == 422


def test_history_cursor_is_stable_when_new_records_arrive(workspace):
    from backend import discovery_history as history

    for n in range(23):
        history.save("search", str(n), {"query": str(n)}, [])
    first = history.listing()
    assert len(first["items"]) == 20 and first["next_before"]
    history.save("search", "new", {}, [])
    older = history.listing(first["next_before"])
    assert len(older["items"]) == 3 and older["next_before"] is None
    assert not {p["id"] for p in older["items"]} & {p["id"] for p in first["items"]}


def test_history_scope_and_archived_local_results(workspace, tmp_path):
    from backend import discovery_history as history

    result = {
        "seed": {"id": "seed", "title": "Attention"},
        "papers": [],
        "local": [
            {"id": "related", "title": "Efficient attention", "reason": "attention"}
        ],
    }
    identifier = history.save("related", "seed", {"document_id": "seed"}, result)
    with store.connection() as c:
        c.execute("UPDATE documents SET archived=1 WHERE id='related'")
    restored = history.get(identifier)
    assert (
        restored["view"]["local"] == []
        and restored["view"]["unavailable_local_count"] == 1
    )
    assert restored["result"] == result
    token = store.database_override.set(tmp_path / "other.sqlite3")
    try:
        database.initialize()
        assert history.listing()["items"] == []
        with pytest.raises(KeyError):
            history.get(identifier)
    finally:
        store.database_override.reset(token)


def test_cached_preference_ranking_and_undo(workspace, monkeypatch):
    calls = []

    async def search(**kwargs):
        calls.append(kwargs)
        return [{"id": "b", "provider_rank": 1}, {"id": "a", "provider_rank": 0}]

    monkeypatch.setattr(discovery, "search", search)

    async def exercise():
        with store.connection() as c:
            c.execute("INSERT INTO feedback(paper_id,vote) VALUES('b',1)")
        assert [p["id"] for p in await discovery.search_cached("query")] == ["b", "a"]
        with store.connection() as c:
            c.execute("UPDATE feedback SET vote=0 WHERE paper_id='b'")
        restored = await discovery.search_cached("query")
        assert [p["id"] for p in restored] == ["a", "b"]
        assert all(p["retrieval_status"] == "cache" for p in restored)
        assert len(calls) == 1

    asyncio.run(exercise())


def test_crossref_title_search_uses_title_field(workspace, monkeypatch):
    real_client = httpx.AsyncClient
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"message": {"items": []}})

    monkeypatch.setattr(
        discovery.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    asyncio.run(dt.lookup("Deep learning", mode="title", source="crossref"))
    assert calls[0].url.params["query.title"] == "Deep learning"
    assert "query.bibliographic" not in calls[0].url.params
