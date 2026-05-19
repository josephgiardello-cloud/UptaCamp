from __future__ import annotations

from pathlib import Path

import pytest

from online_backend import OnlineBackend


@pytest.fixture()
def backend(tmp_path: Path) -> OnlineBackend:
    db = tmp_path / "online.db"
    service = OnlineBackend(db)
    service.upsert_player("p1", "Alice")
    service.upsert_player("p2", "Bob")
    service.upsert_player("p3", "Chris")
    return service


def test_invite_accept_creates_room_match(backend: OnlineBackend) -> None:
    invite = backend.create_invite("p1")
    match_id = backend.accept_invite(invite, "p2")
    match = backend.get_match(match_id)

    assert match.mode == "room"
    assert match.player_one_id == "p1"
    assert match.player_two_id == "p2"
    assert match.state == "active"


def test_matchmaking_pairs_two_waiting_players(backend: OnlineBackend) -> None:
    backend.enqueue_for_matchmaking("p1")
    backend.enqueue_for_matchmaking("p2")
    match_id = backend.pair_waiting_players()

    assert match_id is not None
    match = backend.get_match(match_id)
    assert match.mode == "ranked"
    assert {match.player_one_id, match.player_two_id} == {"p1", "p2"}


def test_submit_turn_is_idempotent(backend: OnlineBackend) -> None:
    invite = backend.create_invite("p1")
    match_id = backend.accept_invite(invite, "p2")

    first = backend.submit_turn(
        match_id=match_id,
        player_id="p1",
        action_type="play_card",
        payload={"card": "5_of_hearts"},
        idempotency_key="same-key",
    )
    second = backend.submit_turn(
        match_id=match_id,
        player_id="p1",
        action_type="play_card",
        payload={"card": "5_of_hearts"},
        idempotency_key="same-key",
    )

    assert first == 0
    assert second == 0
    match = backend.get_match(match_id)
    assert match.turns_played == 1


def test_submit_turn_rejects_wrong_player_order(backend: OnlineBackend) -> None:
    invite = backend.create_invite("p1")
    match_id = backend.accept_invite(invite, "p2")

    with pytest.raises(PermissionError):
        backend.submit_turn(
            match_id=match_id,
            player_id="p2",
            action_type="play_card",
            payload={"card": "7_of_spades"},
            idempotency_key="wrong-order",
        )


def test_finish_match_updates_elo_and_stats(backend: OnlineBackend) -> None:
    invite = backend.create_invite("p1")
    match_id = backend.accept_invite(invite, "p2")

    backend.finish_match(match_id, winner_player_id="p1")

    p1 = backend.get_player_profile("p1")
    p2 = backend.get_player_profile("p2")

    assert p1["games_played"] == 1
    assert p2["games_played"] == 1
    assert p1["wins"] == 1
    assert p2["losses"] == 1
    assert p1["rating"] > 1200
    assert p2["rating"] < 1200


def test_recent_matches_returns_player_history(backend: OnlineBackend) -> None:
    invite = backend.create_invite("p1")
    match_id = backend.accept_invite(invite, "p2")
    backend.finish_match(match_id, winner_player_id=None)

    rows = backend.list_recent_matches("p1")

    assert len(rows) == 1
    assert rows[0]["match_id"] == match_id
    assert rows[0]["state"] == "finished"
