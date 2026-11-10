import pytest
from backend import accounts, store
from scripts.cloud_entry import bootstrap


def test_cloud_bootstrap_requires_secret_before_creating_data(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'ROOT', tmp_path)
    monkeypatch.setattr(accounts, 'AUTH_PATH', tmp_path / 'data/accounts.sqlite3')
    monkeypatch.delenv('MOHENG_REVIEW_PASSWORD', raising=False)
    with pytest.raises(ValueError, match='MOHENG_REVIEW_PASSWORD'):
        bootstrap()
    assert not (tmp_path / 'data').exists()


def test_cloud_bootstrap_hashes_password_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'ROOT', tmp_path)
    monkeypatch.setattr(accounts, 'AUTH_PATH', tmp_path / 'data/accounts.sqlite3')
    monkeypatch.setenv('MOHENG_REVIEW_PASSWORD', 'only-a-test-password-12345')
    first = bootstrap()
    second = bootstrap()
    assert first == second
    with accounts.connect() as c:
        rows = c.execute('SELECT * FROM users').fetchall()
        assert len(rows) == 1
        assert rows[0]['password'] != 'only-a-test-password-12345'
    assert accounts.path(first).exists()
    assert not (tmp_path / 'data/scholartrace.sqlite3').exists()


@pytest.mark.parametrize('setting,expected', [('1', True), ('0', False)])
def test_health_advertises_background_dispatch(monkeypatch, setting, expected):
    import asyncio
    from backend.app import health
    monkeypatch.setenv('SCHOLARTRACE_CLOUD', setting)
    assert asyncio.run(health()).get('background_answers_recommended') is expected


def test_cloud_data_root_is_a_persistent_volume_when_configured(tmp_path, monkeypatch):
    from backend import accounts
    monkeypatch.setenv('SCHOLARTRACE_DATA_DIR', str(tmp_path / 'persistent'))
    assert accounts.data_root() == tmp_path / 'persistent'
    assert accounts.path('reviewer') == tmp_path / 'persistent' / 'accounts' / 'reviewer' / 'library.sqlite3'
