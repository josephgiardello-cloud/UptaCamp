# Online Deployment (Render Free Tier)

This project runs the online stack as two services:

- API server: `online_api_server.py`
- WebSocket server: `online_ws_server.py`

## 1. Provision with render.yaml

Render can auto-detect and deploy both services from `render.yaml`.

## 2. Required environment variables

- `UPTACAMP_DB_PATH=/var/data/online_state.db`
- `UPTACAMP_ALLOWED_ORIGINS=https://your-frontend-host`
- `SENTRY_DSN=<optional sentry dsn>`

## 3. Production client URLs

Set these in local `.env` used by game clients:

- `UPTACAMP_ONLINE_URL_PROD=https://uptacamp-api.onrender.com`
- `UPTACAMP_ONLINE_WS_URL_PROD=wss://uptacamp-ws.onrender.com`

## 4. Smoke check

- API: `GET /health` should return `{ "status": "ok" }`
- WS: connect and send handshake payload with `match_id`, `player_id`, `session_token`

## 5. Notes

- Render free instances spin down on inactivity.
- Use persistent disk for SQLite state retention.
- If you need always-on and lower latency, move to a paid plan.
