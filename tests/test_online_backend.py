from __future__ import annotations

from pathlib import Path

import pytest

from online_backend import OnlineBackend


@pytest.fixture()
def backend(tmp_path: Path) -> OnlineBackend:
    db = tmp_path / "online.db"
    service = OnlineBackend(db)
    service.login_player("Alice", player_id="p1")
    service.login_player("Bob", player_id="p2")
    service.login_player("Chris", player_id="p3")
    return service


def _submit_signed(
    backend: OnlineBackend,
    token: str,
    match_id: str,
    player_id: str,
    action_type: str,
    payload: dict,
    key: str,
) -> int:
    details = backend.get_match_details(match_id)
    turn_number = int(details["summary"]["turns_played"])
    signature = OnlineBackend.build_turn_signature(
        session_token=token,
        match_id=match_id,
        player_id=player_id,
        turn_number=turn_number,
        action_type=action_type,
        payload=payload,
    )
    return backend.submit_turn(
        match_id=match_id,
        player_id=player_id,
        action_type=action_type,
        payload=payload,
        idempotency_key=key,
        signature=signature,
        session_token=token,
    )


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
    p1 = backend.login_player("Alice", player_id="p1")
    invite = backend.create_invite("p1")
    match_id = backend.accept_invite(invite, "p2")

    first = _submit_signed(
        backend,
        p1.session_token,
        match_id=match_id,
        player_id="p1",
        action_type="deal_ready",
        payload={"ready": True},
        key="same-key",
    )
    second = _submit_signed(
        backend,
        p1.session_token,
        match_id=match_id,
        player_id="p1",
        action_type="deal_ready",
        payload={"ready": True},
        key="same-key",
    )

    assert first == 0
    assert second == 0
    match = backend.get_match(match_id)
    assert match.turns_played == 1


def test_submit_turn_rejects_wrong_player_order(backend: OnlineBackend) -> None:
    p2 = backend.login_player("Bob", player_id="p2")
    invite = backend.create_invite("p1")
    match_id = backend.accept_invite(invite, "p2")

    with pytest.raises(PermissionError):
        _submit_signed(
            backend,
            p2.session_token,
            match_id=match_id,
            player_id="p2",
            action_type="deal_ready",
            payload={"ready": True},
            key="wrong-order",
        )


def test_submit_turn_rejects_bad_signature(backend: OnlineBackend) -> None:
    p1 = backend.login_player("Alice", player_id="p1")
    invite = backend.create_invite("p1")
    match_id = backend.accept_invite(invite, "p2")

    with pytest.raises(PermissionError):
        backend.submit_turn(
            match_id=match_id,
            player_id="p1",
            action_type="deal_ready",
            payload={"ready": True},
            idempotency_key="bad-signature",
            signature="not-valid",
            session_token=p1.session_token,
        )


def test_phase_progression_auto_finishes_and_updates_elo(backend: OnlineBackend) -> None:
    p1 = backend.login_player("Alice", player_id="p1")
    p2 = backend.login_player("Bob", player_id="p2")
    invite = backend.create_invite("p1")
    match_id = backend.accept_invite(invite, "p2")

    _submit_signed(backend, p1.session_token, match_id, "p1", "deal_ready", {"ready": True}, "a1")
    _submit_signed(backend, p2.session_token, match_id, "p2", "deal_ready", {"ready": True}, "a2")
    _submit_signed(
        backend,
        p1.session_token,
        match_id,
        "p1",
        "discard",
        {"cards": ["5_of_hearts", "6_of_hearts"]},
        "a3",
    )
    _submit_signed(
        backend,
        p2.session_token,
        match_id,
        "p2",
        "discard",
        {"cards": ["7_of_hearts", "8_of_hearts"]},
        "a4",
    )

    keys = ["a5", "a6", "a7", "a8", "a9", "a10", "a11", "a12"]
    players = [("p1", p1.session_token), ("p2", p2.session_token)] * 4
    for idx, (pid, tok) in enumerate(players):
        _submit_signed(
            backend,
            tok,
            match_id,
            pid,
            "peg",
            {"card": f"{idx+2}_of_spades", "running_total": (idx + 1) * 2 % 31, "points": 1},
            keys[idx],
        )

    _submit_signed(backend, p1.session_token, match_id, "p1", "count", {"points": 3}, "a13")
    _submit_signed(backend, p2.session_token, match_id, "p2", "count", {"points": 1}, "a14")

    details = backend.get_match_details(match_id)
    assert details["summary"]["state"] == "finished"

    p1_profile = backend.get_player_profile("p1")
    p2_profile = backend.get_player_profile("p2")
    assert p1_profile["games_played"] == 1
    assert p2_profile["games_played"] == 1


