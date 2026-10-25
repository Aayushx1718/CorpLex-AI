"""Local administrator recovery. Prompts hide passwords; revokes all sessions."""
from getpass import getpass
from sqlalchemy import create_engine, text
from app.accounts import hash_password
from app.config import get_settings


def main():
    username = input('Existing username: ').strip().lower()
    password = getpass('New password (12–128 characters): ')
    confirmation = getpass('Confirm new password: ')
    if not 12 <= len(password) <= 128 or password != confirmation:
        raise SystemExit('Passwords must match and have 12–128 characters. No changes made.')
    engine = create_engine(get_settings().database_url)
    try:
        with engine.begin() as connection:
            result = connection.execute(text('UPDATE workspace_accounts SET password_hash=:hash WHERE username=:name RETURNING id'), {'name': username, 'hash': hash_password(password)}).first()
            if not result:
                raise SystemExit('Account not found. No changes made.')
            connection.execute(text('DELETE FROM workspace_sessions'))
            connection.execute(text('DELETE FROM workspace_login_limits'))
        print('Password changed and all sessions revoked. Sign in again.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
