from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(8)}"


def _elo_expected(rating_a: int, rating_b: int) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def _elo_update(rating_a: int, rating_b: int, score_a: float, k_factor: int = 24) -> tuple[int, int]:
    expected_a = _elo_expected(rating_a, rating_b)
    expected_b = _elo_expected(rating_b, rating_a)
    new_a = round(rating_a + k_factor * (score_a - expected_a))
    new_b = round(rating_b + k_factor * ((1.0 - score_a) - expected_b))
    return new_a, new_b


@dataclass(frozen=True)
class MatchSummary:
    match_id: str
    mode: str
    state: str
    player_one_id: str
    player_two_id: str
    active_player_id: str
    created_at: str
    updated_at: str
    turns_played: int


class OnlineBackend:
    """Concrete online/async backend for matchmaking, rooms, turns, and ratings.

    This module intentionally avoids framework abstractions so it can be embedded in
    pygame, a CLI service, or an HTTP layer later without changing core behavior.
    """

    def __init__(self, db_path: str | Path = "online_state.db"):
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS players (
                    player_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    rating INTEGER NOT NULL DEFAULT 1200,
                    games_played INTEGER NOT NULL DEFAULT 0,
                    wins INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    draws INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS invites (
                    invite_code TEXT PRIMARY KEY,
                    host_player_id TEXT NOT NULL,
                    guest_player_id TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(host_player_id) REFERENCES players(player_id),
                    FOREIGN KEY(guest_player_id) REFERENCES players(player_id)
                );

                CREATE TABLE IF NOT EXISTS matches (
                    match_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    state TEXT NOT NULL,
                    player_one_id TEXT NOT NULL,
                    player_two_id TEXT NOT NULL,
                    active_player_id TEXT NOT NULL,
                    winner_player_id TEXT,
                    game_state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finished_at TEXT,
                    FOREIGN KEY(player_one_id) REFERENCES players(player_id),
                    FOREIGN KEY(player_two_id) REFERENCES players(player_id),
                    FOREIGN KEY(active_player_id) REFERENCES players(player_id),
                    FOREIGN KEY(winner_player_id) REFERENCES players(player_id)
                );

                CREATE TABLE IF NOT EXISTS turns (
                    turn_id TEXT PRIMARY KEY,
                    match_id TEXT NOT NULL,
                    player_id TEXT NOT NULL,
                    turn_index INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(match_id, idempotency_key),
                    UNIQUE(match_id, turn_index),
                    FOREIGN KEY(match_id) REFERENCES matches(match_id),
                    FOREIGN KEY(player_id) REFERENCES players(player_id)
                );

                CREATE TABLE IF NOT EXISTS matchmaking_queue (
                    queue_id TEXT PRIMARY KEY,
                    player_id TEXT NOT NULL,
                    enqueued_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    matched_match_id TEXT,
                    UNIQUE(player_id, status),
                    FOREIGN KEY(player_id) REFERENCES players(player_id),
                    FOREIGN KEY(matched_match_id) REFERENCES matches(match_id)
                );

                CREATE TABLE IF NOT EXISTS bot_telemetry (
                    event_id TEXT PRIMARY KEY,
                    match_id TEXT,
                    phase TEXT NOT NULL,
                    ai_level INTEGER NOT NULL,
                    state_hash TEXT NOT NULL,
                    candidate_json TEXT NOT NULL,
                    selected_action TEXT NOT NULL,
                    expected_value REAL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(match_id) REFERENCES matches(match_id)
                );
                """
            )

    def upsert_player(self, player_id: str, display_name: str) -> None:
        now = _utc_now_iso()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO players (player_id, display_name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(player_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    updated_at=excluded.updated_at
                """,
                (player_id, display_name, now, now),
            )

    def create_invite(self, host_player_id: str) -> str:
        invite_code = secrets.token_hex(4).upper()
        now = _utc_now_iso()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO invites (invite_code, host_player_id, status, created_at, updated_at)
                VALUES (?, ?, 'open', ?, ?)
                """,
                (invite_code, host_player_id, now, now),
            )
        return invite_code

    def accept_invite(self, invite_code: str, guest_player_id: str) -> str:
        with self._lock:
            with self._connection() as conn:
                invite = conn.execute(
                    "SELECT * FROM invites WHERE invite_code = ?",
                    (invite_code,),
                ).fetchone()
                if invite is None:
                    raise ValueError("Invite does not exist")
                if invite["status"] != "open":
                    raise ValueError("Invite is not open")
                if invite["host_player_id"] == guest_player_id:
                    raise ValueError("Host cannot accept own invite")

                match_id = self._create_match_locked(
                    conn=conn,
                    mode="room",
                    player_one_id=invite["host_player_id"],
                    player_two_id=guest_player_id,
                )

                now = _utc_now_iso()
                conn.execute(
                    """
                    UPDATE invites
                    SET guest_player_id = ?, status = 'accepted', updated_at = ?
                    WHERE invite_code = ?
                    """,
                    (guest_player_id, now, invite_code),
                )
                return match_id

    def enqueue_for_matchmaking(self, player_id: str) -> str:
        queue_id = _new_id("queue")
        now = _utc_now_iso()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO matchmaking_queue (queue_id, player_id, enqueued_at, status)
                VALUES (?, ?, ?, 'waiting')
                """,
                (queue_id, player_id, now),
            )
        return queue_id

    def pair_waiting_players(self) -> Optional[str]:
        with self._lock:
            with self._connection() as conn:
                waiting = conn.execute(
                    """
                    SELECT queue_id, player_id FROM matchmaking_queue
                    WHERE status = 'waiting'
                    ORDER BY enqueued_at ASC
                    LIMIT 2
                    """
                ).fetchall()
                if len(waiting) < 2:
                    return None

                first, second = waiting
                match_id = self._create_match_locked(
                    conn=conn,
                    mode="ranked",
                    player_one_id=first["player_id"],
                    player_two_id=second["player_id"],
                )
                conn.execute(
                    """
                    UPDATE matchmaking_queue
                    SET status='matched', matched_match_id=?
                    WHERE queue_id IN (?, ?)
                    """,
                    (match_id, first["queue_id"], second["queue_id"]),
                )
                return match_id

    def _create_match_locked(
        self,
        conn: sqlite3.Connection,
        mode: str,
        player_one_id: str,
        player_two_id: str,
    ) -> str:
        match_id = _new_id("match")
        now = _utc_now_iso()
        initial_state = {
            "phase": "intro",
            "scores": [0, 0],
            "dealer": 0,
            "last_action": None,
        }
        conn.execute(
            """
            INSERT INTO matches (
                match_id, mode, state, player_one_id, player_two_id, active_player_id,
                game_state_json, created_at, updated_at
            )
            VALUES (?, ?, 'active', ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                mode,
                player_one_id,
                player_two_id,
                player_one_id,
                json.dumps(initial_state, separators=(",", ":")),
                now,
                now,
            ),
        )
        return match_id

    def get_match(self, match_id: str) -> MatchSummary:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT m.*, COALESCE(t.turn_count, 0) AS turn_count
                FROM matches m
                LEFT JOIN (
                    SELECT match_id, COUNT(*) AS turn_count
                    FROM turns
                    GROUP BY match_id
                ) t ON t.match_id = m.match_id
                WHERE m.match_id = ?
                """,
                (match_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Match does not exist")
            return MatchSummary(
                match_id=row["match_id"],
                mode=row["mode"],
                state=row["state"],
                player_one_id=row["player_one_id"],
                player_two_id=row["player_two_id"],
                active_player_id=row["active_player_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                turns_played=int(row["turn_count"]),
            )

    def submit_turn(
        self,
        match_id: str,
        player_id: str,
        action_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> int:
        """Submit a turn and return the committed turn index.

        Guarantees:
        - strict player turn order
        - idempotent retry support keyed by (match_id, idempotency_key)
        - serialized writes under process lock
        """

        with self._lock:
            with self._connection() as conn:
                existing = conn.execute(
                    """
                    SELECT turn_index FROM turns
                    WHERE match_id = ? AND idempotency_key = ?
                    """,
                    (match_id, idempotency_key),
                ).fetchone()
                if existing is not None:
                    return int(existing["turn_index"])

                match = conn.execute(
                    "SELECT * FROM matches WHERE match_id = ?",
                    (match_id,),
                ).fetchone()
                if match is None:
                    raise ValueError("Match does not exist")
                if match["state"] != "active":
                    raise ValueError("Match is not active")
                if match["active_player_id"] != player_id:
                    raise PermissionError("It is not this player's turn")

                turn_index_row = conn.execute(
                    "SELECT COALESCE(MAX(turn_index), -1) AS max_index FROM turns WHERE match_id = ?",
                    (match_id,),
                ).fetchone()
                turn_index = int(turn_index_row["max_index"]) + 1

                turn_id = _new_id("turn")
                now = _utc_now_iso()
                conn.execute(
                    """
                    INSERT INTO turns (
                        turn_id, match_id, player_id, turn_index,
                        action_type, payload_json, idempotency_key, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        turn_id,
                        match_id,
                        player_id,
                        turn_index,
                        action_type,
                        json.dumps(payload, separators=(",", ":")),
                        idempotency_key,
                        now,
                    ),
                )

                state = json.loads(match["game_state_json"])
                state["last_action"] = {
                    "turn_index": turn_index,
                    "player_id": player_id,
                    "action_type": action_type,
                    "payload": payload,
                }
                next_player = match["player_two_id"] if player_id == match["player_one_id"] else match["player_one_id"]
                conn.execute(
                    """
                    UPDATE matches
                    SET active_player_id = ?, game_state_json = ?, updated_at = ?
                    WHERE match_id = ?
                    """,
                    (
                        next_player,
                        json.dumps(state, separators=(",", ":")),
                        now,
                        match_id,
                    ),
                )

                return turn_index

    def finish_match(self, match_id: str, winner_player_id: Optional[str]) -> None:
        with self._lock:
            with self._connection() as conn:
                match = conn.execute(
                    "SELECT * FROM matches WHERE match_id = ?",
                    (match_id,),
                ).fetchone()
                if match is None:
                    raise ValueError("Match does not exist")
                if match["state"] != "active":
                    raise ValueError("Match already finalized")

                now = _utc_now_iso()
                conn.execute(
                    """
                    UPDATE matches
                    SET state='finished', winner_player_id=?, finished_at=?, updated_at=?
                    WHERE match_id=?
                    """,
                    (winner_player_id, now, now, match_id),
                )

                p1 = conn.execute("SELECT * FROM players WHERE player_id = ?", (match["player_one_id"],)).fetchone()
                p2 = conn.execute("SELECT * FROM players WHERE player_id = ?", (match["player_two_id"],)).fetchone()
                if p1 is None or p2 is None:
                    raise ValueError("Players missing for ratings update")

                if winner_player_id is None:
                    score_a = 0.5
                elif winner_player_id == p1["player_id"]:
                    score_a = 1.0
                elif winner_player_id == p2["player_id"]:
                    score_a = 0.0
                else:
                    raise ValueError("Winner must be player one, player two, or None for draw")

                new_a, new_b = _elo_update(int(p1["rating"]), int(p2["rating"]), score_a)

                def _record(player_row: sqlite3.Row, new_rating: int, result: str) -> None:
                    conn.execute(
                        """
                        UPDATE players
                        SET rating=?,
                            games_played=games_played+1,
                            wins=wins+?,
                            losses=losses+?,
                            draws=draws+?,
                            updated_at=?
                        WHERE player_id=?
                        """,
                        (
                            new_rating,
                            1 if result == "win" else 0,
                            1 if result == "loss" else 0,
                            1 if result == "draw" else 0,
                            now,
                            player_row["player_id"],
                        ),
                    )

                if score_a == 1.0:
                    _record(p1, new_a, "win")
                    _record(p2, new_b, "loss")
                elif score_a == 0.0:
                    _record(p1, new_a, "loss")
                    _record(p2, new_b, "win")
                else:
                    _record(p1, new_a, "draw")
                    _record(p2, new_b, "draw")

    def get_player_profile(self, player_id: str) -> dict[str, Any]:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM players WHERE player_id = ?", (player_id,)).fetchone()
            if row is None:
                raise ValueError("Player does not exist")
            return dict(row)

    def list_recent_matches(self, player_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM matches
                WHERE player_one_id = ? OR player_two_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (player_id, player_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def record_bot_decision(
        self,
        phase: str,
        ai_level: int,
        state_hash: str,
        candidates: list[dict[str, Any]],
        selected_action: str,
        expected_value: Optional[float],
        match_id: Optional[str] = None,
    ) -> str:
        event_id = _new_id("bot")
        now = _utc_now_iso()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO bot_telemetry (
                    event_id, match_id, phase, ai_level, state_hash,
                    candidate_json, selected_action, expected_value, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    match_id,
                    phase,
                    ai_level,
                    state_hash,
                    json.dumps(candidates, separators=(",", ":")),
                    selected_action,
                    expected_value,
                    now,
                ),
            )
        return event_id
