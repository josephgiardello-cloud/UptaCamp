from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import logging
import os
from collections import defaultdict
from typing import Any

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


class OnlineWsServer:
    def __init__(self, backend: OnlineBackend):
        self.backend = backend
        self.rooms: dict[str, set[Any]] = defaultdict(set)
        self.last_updated: dict[str, str] = {}

    async def handler(self, websocket):
        match_id = None
        try:
            hello_raw = await asyncio.wait_for(websocket.recv(), timeout=8)
            hello = json.loads(hello_raw)
            match_id = str(hello.get("match_id", ""))
            player_id = str(hello.get("player_id", ""))
            token = str(hello.get("session_token", ""))
            if not match_id or not player_id or not token:
                await websocket.send(
                    json.dumps({"error": "auth payload requires match_id/player_id/session_token"})
                )
                await websocket.close()
                return
            if not self.backend.verify_session_token(player_id, token):
                await websocket.send(json.dumps({"error": "invalid session token"}))
                await websocket.close()
                return

            details = self.backend.get_match_details(match_id)
            summary = details["summary"]
            if player_id not in {summary["player_one_id"], summary["player_two_id"]}:
                await websocket.send(json.dumps({"error": "player is not in match"}))
                await websocket.close()
                return

            self.rooms[match_id].add(websocket)
            await websocket.send(json.dumps({"type": "match_snapshot", "match": details}))
            LOGGER.info("ws subscribe: match=%s player=%s", match_id, player_id)

            while True:
                # Keepalive from client; no-op.
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=15.0)
                    if str(msg).lower() in {"ping", '{"type":"ping"}'}:
                        await websocket.send(json.dumps({"type": "pong"}))
                except asyncio.TimeoutError:
                    await websocket.send(json.dumps({"type": "pong"}))
        except Exception as exc:
            LOGGER.info("ws disconnected: %s", exc)
        finally:
            if match_id is not None:
                self.rooms[match_id].discard(websocket)
                if not self.rooms[match_id]:
                    self.rooms.pop(match_id, None)

    async def broadcaster(self) -> None:
        while True:
            await asyncio.sleep(1.0)
            for match_id, sockets in list(self.rooms.items()):
                if not sockets:
                    continue
                try:
                    details = self.backend.get_match_details(match_id)
                except Exception:
                    continue
                updated_at = str(details["summary"]["updated_at"])
                if self.last_updated.get(match_id) == updated_at:
                    continue
                self.last_updated[match_id] = updated_at
                message = json.dumps({"type": "turn_update", "match": details})

                stale = []
                for sock in list(sockets):
                    try:
                        await sock.send(message)
                    except Exception:
                        stale.append(sock)
                for sock in stale:
                    sockets.discard(sock)


async def _run(host: str, port: int, db_path: str) -> None:
    import websockets  # type: ignore

    backend = OnlineBackend(db_path)
    server = OnlineWsServer(backend)
    async with websockets.serve(server.handler, host, port):
        LOGGER.info("online-ws listening on ws://%s:%s", host, port)
        await server.broadcaster()


def main() -> None:
    load_dotenv()
    _init_sentry()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )
    parser = argparse.ArgumentParser(description="Run UptaCamp websocket match server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--db", default=os.getenv("UPTACAMP_DB_PATH", "data/online_state.db"))
    args = parser.parse_args()
    asyncio.run(_run(args.host, args.port, args.db))


if __name__ == "__main__":
    main()
