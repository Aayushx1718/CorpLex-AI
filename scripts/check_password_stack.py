"""CI/new disposable stacks only: creates one owner and uploads a synthetic sample.

Never run against a user's existing unconfigured workspace: this creates its owner.
Credentials are generated in memory and are never printed. No external requests.
"""
import argparse
from pathlib import Path
import secrets
import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--new-disposable-stack', action='store_true', required=True)
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Port must be between 1024 and 65535.')
    credentials = {'username': 'ci_owner', 'password': secrets.token_urlsafe(32)}
    with httpx.Client(base_url=f'http://127.0.0.1:{args.port}', timeout=30, follow_redirects=False) as client:
        status = client.get('/api/access')
        status.raise_for_status()
        if status.json().get('setup_required') is not True:
            raise SystemExit('Refusing to modify a workspace that already has an account or is not in password mode.')
        assert client.get('/api/contracts').status_code == 401
        response = client.post('/api/auth/setup', json=credentials)
        assert response.status_code == 201, 'Account setup failed.'
        assert client.get('/api/contracts').status_code == 200
        source = Path(__file__).resolve().parents[1] / 'samples/generated/vendor.docx'
        with source.open('rb') as file:
            result = client.post('/api/contracts', data={'contract_type': 'vendor', 'title': 'Recovery check'}, files={'file': ('vendor.docx', file, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
        assert result.status_code in (200, 201), 'Synthetic upload failed.'
        assert client.post('/api/auth/logout').status_code == 200
        assert client.get('/api/contracts').status_code == 401
        assert client.post('/api/auth/login', json={**credentials, 'password': 'Wrong-test-password-only'}).status_code == 401
        assert client.post('/api/auth/login', json=credentials).status_code == 200
        assert client.get('/api/contracts').status_code == 200
        assert client.post('/api/auth/logout').status_code == 200
    print('PASS: new-owner setup, authenticated upload, logout, wrong-password rejection and valid login on the disposable stack.')


if __name__ == '__main__':
    main()
