from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from online_backend import OnlineBackend


class OnlineApiHandler(BaseHTTPRequestHandler):
    backend: OnlineBackend

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
                match = self.backend.get_match(parts[1])
                self._send_json(HTTPStatus.OK, match.__dict__)
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
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        payload = self._read_json_body()

        try:
            if parts == ["players", "upsert"]:
                self.backend.upsert_player(payload["player_id"], payload["display_name"])
                self._send_json(HTTPStatus.OK, {"ok": True})
                return

            if parts == ["invites", "create"]:
                code = self.backend.create_invite(payload["host_player_id"])
                self._send_json(HTTPStatus.OK, {"invite_code": code})
                return

            if parts == ["invites", "accept"]:
                match_id = self.backend.accept_invite(payload["invite_code"], payload["guest_player_id"])
                self._send_json(HTTPStatus.OK, {"match_id": match_id})
                return

            if parts == ["matchmaking", "enqueue"]:
                queue_id = self.backend.enqueue_for_matchmaking(payload["player_id"])
                self._send_json(HTTPStatus.OK, {"queue_id": queue_id})
                return

            if parts == ["matchmaking", "pair"]:
                match_id = self.backend.pair_waiting_players()
                self._send_json(HTTPStatus.OK, {"match_id": match_id})
                return

            if len(parts) == 3 and parts[0] == "matches" and parts[2] == "turns":
                turn_index = self.backend.submit_turn(
                    match_id=parts[1],
                    player_id=payload["player_id"],
                    action_type=payload["action_type"],
                    payload=payload.get("payload", {}),
                    idempotency_key=payload["idempotency_key"],
                )
                self._send_json(HTTPStatus.OK, {"turn_index": turn_index})
                return

            if len(parts) == 3 and parts[0] == "matches" and parts[2] == "finish":
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

            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Route not found"})
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})


def run_server(host: str, port: int, db_path: str) -> None:
    backend = OnlineBackend(db_path)

    class BoundHandler(OnlineApiHandler):
        pass

    BoundHandler.backend = backend
    server = ThreadingHTTPServer((host, port), BoundHandler)
    print(f"online-api listening on http://{host}:{port} db={db_path}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run UptaCamp online API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--db", default="online_state.db")
    args = parser.parse_args()
    run_server(args.host, args.port, args.db)


if __name__ == "__main__":
    main()
