# Changelog

## v1.0.0 - 2026-05-22

- Added repository hygiene tooling and policies (`.gitattributes`, data artifact strategy, cleanup playbook).
- Added deterministic dependency support (`requirements.txt`, `Pipfile`, `Pipfile.lock`).
- Added pre-commit hooks (`black`, `ruff`).
- Added CI runtime smoke workflow for headless validation.
- Added deployment assets for online services (`render.yaml`, deployment docs).
- Added `.env.example` production URL settings and configurable DB path.
- Added Sentry integration hooks for API and WebSocket servers.
- Updated README with Play Online badge, deploy guidance, and production usage.
