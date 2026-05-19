from __future__ import annotations

import argparse
import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from online_backend import OnlineBackend


LOGGER = logging.getLogger(__name__)


class OnlineApiHandler(BaseHTTPRequestHandler):
    backend: OnlineBackend

    def _extract_bearer(self) -> str | None:
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        token = auth[7:].strip()
        return token or None

    def _require_auth(self, player_id: str) -> str:
        token = self._extract_bearer()
        if not token:
            raise PermissionError("Missing bearer token")
        if not self.backend.verify_session_token(player_id, token):
            raise PermissionError("Invalid session token")
        return token

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        body = self.rfile.read(length)
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def log_message(self, fmt: str, *args):
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        try:
            if parts == ["health"]:
                self._send_json(HTTPStatus.OK, {"status": "ok"})
                return

            if len(parts) == 2 and parts[0] == "matches":
                details = self.backend.get_match_details(parts[1])
                self._send_json(HTTPStatus.OK, details)
                return

            if len(parts) == 2 and parts[0] == "players":
                profile = self.backend.get_player_profile(parts[1])
                self._send_json(HTTPStatus.OK, profile)
                return

            if len(parts) == 3 and parts[0] == "players" and parts[2] == "matches":
                qs = parse_qs(parsed.query)
                limit = int(qs.get("limit", ["20"])[0])
                rows = self.backend.list_recent_matches(parts[1], limit=limit)
                self._send_json(HTTPStatus.OK, {"matches": rows})
                return

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
                match_id = self.backend.accept_invite(payload["invite_code"], payload["guest_player_id"])
                self._send_json(HTTPStatus.OK, {"match_id": match_id})
                return

            if parts == ["matchmaking", "enqueue"]:
                self._require_auth(payload["player_id"])
                queue_id = self.backend.enqueue_for_matchmaking(payload["player_id"])
                self._send_json(HTTPStatus.OK, {"queue_id": queue_id})
                return

            if parts == ["matchmaking", "pair"]:
                match_id = self.backend.pair_waiting_players()
                self._send_json(HTTPStatus.OK, {"match_id": match_id})
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
                if owner:
                    self._require_auth(owner)
                self.backend.finish_match(parts[1], payload.get("winner_player_id"))
                self._send_json(HTTPStatus.OK, {"ok": True})
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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    parser = argparse.ArgumentParser(description="Run UptaCamp online API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--db", default="online_state.db")
    args = parser.parse_args()
    run_server(args.host, args.port, args.db)


if __name__ == "__main__":
    main()
