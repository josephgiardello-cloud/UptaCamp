from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DEFAULT_STATS_PATH = Path(__file__).resolve().parent / "player_stats.json"


def _empty_bucket() -> dict[str, Any]:
    return {
        "games_played": 0,
        "wins": 0,
        "losses": 0,
        "skunks_for": 0,
        "skunks_against": 0,
        "hands_as_dealer": 0,
        "hands_as_pone": 0,
        "total_hand_points_as_dealer": 0,
        "total_hand_points_as_pone": 0,
        "total_pegging_points": 0,
        "high_hand": 0,
        "best_game_score": 0,
    }


def _load_store(path: Path) -> dict[str, Any]:
    default_store: dict[str, Any] = {"single_player": {}, "online": {}}
    if not path.exists():
        return default_store
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default_store

    if not isinstance(loaded, dict):
        return default_store

    loaded.setdefault("single_player", {})
    loaded.setdefault("online", {})
    return loaded


def _save_store(path: Path, store: dict[str, Any]) -> None:
    path.write_text(json.dumps(store, indent=2, sort_keys=True), encoding="utf-8")


def _ensure_player(store: dict[str, Any], player_name: str, mode: str) -> dict[str, Any]:
    if mode not in store:
        store[mode] = {}
    if not isinstance(store[mode], dict):
        store[mode] = {}

    bucket = store[mode].setdefault(player_name, _empty_bucket())
    if not isinstance(bucket, dict):
        bucket = _empty_bucket()

    bucket_dict: dict[str, Any] = {}
    for key, value in bucket.items():
        bucket_dict[str(key)] = value
    store[mode][player_name] = bucket_dict

    for key, value in _empty_bucket().items():
        bucket_dict.setdefault(key, value)
    return bucket_dict


def record_hand_stats(
    player_name: str,
    hand_points: int,
    pegging_points: int,
    as_dealer: bool,
    mode: str = "single_player",
    path: Path | None = None,
) -> None:
    stats_path = path or _DEFAULT_STATS_PATH
    store = _load_store(stats_path)
    bucket = _ensure_player(store, player_name, mode)

    if as_dealer:
        bucket["hands_as_dealer"] += 1
        bucket["total_hand_points_as_dealer"] += max(0, int(hand_points))
    else:
        bucket["hands_as_pone"] += 1
        bucket["total_hand_points_as_pone"] += max(0, int(hand_points))

    bucket["total_pegging_points"] += max(0, int(pegging_points))
    bucket["high_hand"] = max(bucket["high_hand"], max(0, int(hand_points)))

    _save_store(stats_path, store)


def record_game_result(
    player_name: str,
    won: bool,
    skunk_for: bool,
    skunk_against: bool,
    final_score: int,
    mode: str = "single_player",
    path: Path | None = None,
) -> None:
    stats_path = path or _DEFAULT_STATS_PATH
    store = _load_store(stats_path)
    bucket = _ensure_player(store, player_name, mode)

    bucket["games_played"] += 1
    if won:
        bucket["wins"] += 1
    else:
        bucket["losses"] += 1

    if skunk_for:
        bucket["skunks_for"] += 1
    if skunk_against:
        bucket["skunks_against"] += 1

    bucket["best_game_score"] = max(bucket["best_game_score"], max(0, int(final_score)))

    _save_store(stats_path, store)


def get_player_profile(
    player_name: str,
    mode: str = "single_player",
    path: Path | None = None,
) -> dict[str, Any]:
    stats_path = path or _DEFAULT_STATS_PATH
    store = _load_store(stats_path)
    bucket = _ensure_player(store, player_name, mode)

    games = max(0, int(bucket["games_played"]))
    wins = max(0, int(bucket["wins"]))
    hands_as_dealer = max(0, int(bucket["hands_as_dealer"]))
    hands_as_pone = max(0, int(bucket["hands_as_pone"]))
    hand_total = hands_as_dealer + hands_as_pone

    avg_dealer = bucket["total_hand_points_as_dealer"] / hands_as_dealer if hands_as_dealer else 0.0
    avg_pone = bucket["total_hand_points_as_pone"] / hands_as_pone if hands_as_pone else 0.0
    avg_pegging = bucket["total_pegging_points"] / hand_total if hand_total else 0.0

    return {
        "player_name": player_name,
        "mode": mode,
        "games_played": games,
        "wins": wins,
        "losses": max(0, int(bucket["losses"])),
        "win_pct": (wins / games * 100.0) if games else 0.0,
        "skunks_for": max(0, int(bucket["skunks_for"])),
        "skunks_against": max(0, int(bucket["skunks_against"])),
        "hands_as_dealer": hands_as_dealer,
        "hands_as_pone": hands_as_pone,
        "avg_hand_as_dealer": avg_dealer,
        "avg_hand_as_pone": avg_pone,
        "avg_pegging_points": avg_pegging,
        "high_hand": max(0, int(bucket["high_hand"])),
        "best_game_score": max(0, int(bucket["best_game_score"])),
    }
