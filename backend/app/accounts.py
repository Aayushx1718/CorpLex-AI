"""Single-owner local password login; no external identity or paid service."""
import hashlib
import hmac
import secrets
from http.cookies import SimpleCookie, CookieError
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

COOKIE = 'corplex_session'
ITERATIONS = 600_000
PUBLIC = {'/api/health', '/api/ready', '/api/access', '/api/auth/setup', '/api/auth/login', '/api/auth/logout'}


def password_mode(settings):
    return getattr(settings, 'corplex_password_login', True) and not settings.corplex_access_token


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f'pbkdf2_sha256${ITERATIONS}${salt}${digest}'


def verify_password(password, encoded):
    try:
        algorithm, count, salt, expected = encoded.split('$')
        if algorithm != 'pbkdf2_sha256' or int(count) != ITERATIONS:
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(count)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def session_account(engine, cookie):
    if not cookie or len(cookie) > 200:
        return None
    with engine.connect() as connection:
        return connection.execute(text('''SELECT a.id, a.username FROM workspace_sessions s
            JOIN workspace_accounts a ON a.id=s.account_id
            WHERE s.token_hash=:hash AND s.expires_at > now()'''), {'hash': digest(cookie)}).mappings().first()


def access_state(engine, settings, cookie):
    result = {'authentication_required': bool(settings.corplex_access_token) or password_mode(settings),
              'reviewer_token_required': bool(settings.corplex_review_token), 'mode': settings.app_env,
              'auth_mode': 'password' if password_mode(settings) else 'token' if settings.corplex_access_token else 'local',
              'setup_required': False, 'authenticated': False, 'username': None}
    if password_mode(settings):
        with engine.connect() as connection:
            result['setup_required'] = not connection.execute(text('SELECT EXISTS(SELECT 1 FROM workspace_accounts)')).scalar_one()
        account = session_account(engine, cookie)
        if account:
            result.update(authenticated=True, username=account['username'])
    return result


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r'^[a-zA-Z0-9_.-]+$')
    password: SecretStr = Field(min_length=12, max_length=128)


# Invalid usernames still perform password work against a valid dummy hash.
DUMMY_HASH = hash_password('non-user-dummy-password')


def build_accounts_router(engine, settings):
    router = APIRouter(prefix='/api/auth', tags=['workspace account'])

    def enabled():
        if not password_mode(settings):
            raise HTTPException(409, 'Password login is not enabled for this workspace.')

    def rate_limit(request):
        # Use the actual peer, never caller-controlled forwarded headers.
        client = digest(request.client.host if request.client else 'unknown')
        with engine.begin() as connection:
            connection.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))'), {'key': client})
            connection.execute(text("DELETE FROM workspace_login_limits WHERE window_start < now() - interval '15 minutes'"))
            attempts = connection.execute(text('''INSERT INTO workspace_login_limits(client_hash,attempts) VALUES (:key,1)
                ON CONFLICT(client_hash) DO UPDATE SET attempts=workspace_login_limits.attempts+1
                RETURNING attempts'''), {'key': client}).scalar_one()
        if attempts > 10:
            raise HTTPException(429, 'Too many sign-in attempts. Wait 15 minutes and try again.', headers={'Retry-After': '900'})
        return client

    def issue_session(account, response, old_cookie=None, client=None):
        token = secrets.token_urlsafe(32)
        with engine.begin() as connection:
            connection.execute(text('DELETE FROM workspace_sessions WHERE expires_at <= now()'))
            if old_cookie:
                connection.execute(text('DELETE FROM workspace_sessions WHERE token_hash=:hash'), {'hash': digest(old_cookie)})
            connection.execute(text("INSERT INTO workspace_sessions(token_hash,account_id,expires_at) VALUES (:hash,:id,now()+interval '8 hours')"), {'hash': digest(token), 'id': account['id']})
            if client:
                connection.execute(text('DELETE FROM workspace_login_limits WHERE client_hash=:key'), {'key': client})
        response.set_cookie(COOKIE, token, max_age=8*3600, httponly=True, secure=settings.app_env == 'production', samesite='strict', path='/api')
        response.headers['Cache-Control'] = 'no-store'
        return {'username': account['username'], 'authenticated': True}

    @router.post('/setup', status_code=201)
    def setup(body: Credentials, request: Request, response: Response):
        enabled()
        client = rate_limit(request)
        encoded = hash_password(body.password.get_secret_value())
        with engine.begin() as connection:
            connection.execute(text('SELECT pg_advisory_xact_lock(42006)'))
            if connection.execute(text('SELECT EXISTS(SELECT 1 FROM workspace_accounts)')).scalar_one():
                raise HTTPException(409, 'The local account already exists. Sign in instead.')
            account = connection.execute(text('INSERT INTO workspace_accounts(username,password_hash) VALUES (:name,:hash) RETURNING id,username'), {'name': body.username.lower(), 'hash': encoded}).mappings().one()
        return issue_session(account, response, request.cookies.get(COOKIE), client)

    @router.post('/login')
    def login(body: Credentials, request: Request, response: Response):
        enabled()
        client = rate_limit(request)
        with engine.connect() as connection:
            account = connection.execute(text('SELECT id,username,password_hash FROM workspace_accounts WHERE username=:name'), {'name': body.username.lower()}).mappings().first()
        valid = verify_password(body.password.get_secret_value(), account['password_hash'] if account else DUMMY_HASH)
        if not account or not valid:
            raise HTTPException(401, 'Username or password is incorrect.')
        return issue_session(account, response, request.cookies.get(COOKIE), client)

    @router.post('/logout')
    def logout(request: Request, response: Response):
        token = request.cookies.get(COOKIE)
        if token:
            with engine.begin() as connection:
                connection.execute(text('DELETE FROM workspace_sessions WHERE token_hash=:hash'), {'hash': digest(token)})
        response.delete_cookie(COOKIE, path='/api', secure=settings.app_env == 'production', httponly=True, samesite='strict')
        response.headers['Cache-Control'] = 'no-store'
        return {'signed_out': True}

    return router


class AccountMiddleware:
    def __init__(self, app, engine, settings):
        self.app, self.engine, self.settings = app, engine, settings

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope['path'].startswith('/api/') or scope['path'] in PUBLIC or scope['method'] == 'OPTIONS' or not password_mode(self.settings):
            return await self.app(scope, receive, send)
        cookie = SimpleCookie()
        try:
            headers = dict(scope['headers'])
            cookie.load(headers.get(b'cookie', b'').decode('latin1'))
            token = cookie[COOKIE].value if COOKIE in cookie else ''
            account = await run_in_threadpool(session_account, self.engine, token)
        except CookieError:
            return await JSONResponse({'detail': 'Invalid session cookie.'}, 401)(scope, receive, send)
        except SQLAlchemyError:
            return await JSONResponse({'detail': 'Workspace authentication storage unavailable.'}, 503)(scope, receive, send)
        if not account:
            return await JSONResponse({'detail': 'Sign in to access this workspace.'}, 401)(scope, receive, send)
        scope.setdefault('state', {})['account_username'] = account['username']
        return await self.app(scope, receive, send)