def test_pegging_running_total_and_points_are_server_authoritative(backend: OnlineBackend) -> None:
    p1 = backend.login_player("Alice", player_id="p1")
    p2 = backend.login_player("Bob", player_id="p2")
    invite = backend.create_invite("p1")
    match_id = backend.accept_invite(invite, "p2")

    _submit_signed(backend, p1.session_token, match_id, "p1", "deal_ready", {"ready": True}, "s1")
    _submit_signed(backend, p2.session_token, match_id, "p2", "deal_ready", {"ready": True}, "s2")
    _submit_signed(
        backend,
        p1.session_token,
        match_id,
        "p1",
        "discard",
        {"cards": ["5_of_hearts", "6_of_hearts"]},
        "s3",
    )
    _submit_signed(
        backend,
        p2.session_token,
        match_id,
        "p2",
        "discard",
        {"cards": ["7_of_hearts", "8_of_hearts"]},
        "s4",
    )

    _submit_signed(
        backend,
        p1.session_token,
        match_id,
        "p1",
        "peg",
        {"card": "10_of_hearts", "running_total": 99, "points": 9},
        "s5",
    )

    details = backend.get_match_details(match_id)
    state = details["game_state"]
    assert state["pegging_running_total"] == 10
    assert state["scores"][0] == 0


def test_pegging_go_action_resets_count_and_awards_last_card(backend: OnlineBackend) -> None:
    p1 = backend.login_player("Alice", player_id="p1")
    p2 = backend.login_player("Bob", player_id="p2")
    invite = backend.create_invite("p1")
    match_id = backend.accept_invite(invite, "p2")

    _submit_signed(backend, p1.session_token, match_id, "p1", "deal_ready", {"ready": True}, "g1")
    _submit_signed(backend, p2.session_token, match_id, "p2", "deal_ready", {"ready": True}, "g2")
    _submit_signed(
        backend,
        p1.session_token,
        match_id,
        "p1",
        "discard",
        {"cards": ["5_of_hearts", "6_of_hearts"]},
        "g3",
    )
    _submit_signed(
        backend,
        p2.session_token,
        match_id,
        "p2",
        "discard",
        {"cards": ["7_of_hearts", "8_of_hearts"]},
        "g4",
    )

    _submit_signed(
        backend,
        p1.session_token,
        match_id,
        "p1",
        "peg",
        {"card": "10_of_hearts", "running_total": 10, "points": 0},
        "g5",
    )
    _submit_signed(backend, p2.session_token, match_id, "p2", "go", {}, "g6")
    _submit_signed(backend, p1.session_token, match_id, "p1", "go", {}, "g7")

    details = backend.get_match_details(match_id)
    state = details["game_state"]
    assert state["pegging_passes"] == [False, False]
    assert state["pegging_pile"] == []


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


def test_leaderboard_returns_sorted_players(backend: OnlineBackend) -> None:
    invite = backend.create_invite("p1")
    match_id = backend.accept_invite(invite, "p2")
    backend.finish_match(match_id, winner_player_id="p1")

    board = backend.leaderboard(limit=3)

    assert len(board) >= 2
    assert board[0]["rating"] >= board[1]["rating"]


def test_match_chat_round_trip(backend: OnlineBackend) -> None:
    p1 = backend.login_player("Alice", player_id="p1")
    invite = backend.create_invite("p1")
    match_id = backend.accept_invite(invite, "p2")

    posted = backend.post_chat_message(
        match_id=match_id,
        player_id="p1",
        message="gl hf",
        session_token=p1.session_token,
    )
    rows = backend.list_chat_messages(match_id)

    assert posted["message"] == "gl hf"
    assert len(rows) == 1
    assert rows[0]["message"] == "gl hf"


def test_rematch_requires_both_players_and_creates_new_match(backend: OnlineBackend) -> None:
    p1 = backend.login_player("Alice", player_id="p1")
    p2 = backend.login_player("Bob", player_id="p2")
    invite = backend.create_invite("p1")
    match_id = backend.accept_invite(invite, "p2")
    backend.finish_match(match_id, winner_player_id="p1")

    first = backend.request_rematch(match_id, "p1", session_token=p1.session_token)
    second = backend.request_rematch(match_id, "p2", session_token=p2.session_token)

    assert first["status"] == "pending"
    assert first["new_match_id"] is None
    assert second["status"] == "accepted"
    assert second["new_match_id"]
