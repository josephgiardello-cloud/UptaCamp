from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from online_backend import OnlineBackend


class OnlineClientError(RuntimeError):
    pass


class OnlineClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8787"):
        self.base_url = base_url.rstrip("/")
        self.player_id: str | None = None
        self.display_name: str | None = None
        self.session_token: str | None = None

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Content-Type": "application/json"}
        if self.session_token:
            headers["Authorization"] = f"Bearer {self.session_token}"
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url=url, method=method, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")
                detail = json.loads(body).get("error", body)
            except Exception:
                detail = str(exc)
            raise OnlineClientError(f"{method} {path} failed: {detail}") from exc
        except urllib.error.URLError as exc:
            raise OnlineClientError(f"Cannot reach online service at {self.base_url}") from exc

    def login(self, display_name: str) -> dict[str, str]:
        res = self._request("POST", "/players", {"display_name": display_name})
        self.player_id = str(res["player_id"])
        self.display_name = str(res["display_name"])
        self.session_token = str(res["session_token"])
        return {
            "player_id": self.player_id,
            "display_name": self.display_name,
            "session_token": self.session_token,
        }

    def create_room(self) -> str:
        self._require_login()
        res = self._request("POST", "/invites/create", {"host_player_id": self.player_id})
        return str(res["invite_code"])

    def join_room(self, invite_code: str) -> str:
        self._require_login()
        res = self._request(
            "POST",
            "/invites/accept",
            {"invite_code": invite_code.strip().upper(), "guest_player_id": self.player_id},
        )
        return str(res["match_id"])

    def enqueue(self) -> str:
        self._require_login()
        res = self._request("POST", "/matchmaking/enqueue", {"player_id": self.player_id})
        return str(res["queue_id"])

    def trigger_pair(self) -> str | None:
        res = self._request("POST", "/matchmaking/pair", {})
        raw = res.get("match_id")
        return str(raw) if raw else None

    def get_match(self, match_id: str) -> dict[str, Any]:
        return self._request("GET", f"/matches/{match_id}")

    def leaderboard(self, limit: int = 50) -> list[dict[str, Any]]:
        res = self._request("GET", f"/leaderboard?limit={limit}")
        return list(res.get("players", []))

    def post_chat(self, match_id: str, message: str) -> dict[str, Any]:
        self._require_login()
        return self._request(
            "POST",
            f"/matches/{match_id}/chat",
            {
                "player_id": self.player_id,
                "message": message,
            },
        )

    def get_chat(self, match_id: str, limit: int = 100) -> list[dict[str, Any]]:
        res = self._request("GET", f"/matches/{match_id}/chat?limit={limit}")
        return list(res.get("messages", []))

    def request_rematch(self, match_id: str) -> dict[str, Any]:
        self._require_login()
        return self._request(
            "POST",
            f"/matches/{match_id}/rematch",
            {
                "player_id": self.player_id,
            },
        )

    def submit_turn(self, match_id: str, action_type: str, payload: dict[str, Any]) -> int:
        self._require_login()
        details = self.get_match(match_id)
        turn_number = int(details["summary"]["turns_played"])
        signature = OnlineBackend.build_turn_signature(
            session_token=self.session_token or "",
            match_id=match_id,
            player_id=self.player_id or "",
            turn_number=turn_number,
            action_type=action_type,
            payload=payload,
        )
        idempotency_key = f"{self.player_id}-{uuid.uuid4().hex[:12]}"
        res = self._request(
            "POST",
            f"/matches/{match_id}/turns",
            {
                "player_id": self.player_id,
                "action_type": action_type,
                "payload": payload,
                "idempotency_key": idempotency_key,
                "signature": signature,
            },
        )
        return int(res["turn_index"])

    def _require_login(self) -> None:
        if not self.player_id or not self.session_token:
            raise OnlineClientError("You must log in first")


class MatchEventStream:
    """Background match updates with websocket-first and polling fallback."""

    def __init__(
        self,
        client: OnlineClient,
        match_id: str,
        ws_url: str | None = None,
        *,
        poll_interval_s: float = 2.0,
        ws_recv_timeout_s: float = 1.5,
    ):
        self.client = client
        self.match_id = match_id
        self.ws_url = ws_url
        self.poll_interval_s = max(0.25, float(poll_interval_s))
        self.ws_recv_timeout_s = max(0.25, float(ws_recv_timeout_s))
        self.last_snapshot: dict[str, Any] | None = None
        self.last_error: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        # WebSocket support is optional; fallback to polling if missing/fails.
        ws_url = self.ws_url or self.client.base_url.replace("http://", "ws://").replace(
            "https://", "wss://"
        )

        try:
            import asyncio

            import websockets  # type: ignore

            async def _listen() -> None:
                async with websockets.connect(ws_url) as sock:
                    await sock.send(
                        json.dumps(
                            {
                                "match_id": self.match_id,
                                "player_id": self.client.player_id,
                                "session_token": self.client.session_token,
                            }
                        )
                    )
                    while not self._stop.is_set():
                        msg = await asyncio.wait_for(
                            sock.recv(), timeout=self.ws_recv_timeout_s
                        )
                        data = json.loads(str(msg))
                        if "error" in data:
                            raise OnlineClientError(str(data["error"]))
                        if data.get("type") in {"match_snapshot", "turn_update"}:
                            self.last_snapshot = data.get("match", data)

            asyncio.run(_listen())
            return
        except Exception as exc:
            self.last_error = f"websocket unavailable, using polling: {exc}"

        while not self._stop.is_set():
            try:
                self.last_snapshot = self.client.get_match(self.match_id)
            except Exception as exc:
                self.last_error = str(exc)
            time.sleep(self.poll_interval_s)
