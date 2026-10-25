# Workspace interface

The application opens with a designed entry page, followed by separate URL-backed workspace pages. Dashboard is the default page, with live latest-version portfolio counts, charts and an agreement table; no seeded figures or made-up trends are shown. Uploading an agreement supplies its data. Empty portfolios show an explicit empty state.

- **Dashboard:** a concise portfolio summary, distribution charts, agreement preview and links to upload/research.
- **Portfolio analytics:** the full filterable charts, financial term tables, paginated register and deadline tracker.
- **Contract repository:** upload, source inspection and contract versioning.
- **Machine learning lab:** model availability, actual recorded evaluations and supported inference.
- **Research & review tools:** scoped research, scenarios, comparison, human approval and export.
- **System status:** API/database readiness, local research availability and actual model activation status. This is the last sidebar item; operational cards no longer replace the dashboard.

Navigation supports direct URLs and browser Back/Forward. The interface adapts to full desktop, half-screen browser and phone widths. Wide financial/source tables scroll within their container rather than expanding the page.

## Local username and password

Default laptop startup now uses a real single-owner account. With no owner yet, the entry screen asks for a username, password and confirmation. Choose a 3–40 character username (letters, digits, dots, dashes or underscores) and a password of 12–128 characters. The first account owns this local workspace; later visitors see Sign in, not open registration. Existing contracts are preserved by the additive migration.

Passwords use salted PBKDF2-HMAC-SHA256 (600,000 iterations); plaintext passwords are not stored. The backend checks authentication before serving private API routes. Random session tokens are held in HttpOnly, SameSite=Strict cookies, with only SHA-256 token digests stored server-side. Sessions expire after 8 hours, survive a normal browser refresh and are revoked on logout. No credentials enter localStorage/sessionStorage. Login attempts are limited per actual peer address (10 attempts per 15 minutes, reset after success); forwarded headers cannot bypass the limit.

The local HTTP cookie is for the loopback-bound laptop stack. Production mode uses Secure cookies and retains the existing fail-closed token/reviewer requirements. This is not a multi-user registration/tenant system or an independently certified security product. Reviewer labels remain a separate human assertion; an account does not establish legal authority.

A configured `CORPLEX_ACCESS_TOKEN` selects the existing token-protected mode instead; that token is still verified by the server. `CORPLEX_PASSWORD_LOGIN=false` explicitly selects the older unauthenticated local mode only when no workspace token is set. This opt-out is not the default and must not be publicly exposed. Access-configuration failures do not reveal the workspace.

## Forgot your local password?

From the project folder, with Docker running:

```cmd
docker compose -p corplex-app -f compose.app.yaml exec backend .venv/bin/python -m app.reset_password
```

Enter your existing username and new password twice. Password input is hidden. This administrator operation changes only the matching account hash, revokes all sessions and resets login limits; it preserves documents. Anyone with local Docker/database administrator access can administer this local account. There is no paid email reset service.

## Black-and-white appearance

The interface uses black navigation and buttons, white content surfaces, charcoal typography and grayscale charts with explicit labels. All assets, fonts and authentication run locally. There is no domain, paid API or external login provider requirement.
