from __future__ import annotations

import argparse
import importlib
import json
import logging
import os
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from online_backend import OnlineBackend

sentry_sdk: Any | None = None
try:
    sentry_sdk = importlib.import_module("sentry_sdk")
except Exception:  # pragma: no cover - optional dependency at runtime
    sentry_sdk = None

LOGGER = logging.getLogger(__name__)


def _init_sentry() -> None:
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn or sentry_sdk is None:
        return
    sentry_sdk.init(dsn=dsn, traces_sample_rate=0.05)


class OnlineApiHandler(BaseHTTPRequestHandler):
    backend: OnlineBackend
    # Basic in-process throttling. This is intentionally lightweight and
    # primarily protects local/dev servers from bursts.
    RATE_LIMIT_WINDOW_S = 60.0
    RATE_LIMIT_PER_IP = 180
    RATE_LIMIT_PER_PLAYER = 120
    CORS_ALLOWED_ORIGINS = tuple(
        origin.strip()
        for origin in os.getenv(
            "UPTACAMP_ALLOWED_ORIGINS",
            "http://127.0.0.1,http://localhost",
        ).split(",")
        if origin.strip()
    )
    _rate_limit_lock = threading.Lock()
    _ip_hits: dict[str, list[float]] = {}
    _player_hits: dict[str, list[float]] = {}

    def _cors_allow_origin(self) -> str:
        allowed = self.CORS_ALLOWED_ORIGINS
        if not allowed:
            return "null"
        if "*" in allowed:
            return "*"
        request_origin = self.headers.get("Origin", "").strip()
        if request_origin and request_origin in allowed:
            return request_origin
        return allowed[0]

    def end_headers(self) -> None:
        cors_origin = self._cors_allow_origin()
        self.send_header("Access-Control-Allow-Origin", cors_origin)
        if cors_origin != "*":
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Authorization, Content-Type, X-Requested-With",
        )
        self.send_header("Access-Control-Max-Age", "600")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _client_ip(self) -> str:
        forwarded = self.headers.get("X-Forwarded-For", "").strip()
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
        host = self.client_address[0] if self.client_address else "unknown"
        return str(host)

    def _log_suspicious(self, reason: str, *, player_id: str | None = None) -> None:
        LOGGER.warning(
            "suspicious_request: reason=%s ip=%s method=%s path=%s player_id=%s",
            reason,
            self._client_ip(),
            self.command,
            self.path,
            player_id,
        )

    @classmethod
    def _allow_hit(
        cls,
        bucket: dict[str, list[float]],
        key: str,
        now: float,
        *,
        limit: int,
        window_s: float,
    ) -> bool:
        with cls._rate_limit_lock:
            hits = bucket.setdefault(key, [])
            cutoff = now - window_s
            while hits and hits[0] < cutoff:
                hits.pop(0)
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def _enforce_rate_limit(self, *, player_id: str | None = None) -> bool:
        now = time.monotonic()
        ip = self._client_ip()
        if not self._allow_hit(
            self._ip_hits,
            ip,
            now,
            limit=self.RATE_LIMIT_PER_IP,
            window_s=self.RATE_LIMIT_WINDOW_S,
        ):
            self._log_suspicious("rate_limit_ip", player_id=player_id)
            self._send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "Rate limit exceeded"})
            return False

        if player_id and not self._allow_hit(
            self._player_hits,
            player_id,
            now,
            limit=self.RATE_LIMIT_PER_PLAYER,
            window_s=self.RATE_LIMIT_WINDOW_S,
        ):
            self._log_suspicious("rate_limit_player", player_id=player_id)
            self._send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "Rate limit exceeded"})
            return False
        return True

    def _extract_bearer(self) -> str | None:
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        token = auth[7:].strip()
        return token or None

    def _require_auth(self, player_id: str) -> str:
        token = self._extract_bearer()
        if not token:
            self._log_suspicious("missing_bearer", player_id=player_id)
            raise PermissionError("Missing bearer token")
        if not self.backend.verify_session_token(player_id, token):
            self._log_suspicious("invalid_bearer", player_id=player_id)
            raise PermissionError("Invalid session token")
        return token

    @staticmethod
    def _query_single(parsed_query: dict[str, list[str]], key: str) -> str | None:
        values = parsed_query.get(key, [])
        if not values:
            return None
        value = str(values[0]).strip()
        return value or None

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        body = self.rfile.read(length)
        if not body:
            return {}
        parsed = json.loads(body.decode("utf-8"))
        return cast(dict[str, Any], parsed)

    def log_message(self, fmt: str, *args):
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        parts = [p for p in parsed.path.split("/") if p]
        if not self._enforce_rate_limit():
            return
        try:
            if parts == ["health"]:
                self._send_json(HTTPStatus.OK, {"status": "ok"})
                return

            if len(parts) == 2 and parts[0] == "matches":
                requester_id = self._query_single(qs, "player_id")
                if not requester_id:
                    raise PermissionError("player_id query parameter is required")
                token = self._require_auth(requester_id)
                details = self.backend.get_match_details(
                    parts[1],
                    requester_player_id=requester_id,
                    session_token=token,
                )
                self._send_json(HTTPStatus.OK, details)
                return

            if len(parts) == 2 and parts[0] == "players":
                requester_id = parts[1]
                self._require_auth(requester_id)
                profile = self.backend.get_player_profile(parts[1])
                self._send_json(HTTPStatus.OK, profile)
                return

            if len(parts) == 3 and parts[0] == "players" and parts[2] == "matches":
                requester_id = parts[1]
                self._require_auth(requester_id)
                limit = int(qs.get("limit", ["20"])[0])
                rows = self.backend.list_recent_matches(parts[1], limit=limit)
                self._send_json(HTTPStatus.OK, {"matches": rows})
                return

            if parts == ["leaderboard"]:
                qs = parse_qs(parsed.query)
                limit = int(qs.get("limit", ["50"])[0])
                rows = self.backend.leaderboard(limit=limit)
                self._send_json(HTTPStatus.OK, {"players": rows})
                return

            if len(parts) == 3 and parts[0] == "matches" and parts[2] == "chat":
                requester_id = self._query_single(qs, "player_id")
                if not requester_id:
                    raise PermissionError("player_id query parameter is required")
                token = self._require_auth(requester_id)
                limit = int(qs.get("limit", ["100"])[0])
                rows = self.backend.list_chat_messages(
                    parts[1],
                    limit=limit,
                    requester_player_id=requester_id,
                    session_token=token,
                )
                self._send_json(HTTPStatus.OK, {"messages": rows})
                return

            self._log_suspicious("unknown_get_route")
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Route not found"})
        except PermissionError as exc:
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": str(exc)})
        except Exception as exc:
            LOGGER.exception("GET failed: path=%s", self.path)
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        payload = self._read_json_body()
        player_hint = (
            payload.get("player_id")
            or payload.get("host_player_id")
            or payload.get("guest_player_id")
        )
        if player_hint is not None and not isinstance(player_hint, str):
            player_hint = str(player_hint)
        if not self._enforce_rate_limit(player_id=cast(str | None, player_hint)):
            return

        try:
            if parts == ["players", "login"]:
                result = self.backend.login_player(
                    display_name=payload["display_name"],
                    player_id=payload.get("player_id"),
                )
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "player_id": result.player_id,
                        "display_name": result.display_name,
                        "session_token": result.session_token,
                    },
                )
                return

            if parts == ["players"]:
                result = self.backend.login_player(display_name=payload["display_name"])
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "player_id": result.player_id,
                        "display_name": result.display_name,
                        "session_token": result.session_token,
                    },
                )
                return

            if parts == ["players", "upsert"]:
                self.backend.upsert_player(payload["player_id"], payload["display_name"])
                self._send_json(HTTPStatus.OK, {"ok": True})
                return

            if parts == ["invites", "create"]:
                self._require_auth(payload["host_player_id"])
                code = self.backend.create_invite(payload["host_player_id"])
                self._send_json(HTTPStatus.OK, {"invite_code": code})
                return

            if parts == ["invites", "accept"]:
                self._require_auth(payload["guest_player_id"])
                match_id = self.backend.accept_invite(
                    payload["invite_code"], payload["guest_player_id"]
                )
                self._send_json(HTTPStatus.OK, {"match_id": match_id})
                return

            if parts == ["matchmaking", "enqueue"]:
                self._require_auth(payload["player_id"])
                queue_id = self.backend.enqueue_for_matchmaking(payload["player_id"])
                self._send_json(HTTPStatus.OK, {"queue_id": queue_id})
                return

            if parts == ["matchmaking", "pair"]:
                paired_match_id = self.backend.pair_waiting_players()
                self._send_json(HTTPStatus.OK, {"match_id": paired_match_id})
                return

            if len(parts) == 3 and parts[0] == "matches" and parts[2] == "turns":
                token = self._require_auth(payload["player_id"])
                turn_index = self.backend.submit_turn(
                    match_id=parts[1],
                    player_id=payload["player_id"],
                    action_type=payload["action_type"],
                    payload=payload.get("payload", {}),
                    idempotency_key=payload["idempotency_key"],
                    signature=payload.get("signature"),
                    session_token=token,
                )
                self._send_json(HTTPStatus.OK, {"turn_index": turn_index})
                return

            if len(parts) == 3 and parts[0] == "matches" and parts[2] == "finish":
                owner = payload.get("player_id")
                if not owner or not isinstance(owner, str):
                    raise PermissionError("player_id is required")
                self._require_auth(owner)
                self.backend.finish_match(
                    parts[1],
                    payload.get("winner_player_id"),
                    finisher_player_id=owner,
                )
                self._send_json(HTTPStatus.OK, {"ok": True})
                return

            if len(parts) == 3 and parts[0] == "matches" and parts[2] == "chat":
                token = self._require_auth(payload["player_id"])
                row = self.backend.post_chat_message(
                    match_id=parts[1],
                    player_id=payload["player_id"],
                    message=payload["message"],
                    session_token=token,
                )
                self._send_json(HTTPStatus.OK, row)
                return

            if len(parts) == 3 and parts[0] == "matches" and parts[2] == "rematch":
                token = self._require_auth(payload["player_id"])
                row = self.backend.request_rematch(
                    prior_match_id=parts[1],
                    player_id=payload["player_id"],
                    session_token=token,
                )
                self._send_json(HTTPStatus.OK, row)
                return

            if parts == ["telemetry", "bot-decision"]:
                event_id = self.backend.record_bot_decision(
                    phase=payload["phase"],
                    ai_level=int(payload["ai_level"]),
                    state_hash=payload["state_hash"],
                    candidates=payload.get("candidates", []),
                    selected_action=payload["selected_action"],
                    expected_value=payload.get("expected_value"),
                    match_id=payload.get("match_id"),
                )
                self._send_json(HTTPStatus.OK, {"event_id": event_id})
                return

            if parts == ["telemetry", "bot-decision-batch"]:
                count = self.backend.record_bot_decisions_batch(payload.get("rows", []))
                self._send_json(HTTPStatus.OK, {"inserted": count})
                return

            self._log_suspicious("unknown_post_route", player_id=cast(str | None, player_hint))
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Route not found"})
        except PermissionError as exc:
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": str(exc)})
        except Exception as exc:
            LOGGER.exception("POST failed: path=%s", self.path)
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})


def run_server(host: str, port: int, db_path: str) -> None:
    backend = OnlineBackend(db_path)

    class BoundHandler(OnlineApiHandler):
        pass

    BoundHandler.backend = backend
    server = ThreadingHTTPServer((host, port), BoundHandler)
    LOGGER.info("online-api listening on http://%s:%s db=%s", host, port, db_path)
    print(f"online-api listening on http://{host}:{port} db={db_path}")
    server.serve_forever()


def main() -> None:
    load_dotenv()
    _init_sentry()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    parser = argparse.ArgumentParser(description="Run UptaCamp online API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--db", default=os.getenv("UPTACAMP_DB_PATH", "data/online_state.db"))
    args = parser.parse_args()
    run_server(args.host, args.port, args.db)


if __name__ == "__main__":
    main()
