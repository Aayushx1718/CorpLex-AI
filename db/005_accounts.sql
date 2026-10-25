-- Single-owner local account and revocable, expiring server-side sessions.
BEGIN;
SELECT pg_advisory_xact_lock(42005);
CREATE TABLE IF NOT EXISTS workspace_accounts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    singleton boolean NOT NULL DEFAULT true UNIQUE CHECK (singleton),
    username text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS workspace_sessions (
    token_hash char(64) PRIMARY KEY,
    account_id uuid NOT NULL REFERENCES workspace_accounts(id) ON DELETE CASCADE,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_workspace_sessions_expiry ON workspace_sessions(expires_at);
CREATE TABLE IF NOT EXISTS workspace_login_limits (
    client_hash char(64) PRIMARY KEY,
    attempts integer NOT NULL CHECK (attempts > 0),
    window_start timestamptz NOT NULL DEFAULT now()
);
COMMIT;
