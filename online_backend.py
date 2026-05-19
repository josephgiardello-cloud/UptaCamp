from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


LOGGER = logging.getLogger(__name__)


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


@dataclass(frozen=True)
class LoginResult:
    player_id: str
    display_name: str
    session_token: str


class OnlineBackend:
    """Concrete online/async backend for matchmaking, rooms, turns, and ratings.

    This module intentionally avoids framework abstractions so it can be embedded in
    pygame, a CLI service, or an HTTP layer later without changing core behavior.
    """

    PHASES = ["deal", "discard", "pegging", "counting", "finished"]
    PHASE_TURN_TARGET = {
        "deal": 2,
        "discard": 2,
        "pegging": 8,
        "counting": 2,
    }

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
                    session_token_hash TEXT,
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
                    signature TEXT,
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

                CREATE TABLE IF NOT EXISTS match_chat (
                    message_id TEXT PRIMARY KEY,
                    match_id TEXT NOT NULL,
                    player_id TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(match_id) REFERENCES matches(match_id),
                    FOREIGN KEY(player_id) REFERENCES players(player_id)
                );

                CREATE TABLE IF NOT EXISTS rematch_requests (
                    request_id TEXT PRIMARY KEY,
                    prior_match_id TEXT NOT NULL,
                    requested_by_player_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(prior_match_id, requested_by_player_id),
                    FOREIGN KEY(prior_match_id) REFERENCES matches(match_id),
                    FOREIGN KEY(requested_by_player_id) REFERENCES players(player_id)
                );

                CREATE INDEX IF NOT EXISTS idx_matches_player_one ON matches(player_one_id);
                CREATE INDEX IF NOT EXISTS idx_matches_player_two ON matches(player_two_id);
                CREATE INDEX IF NOT EXISTS idx_turns_match_id ON turns(match_id);
                CREATE INDEX IF NOT EXISTS idx_queue_status_time ON matchmaking_queue(status, enqueued_at);
                CREATE INDEX IF NOT EXISTS idx_telemetry_match ON bot_telemetry(match_id);
                CREATE INDEX IF NOT EXISTS idx_chat_match_time ON match_chat(match_id, created_at);
                """
            )

            cols = {
                row["name"]: row["type"]
                for row in conn.execute("PRAGMA table_info(players)").fetchall()
            }
            if "session_token_hash" not in cols:
                conn.execute("ALTER TABLE players ADD COLUMN session_token_hash TEXT")

            turn_cols = {
                row["name"]: row["type"]
                for row in conn.execute("PRAGMA table_info(turns)").fetchall()
            }
            if "signature" not in turn_cols:
                conn.execute("ALTER TABLE turns ADD COLUMN signature TEXT")

    @staticmethod
    def _hash_token(session_token: str) -> str:
        return hashlib.sha256(session_token.encode("utf-8")).hexdigest()

    @staticmethod
    def build_turn_signature(
        session_token: str,
        match_id: str,
        player_id: str,
        turn_number: int,
        action_type: str,
        payload: dict[str, Any],
    ) -> str:
        payload_blob = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        msg = f"{match_id}|{player_id}|{turn_number}|{action_type}|{payload_blob}".encode("utf-8")
        return hmac.new(session_token.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    def login_player(self, display_name: str, player_id: Optional[str] = None) -> LoginResult:
        display_name = display_name.strip()
        if not display_name:
            raise ValueError("Display name cannot be blank")

        now = _utc_now_iso()
        resolved_player_id = player_id or _new_id("player")
        session_token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(session_token)

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO players (player_id, display_name, session_token_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(player_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    session_token_hash=excluded.session_token_hash,
                    updated_at=excluded.updated_at
                """,
                (resolved_player_id, display_name, token_hash, now, now),
            )

        LOGGER.info("login: player_id=%s display_name=%s", resolved_player_id, display_name)
        return LoginResult(
            player_id=resolved_player_id,
            display_name=display_name,
            session_token=session_token,
        )

    def verify_session_token(self, player_id: str, session_token: str) -> bool:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT session_token_hash FROM players WHERE player_id = ?",
                (player_id,),
            ).fetchone()
            if row is None or not row["session_token_hash"]:
                return False
            return hmac.compare_digest(str(row["session_token_hash"]), self._hash_token(session_token))

    def upsert_player(self, player_id: str, display_name: str) -> None:
        now = _utc_now_iso()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO players (player_id, display_name, created_at, updated_at, session_token_hash)
                VALUES (?, ?, ?, ?, COALESCE((SELECT session_token_hash FROM players WHERE player_id = ?), NULL))
                ON CONFLICT(player_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    updated_at=excluded.updated_at
                """,
                (player_id, display_name, now, now, player_id),
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
            "phase": "deal",
            "phase_index": 0,
            "phase_progress": 0,
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

    def _get_match_row(self, conn: sqlite3.Connection, match_id: str) -> sqlite3.Row:
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
        return row

    def get_match(self, match_id: str) -> MatchSummary:
        with self._connection() as conn:
            row = self._get_match_row(conn, match_id)
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

    def get_match_details(self, match_id: str) -> dict[str, Any]:
        with self._connection() as conn:
            row = self._get_match_row(conn, match_id)
            state = json.loads(row["game_state_json"])
            return {
                "summary": {
                    "match_id": row["match_id"],
                    "mode": row["mode"],
                    "state": row["state"],
                    "player_one_id": row["player_one_id"],
                    "player_two_id": row["player_two_id"],
                    "active_player_id": row["active_player_id"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "turns_played": int(row["turn_count"]),
                },
                "game_state": state,
            }

    @staticmethod
    def _validate_action(phase: str, action_type: str, payload: dict[str, Any]) -> None:
        if phase == "deal":
            if action_type != "deal_ready":
                raise ValueError("Only deal_ready is valid during deal phase")
            return
        if phase == "discard":
            cards = payload.get("cards")
            if action_type != "discard" or not isinstance(cards, list) or len(cards) != 2:
                raise ValueError("Discard phase requires discard action with exactly 2 cards")
            return
        if phase == "pegging":
            if action_type != "peg":
                raise ValueError("Pegging phase requires peg action")
            if not isinstance(payload.get("card"), str):
                raise ValueError("Peg action requires card label")
            running_total = payload.get("running_total")
            if not isinstance(running_total, int) or running_total < 0 or running_total > 31:
                raise ValueError("Peg action requires running_total between 0 and 31")
            return
        if phase == "counting":
            points = payload.get("points")
            if action_type != "count" or not isinstance(points, int) or points < 0 or points > 29:
                raise ValueError("Counting phase requires count action with points 0..29")
            return
        raise ValueError("No actions accepted for current phase")

    def _finish_match_locked(
        self,
        conn: sqlite3.Connection,
        match_row: sqlite3.Row,
        winner_player_id: Optional[str],
    ) -> None:
        match_id = str(match_row["match_id"])
        if match_row["state"] != "active":
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

        p1 = conn.execute("SELECT * FROM players WHERE player_id = ?", (match_row["player_one_id"],)).fetchone()
        p2 = conn.execute("SELECT * FROM players WHERE player_id = ?", (match_row["player_two_id"],)).fetchone()
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

        LOGGER.info("finish_match: match_id=%s winner=%s", match_id, winner_player_id)

    def submit_turn(
        self,
        match_id: str,
        player_id: str,
        action_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
        signature: Optional[str] = None,
        session_token: Optional[str] = None,
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

                if session_token:
                    if not self.verify_session_token(player_id, session_token):
                        raise PermissionError("Invalid session token")

                turn_index_row = conn.execute(
                    "SELECT COALESCE(MAX(turn_index), -1) AS max_index FROM turns WHERE match_id = ?",
                    (match_id,),
                ).fetchone()
                turn_index = int(turn_index_row["max_index"]) + 1

                state = json.loads(match["game_state_json"])
                phase = str(state.get("phase", "deal"))
                self._validate_action(phase, action_type, payload)

                if session_token:
                    expected_signature = self.build_turn_signature(
                        session_token=session_token,
                        match_id=match_id,
                        player_id=player_id,
                        turn_number=turn_index,
                        action_type=action_type,
                        payload=payload,
                    )
                    if not signature or not hmac.compare_digest(signature, expected_signature):
                        raise PermissionError("Invalid turn signature")

                turn_id = _new_id("turn")
                now = _utc_now_iso()
                conn.execute(
                    """
                    INSERT INTO turns (
                        turn_id, match_id, player_id, turn_index,
                        action_type, payload_json, signature, idempotency_key, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        turn_id,
                        match_id,
                        player_id,
                        turn_index,
                        action_type,
                        json.dumps(payload, separators=(",", ":")),
                        signature,
                        idempotency_key,
                        now,
                    ),
                )

                if action_type in ("peg", "count"):
                    points = payload.get("points")
                    if isinstance(points, int):
                        idx = 0 if player_id == match["player_one_id"] else 1
                        state["scores"][idx] += points

                state["last_action"] = {
                    "turn_index": turn_index,
                    "player_id": player_id,
                    "action_type": action_type,
                    "payload": payload,
                }

                current_phase = str(state.get("phase", "deal"))
                progress = int(state.get("phase_progress", 0)) + 1
                state["phase_progress"] = progress

                target = self.PHASE_TURN_TARGET.get(current_phase, 0)
                if target and progress >= target:
                    next_phase_index = min(int(state.get("phase_index", 0)) + 1, len(self.PHASES) - 1)
                    next_phase = self.PHASES[next_phase_index]
                    state["phase_index"] = next_phase_index
                    state["phase"] = next_phase
                    state["phase_progress"] = 0

                next_player = match["player_two_id"] if player_id == match["player_one_id"] else match["player_one_id"]

                if state.get("phase") == "finished":
                    p1_score = int(state["scores"][0])
                    p2_score = int(state["scores"][1])
                    winner: Optional[str]
                    if p1_score > p2_score:
                        winner = str(match["player_one_id"])
                    elif p2_score > p1_score:
                        winner = str(match["player_two_id"])
                    else:
                        winner = None
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
                    refreshed = conn.execute("SELECT * FROM matches WHERE match_id = ?", (match_id,)).fetchone()
                    if refreshed is None:
                        raise ValueError("Match disappeared during submit")
                    self._finish_match_locked(conn, refreshed, winner)
                    return turn_index

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

                LOGGER.info(
                    "submit_turn: match_id=%s turn=%s player=%s action=%s phase=%s",
                    match_id,
                    turn_index,
                    player_id,
                    action_type,
                    state.get("phase"),
                )

                return turn_index

    def finish_match(self, match_id: str, winner_player_id: Optional[str]) -> None:
        with self._lock:
            with self._connection() as conn:
                match = conn.execute("SELECT * FROM matches WHERE match_id = ?", (match_id,)).fetchone()
                if match is None:
                    raise ValueError("Match does not exist")
                self._finish_match_locked(conn, match, winner_player_id)

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

    def leaderboard(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT player_id, display_name, rating, games_played, wins, losses, draws
                FROM players
                ORDER BY rating DESC, wins DESC, games_played DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def post_chat_message(
        self,
        match_id: str,
        player_id: str,
        message: str,
        session_token: Optional[str] = None,
    ) -> dict[str, Any]:
        text = message.strip()
        if not text:
            raise ValueError("Message cannot be blank")
        if len(text) > 400:
            raise ValueError("Message too long")
        if session_token and not self.verify_session_token(player_id, session_token):
            raise PermissionError("Invalid session token")

        now = _utc_now_iso()
        message_id = _new_id("chat")
        with self._connection() as conn:
            match = conn.execute("SELECT * FROM matches WHERE match_id = ?", (match_id,)).fetchone()
            if match is None:
                raise ValueError("Match does not exist")
            if player_id not in {match["player_one_id"], match["player_two_id"]}:
                raise PermissionError("Player is not in this match")
            conn.execute(
                """
                INSERT INTO match_chat (message_id, match_id, player_id, message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (message_id, match_id, player_id, text, now),
            )
        return {
            "message_id": message_id,
            "match_id": match_id,
            "player_id": player_id,
            "message": text,
            "created_at": now,
        }

    def list_chat_messages(self, match_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT message_id, match_id, player_id, message, created_at
                FROM match_chat
                WHERE match_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (match_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def request_rematch(
        self,
        prior_match_id: str,
        player_id: str,
        session_token: Optional[str] = None,
    ) -> dict[str, Any]:
        if session_token and not self.verify_session_token(player_id, session_token):
            raise PermissionError("Invalid session token")

        with self._lock:
            with self._connection() as conn:
                prior = conn.execute("SELECT * FROM matches WHERE match_id = ?", (prior_match_id,)).fetchone()
                if prior is None:
                    raise ValueError("Prior match does not exist")
                if prior["state"] != "finished":
                    raise ValueError("Rematch allowed only for finished matches")
                if player_id not in {prior["player_one_id"], prior["player_two_id"]}:
                    raise PermissionError("Player is not in this match")

                conn.execute(
                    """
                    INSERT OR IGNORE INTO rematch_requests (request_id, prior_match_id, requested_by_player_id, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (_new_id("rmq"), prior_match_id, player_id, _utc_now_iso()),
                )

                req_rows = conn.execute(
                    "SELECT requested_by_player_id FROM rematch_requests WHERE prior_match_id = ?",
                    (prior_match_id,),
                ).fetchall()
                requested = {r["requested_by_player_id"] for r in req_rows}

                players = {prior["player_one_id"], prior["player_two_id"]}
                if requested == players:
                    new_match_id = self._create_match_locked(
                        conn,
                        mode=str(prior["mode"]),
                        player_one_id=str(prior["player_two_id"]),
                        player_two_id=str(prior["player_one_id"]),
                    )
                    conn.execute(
                        "DELETE FROM rematch_requests WHERE prior_match_id = ?",
                        (prior_match_id,),
                    )
                    return {
                        "status": "accepted",
                        "new_match_id": new_match_id,
                    }

                return {
                    "status": "pending",
                    "new_match_id": None,
                }

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

    def record_bot_decisions_batch(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        now = _utc_now_iso()
        batch = []
        for row in rows:
            batch.append(
                (
                    row.get("event_id") or _new_id("bot"),
                    row.get("match_id"),
                    row["phase"],
                    int(row["ai_level"]),
                    row["state_hash"],
                    json.dumps(row.get("candidates", []), separators=(",", ":")),
                    row["selected_action"],
                    row.get("expected_value"),
                    row.get("created_at") or now,
                )
            )
        with self._connection() as conn:
            conn.executemany(
                """
                INSERT INTO bot_telemetry (
                    event_id, match_id, phase, ai_level, state_hash,
                    candidate_json, selected_action, expected_value, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                batch,
            )
        return len(batch)
