# Workspace interface

The application opens with a designed entry page, followed by separate URL-backed workspace pages. Dashboard is the default page, with live latest-version portfolio counts, charts and an agreement table; no seeded figures or made-up trends are shown. Uploading an agreement supplies its data. Empty portfolios show an explicit empty state.

- **Dashboard:** a concise portfolio summary, distribution charts, agreement preview and links to upload/research.
- **Portfolio analytics:** the full filterable charts, financial term tables, paginated register and deadline tracker.
- **Contract repository:** upload, source inspection and contract versioning.
- **Machine learning lab:** model availability, actual recorded evaluations and supported inference.
- **Research & review tools:** scoped research, scenarios, comparison, human approval and export.
- **System status:** API/database readiness, local research availability and actual model activation status. This is the last sidebar item; operational cards no longer replace the dashboard.

Navigation supports direct URLs and browser Back/Forward. The interface adapts to full desktop, half-screen browser and phone widths. Wide financial/source tables scroll within their container rather than expanding the page.

## Entry is not a fabricated account system

In default local mode, **Open local workspace** requires no account, password, API key or payment. The optional name is an in-memory display label, explicitly not a verified identity. Leaving or reloading the workspace resets the entry state. This screen is a local user flow, not a security boundary for an unauthenticated server.

When workspace tokens are configured, the same entry screen requires a real access token and validates it against the backend before mounting the workspace. Tokens remain in memory and clear on exit/reload. A failed access-configuration request does not reveal the workspace. Individual user accounts, registration and password recovery are not implemented; do not present display names as authenticated users or expose the default local server publicly.

All styling uses local assets and system fonts. There are no external font, image, authentication or paid API dependencies for this interface.
