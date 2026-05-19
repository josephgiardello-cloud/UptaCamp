from __future__ import annotations

import contextlib
import socket
import threading
from pathlib import Path

from http.server import ThreadingHTTPServer

from online_api_server import OnlineApiHandler
from online_backend import OnlineBackend
from online_client import OnlineClient


@contextlib.contextmanager
def _serve_backend(db_path: Path):
    backend = OnlineBackend(db_path)

    class BoundHandler(OnlineApiHandler):
        pass

    BoundHandler.backend = backend

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    host, port = sock.getsockname()
    sock.close()

    server = ThreadingHTTPServer((host, port), BoundHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield backend, f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


def _action_for_phase(turn_index: int, phase: str):
    if phase == "deal":
        return "deal_ready", {"ready": True}
    if phase == "discard":
        return "discard", {"cards": ["5_of_hearts", "king_of_clubs"]}
    if phase == "pegging":
        return "peg", {"card": "7_of_spades", "running_total": (turn_index * 3) % 31, "points": 1}
    if phase == "counting":
        return "count", {"points": 2 if turn_index % 2 == 0 else 1}
    raise AssertionError(f"unexpected phase {phase}")


def test_end_to_end_online_match_updates_winner_and_elo(tmp_path: Path) -> None:
    db_path = tmp_path / "e2e.db"
    with _serve_backend(db_path) as (backend, url):
        c1 = OnlineClient(url)
        c2 = OnlineClient(url)

        p1 = c1.login("Alice")
        p2 = c2.login("Bob")

        invite = c1.create_room()
        match_id = c2.join_room(invite)

        for _ in range(32):
            details = c1.get_match(match_id)
            state = details["summary"]["state"]
            if state == "finished":
                break

            active = details["summary"]["active_player_id"]
            phase = details["game_state"]["phase"]
            turns = int(details["summary"]["turns_played"])
            action, payload = _action_for_phase(turns, phase)
            if active == p1["player_id"]:
                c1.submit_turn(match_id, action, payload)
            elif active == p2["player_id"]:
                c2.submit_turn(match_id, action, payload)
            else:
                raise AssertionError("unknown active player")

        details = c1.get_match(match_id)
        assert details["summary"]["state"] == "finished"

        p1_profile = backend.get_player_profile(p1["player_id"])
        p2_profile = backend.get_player_profile(p2["player_id"])
        assert p1_profile["games_played"] == 1
        assert p2_profile["games_played"] == 1
        assert p1_profile["rating"] != 1200 or p2_profile["rating"] != 1200
