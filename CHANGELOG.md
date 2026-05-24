# Changelog

## v1.1.0-beta - 2026-05-23

- Added Windows beta distribution artifact in repo root (`CribbageGame-Windows-Test.zip`).
- Added one-command Windows packaging script (`build_windows.ps1`) for repeatable beta builds.
- Updated client online defaults to hosted production endpoints, with environment override support.
- Improved online client error messaging for misconfigured route/base URL cases.
- Corrected README project state and online messaging (desktop client + backend status badge only).
- Added dedicated beta release notes document for GitHub publishing (`docs/RELEASE_v1.1.0-beta.md`).

## v1.0.0 - 2026-05-22

- Added repository hygiene tooling and policies (`.gitattributes`, data artifact strategy, cleanup playbook).
- Added deterministic dependency support (`requirements.txt`, `Pipfile`, `Pipfile.lock`).
- Added pre-commit hooks (`black`, `ruff`).
- Added CI runtime smoke workflow for headless validation.
- Added deployment assets for online services (`render.yaml`, deployment docs).
- Added `.env.example` production URL settings and configurable DB path.
- Added Sentry integration hooks for API and WebSocket servers.
- Updated README with Play Online badge, deploy guidance, and production usage.
