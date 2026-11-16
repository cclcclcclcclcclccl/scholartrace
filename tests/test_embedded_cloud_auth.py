"""Exercise proxy origin checks and partitioned sessions without private credentials."""
from fastapi import FastAPI,Response
from fastapi.testclient import TestClient
import pytest
from backend import accounts

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(accounts,'PUBLIC',True)
    monkeypatch.setattr(accounts,'user',lambda request:None)
    monkeypatch.setenv('SCHOLARTRACE_PUBLIC_ORIGIN','https://review.example')
    monkeypatch.setenv('SCHOLARTRACE_EMBEDDED','1')
    app=FastAPI();app.middleware('http')(accounts.scope)
    @app.post('/api/account/login')
    def mutation():return {'ok':True}
    return TestClient(app,base_url='https://internal.proxy')

def test_exact_public_origin_is_accepted_behind_rewriting_proxy(client):
    assert client.post('/api/account/login',headers={'Origin':'https://review.example'}).status_code==200

@pytest.mark.parametrize('origin',[None,'null','https://evil.example','https://review.example.evil','http://review.example','https://review.example/extra','https://internal.proxy'])
def test_embedded_mutations_require_exact_configured_origin(client,origin):
    headers={} if origin is None else {'Origin':origin}
    assert client.post('/api/account/login',headers=headers).status_code==403

def test_forwarded_host_does_not_expand_origin_allowlist(client):
    assert client.post('/api/account/login',headers={'Origin':'https://evil.example','X-Forwarded-Host':'evil.example'}).status_code==403

def test_embedded_session_is_secure_partitioned_and_http_only(tmp_path,monkeypatch):
    monkeypatch.setattr(accounts,'AUTH_PATH',tmp_path/'accounts.sqlite3');accounts.initialize()
    monkeypatch.setattr(accounts,'PUBLIC',True);monkeypatch.setenv('SCHOLARTRACE_EMBEDDED','1')
    response=Response();accounts.create_session('test-user',response)
    cookie=response.headers['set-cookie'].lower()
    assert 'partitioned' in cookie and 'samesite=none' in cookie
    assert 'secure' in cookie and 'httponly' in cookie

def test_default_session_remains_strict(tmp_path,monkeypatch):
    monkeypatch.setattr(accounts,'AUTH_PATH',tmp_path/'accounts.sqlite3');accounts.initialize()
    monkeypatch.delenv('SCHOLARTRACE_EMBEDDED',raising=False)
    response=Response();accounts.create_session('test-user',response)
    cookie=response.headers['set-cookie'].lower()
    assert 'samesite=strict' in cookie and 'partitioned' not in cookie

def test_logout_expires_the_same_partitioned_cookie(tmp_path,monkeypatch):
    from starlette.requests import Request
    monkeypatch.setattr(accounts,'AUTH_PATH',tmp_path/'accounts.sqlite3');accounts.initialize()
    monkeypatch.setattr(accounts,'PUBLIC',True);monkeypatch.setenv('SCHOLARTRACE_EMBEDDED','1')
    response=Response();accounts.logout(Request({'type':'http','headers':[]}),response)
    cookie=response.headers['set-cookie'].lower()
    assert 'partitioned' in cookie and 'samesite=none' in cookie and 'max-age=0' in cookie

@pytest.mark.parametrize('configured',['https://user@review.example','http://review.example','https://review.example/path','https://review.example?x=1'])
def test_invalid_public_origin_fails_closed(client,monkeypatch,configured):
    monkeypatch.setenv('SCHOLARTRACE_PUBLIC_ORIGIN',configured)
    assert client.post('/api/account/login',headers={'Origin':configured}).status_code==403
