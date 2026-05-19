from __future__ import annotations

import asyncio
import json

import pytest

from online_ws_server import OnlineWsServer


class _FakeBackend:
    def __init__(self, valid_token: bool = True):
        self.valid_token = valid_token
        self.updated_at = "u1"

    def verify_session_token(self, player_id: str, token: str) -> bool:
        return self.valid_token

    def get_match_details(self, match_id: str):
        return {
            "summary": {
                "player_one_id": "p1",
                "player_two_id": "p2",
                "updated_at": self.updated_at,
            },
            "game_state": {"phase": "deal"},
        }


class _FakeWebSocket:
    def __init__(self, incoming):
        self._incoming = list(incoming)
        self.sent = []
        self.closed = False

    async def recv(self):
        if not self._incoming:
            raise RuntimeError("done")
        item = self._incoming.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def send(self, message: str):
        self.sent.append(json.loads(message))

    async def close(self):
        self.closed = True


def test_handler_rejects_missing_auth_payload():
    server = OnlineWsServer(_FakeBackend(valid_token=True))
    ws = _FakeWebSocket([json.dumps({})])

    asyncio.run(server.handler(ws))

    assert ws.closed is True
    assert ws.sent[0]["error"].startswith("auth payload requires")


def test_handler_rejects_invalid_token():
    server = OnlineWsServer(_FakeBackend(valid_token=False))
    ws = _FakeWebSocket([json.dumps({"match_id": "m1", "player_id": "p1", "session_token": "bad"})])

    asyncio.run(server.handler(ws))

    assert ws.closed is True
    assert ws.sent[0]["error"] == "invalid session token"


def test_handler_accepts_valid_subscriber_and_answers_ping():
    server = OnlineWsServer(_FakeBackend(valid_token=True))
    hello = json.dumps({"match_id": "m1", "player_id": "p1", "session_token": "ok"})
    ws = _FakeWebSocket([hello, "ping", RuntimeError("disconnect")])

    asyncio.run(server.handler(ws))

    sent_types = [msg.get("type") for msg in ws.sent]
    assert "match_snapshot" in sent_types
    assert "pong" in sent_types
    assert "m1" not in server.rooms


def test_broadcaster_pushes_turn_update_when_match_changes(monkeypatch):
    backend = _FakeBackend(valid_token=True)
    server = OnlineWsServer(backend)
    ws = _FakeWebSocket([])
    server.rooms["m1"].add(ws)

    calls = {"count": 0}

    async def _fast_sleep(_seconds: float):
        calls["count"] += 1
        if calls["count"] > 1:
            raise asyncio.CancelledError()

    monkeypatch.setattr("online_ws_server.asyncio.sleep", _fast_sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(server.broadcaster())

    assert ws.sent
    assert ws.sent[0]["type"] == "turn_update"
