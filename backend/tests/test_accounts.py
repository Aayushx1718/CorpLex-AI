from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.accounts import AccountMiddleware, build_accounts_router, access_state, COOKIE, digest, hash_password, verify_password
from app.security import SecurityMiddleware


@pytest.fixture
def accounts(db_engine):
    settings = SimpleNamespace(corplex_password_login=True, corplex_access_token='', corplex_review_token='', app_env='test', cors_origins=[])
    app = FastAPI()
    app.include_router(build_accounts_router(db_engine, settings))
    @app.get('/api/private')
    def private(): return {'private': True}
    @app.get('/api/access')
    def status(): return access_state(db_engine, settings, None)
    app.add_middleware(AccountMiddleware, engine=db_engine, settings=settings)
    app.add_middleware(SecurityMiddleware, settings=settings)
    with TestClient(app) as client:
        yield client


CREDS = {'username': 'Aayush', 'password': 'Example-test-only-2026'}


def test_setup_stores_only_salted_hash_and_protects_api(accounts, db_engine):
    assert accounts.get('/api/private').status_code == 401
    assert accounts.get('/api/access').json()['setup_required']
    response = accounts.post('/api/auth/setup', json=CREDS)
    assert response.status_code == 201
    assert response.json()['username'] == 'aayush'
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie and 'Path=/api' in cookie
    assert accounts.get('/api/private').status_code == 200
    with db_engine.connect() as connection:
        encoded = connection.execute(text('SELECT password_hash FROM workspace_accounts')).scalar_one()
        session_hash = connection.execute(text('SELECT token_hash FROM workspace_sessions')).scalar_one()
    assert CREDS['password'] not in encoded and verify_password(CREDS['password'], encoded)
    assert session_hash == digest(accounts.cookies[COOKIE])
    assert accounts.post('/api/auth/setup', json=CREDS).status_code == 409
    assert not accounts.get('/api/access').json()['setup_required']


def test_wrong_password_logout_replay_and_session_expiry(accounts, db_engine):
    accounts.post('/api/auth/setup', json=CREDS)
    old = accounts.cookies[COOKIE]
    assert accounts.post('/api/auth/logout').status_code == 200
    assert accounts.get('/api/private').status_code == 401
    accounts.cookies.set(COOKIE, old)
    assert accounts.get('/api/private').status_code == 401
    accounts.cookies.clear()
    bad = accounts.post('/api/auth/login', json={**CREDS, 'password': 'Incorrect-password-value'})
    assert bad.status_code == 401 and 'Incorrect-password' not in bad.text
    assert accounts.post('/api/auth/login', json=CREDS).status_code == 200
    assert accounts.get('/api/private').status_code == 200
    with db_engine.begin() as connection:
        connection.execute(text('UPDATE workspace_sessions SET expires_at=:expiry'), {'expiry': datetime.now(timezone.utc)-timedelta(seconds=1)})
    assert accounts.get('/api/private').status_code == 401


def test_rate_limit_is_persistent_and_cross_origin_requests_are_rejected(accounts):
    for _ in range(10):
        assert accounts.post('/api/auth/login', json=CREDS).status_code == 401
    assert accounts.post('/api/auth/login', json=CREDS).status_code == 429
    assert accounts.post('/api/auth/setup', json=CREDS, headers={'Origin': 'https://untrusted.example'}).status_code == 403


def test_password_hashes_are_salted_and_wrong_password_fails():
    first, second = hash_password(CREDS['password']), hash_password(CREDS['password'])
    assert first != second
    assert verify_password(CREDS['password'], first)
    assert not verify_password('incorrect', first)
    assert not verify_password('irrelevant', 'invalid-hash')


def test_validation_errors_do_not_echo_password(monkeypatch):
    from app.main import app
    with TestClient(app) as client:
        response = client.post('/api/auth/login', json={'username': 'aayush', 'password': 'shortSECRET'})
    assert response.status_code == 422
    assert 'shortSECRET' not in response.text
