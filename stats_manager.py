from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from runtime_paths import writable_path

_LEGACY_STATS_PATH = writable_path("player_stats.json")
_PLAYER_STATS_DIR = writable_path("player_profiles")


def _empty_bucket() -> dict[str, Any]:
    return {
        "games_played": 0,
        "wins": 0,
        "losses": 0,
        "win_streak": 0,
        "best_win_streak": 0,
        "skunks_for": 0,
        "skunks_against": 0,
        "hands_as_dealer": 0,
        "hands_as_pone": 0,
        "total_hand_points_as_dealer": 0,
        "total_hand_points_as_pone": 0,
        "total_pegging_points": 0,
        "total_points_scored": 0,
        "high_hand": 0,
        "best_game_score": 0,
        "total_margin_wins": 0,
        "total_margin_losses": 0,
    }


def _default_store() -> dict[str, Any]:
    return {
        "single_player": {},
        "online": {},
        "difficulty_wins": {},
    }


def _player_key(player_name: str) -> str:
    return str(player_name).strip() or "Player"


def _player_slug(player_name: str) -> str:
    key = _player_key(player_name)
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", key).strip("._-")
    return slug or "Player"


def _default_stats_path_for_player(player_name: str) -> Path:
    return _PLAYER_STATS_DIR / f"{_player_slug(player_name)}.json"


def _resolve_stats_path(player_name: str, path: Path | None) -> Path:
    return path or _default_stats_path_for_player(player_name)


def _load_store_from(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _default_store()
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _default_store()

    if not isinstance(loaded, dict):
        return _default_store()

    loaded.setdefault("single_player", {})
    loaded.setdefault("online", {})
    loaded.setdefault("difficulty_wins", {})
    return loaded


def _bootstrap_player_store(player_name: str, stats_path: Path, *, migrate_legacy: bool = True) -> None:
    if stats_path.exists():
        return

    player_key = _player_key(player_name)
    store = _default_store()

    # Migrate legacy per-player progress on first profile creation.
    if migrate_legacy and _LEGACY_STATS_PATH.exists() and stats_path != _LEGACY_STATS_PATH:
        legacy = _load_store_from(_LEGACY_STATS_PATH)
        for mode in ("single_player", "online"):
            src_mode = legacy.get(mode, {})
            if isinstance(src_mode, dict):
                src_bucket = src_mode.get(player_key)
                if isinstance(src_bucket, dict):
                    store[mode][player_key] = dict(src_bucket)

        src_wins = legacy.get("difficulty_wins", {})
        if isinstance(src_wins, dict):
            src_player_wins = src_wins.get(player_key)
            if isinstance(src_player_wins, dict):
                store["difficulty_wins"][player_key] = dict(src_player_wins)

    _save_store(stats_path, store)


def create_player_profile(player_name: str, *, path: Path | None = None) -> Path:
    use_default_path = path is None
    stats_path = _resolve_stats_path(player_name, path)
    _bootstrap_player_store(player_name, stats_path, migrate_legacy=use_default_path)
    store = _load_store(stats_path)
    key = _player_key(player_name)
    _ensure_player(store, key, "single_player")
    _ensure_player(store, key, "online")
    wins_store = store.setdefault("difficulty_wins", {})
    if isinstance(wins_store, dict):
        wins_store.setdefault(key, {})
    _save_store(stats_path, store)
    return stats_path


def _load_store(path: Path) -> dict[str, Any]:
    return _load_store_from(path)


def _save_store(path: Path, store: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(store, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        # Non-fatal: stats persistence should never crash gameplay.
        return


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
    use_default_path = path is None
    stats_path = _resolve_stats_path(player_name, path)
    _bootstrap_player_store(player_name, stats_path, migrate_legacy=use_default_path)
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
    opponent_score: int = 0,
    mode: str = "single_player",
    path: Path | None = None,
) -> None:
    use_default_path = path is None
    stats_path = _resolve_stats_path(player_name, path)
    _bootstrap_player_store(player_name, stats_path, migrate_legacy=use_default_path)
    store = _load_store(stats_path)
    bucket = _ensure_player(store, player_name, mode)

    bucket["games_played"] += 1
    final_score_int = max(0, int(final_score))
    opponent_score_int = max(0, int(opponent_score))
    margin = final_score_int - opponent_score_int

    if won:
        bucket["wins"] += 1
        bucket["win_streak"] += 1
        bucket["best_win_streak"] = max(bucket["best_win_streak"], bucket["win_streak"])
        bucket["total_margin_wins"] += max(0, margin)
    else:
        bucket["losses"] += 1
        bucket["win_streak"] = 0
        bucket["total_margin_losses"] += max(0, abs(margin))

    if skunk_for:
        bucket["skunks_for"] += 1
    if skunk_against:
        bucket["skunks_against"] += 1

    bucket["best_game_score"] = max(bucket["best_game_score"], final_score_int)
    bucket["total_points_scored"] += final_score_int

    _save_store(stats_path, store)


def get_player_profile(
    player_name: str,
    mode: str = "single_player",
    path: Path | None = None,
) -> dict[str, Any]:
    use_default_path = path is None
    stats_path = _resolve_stats_path(player_name, path)
    _bootstrap_player_store(player_name, stats_path, migrate_legacy=use_default_path)
    store = _load_store(stats_path)
    bucket = _ensure_player(store, player_name, mode)

    games = max(0, int(bucket["games_played"]))
    wins = max(0, int(bucket["wins"]))
    losses = max(0, int(bucket["losses"]))
    hands_as_dealer = max(0, int(bucket["hands_as_dealer"]))
    hands_as_pone = max(0, int(bucket["hands_as_pone"]))
    hand_total = hands_as_dealer + hands_as_pone

    avg_dealer = bucket["total_hand_points_as_dealer"] / hands_as_dealer if hands_as_dealer else 0.0
    avg_pone = bucket["total_hand_points_as_pone"] / hands_as_pone if hands_as_pone else 0.0
    avg_pegging = bucket["total_pegging_points"] / hand_total if hand_total else 0.0
    avg_margin_win = (
        max(0, int(bucket["total_margin_wins"])) / wins if wins else 0.0
    )
    avg_margin_loss = (
        max(0, int(bucket["total_margin_losses"])) / losses if losses else 0.0
    )

    return {
        "player_name": player_name,
        "mode": mode,
        "games_played": games,
        "wins": wins,
        "losses": losses,
        "win_pct": (wins / games * 100.0) if games else 0.0,
        "current_win_streak": max(0, int(bucket["win_streak"])),
        "best_win_streak": max(0, int(bucket["best_win_streak"])),
        "skunks_for": max(0, int(bucket["skunks_for"])),
        "skunks_against": max(0, int(bucket["skunks_against"])),
        "hands_as_dealer": hands_as_dealer,
        "hands_as_pone": hands_as_pone,
        "avg_hand_as_dealer": avg_dealer,
        "avg_hand_as_pone": avg_pone,
        "avg_pegging_points": avg_pegging,
        "avg_pegging": avg_pegging,
        "high_hand": max(0, int(bucket["high_hand"])),
        "best_game_score": max(0, int(bucket["best_game_score"])),
        "total_points_scored": max(0, int(bucket["total_points_scored"])),
        "avg_margin_win": avg_margin_win,
        "avg_margin_loss": avg_margin_loss,
    }


def reset_player_stats(
    player_name: str,
    mode: str = "single_player",
    path: Path | None = None,
) -> bool:
    use_default_path = path is None
    stats_path = _resolve_stats_path(player_name, path)
    _bootstrap_player_store(player_name, stats_path, migrate_legacy=use_default_path)
    store = _load_store(stats_path)
    if mode in store and isinstance(store[mode], dict) and player_name in store[mode]:
        store[mode][player_name] = _empty_bucket()
        _save_store(stats_path, store)
        return True
    return False


def get_bert_stats_comment(profile: dict[str, Any]) -> str:
    win_pct = float(profile.get("win_pct", 0.0))
    if win_pct >= 65.0:
        return "You've been haulin' em in wicked good lately, bub."
    if win_pct >= 50.0:
        return "Ayuh, you're holdin your own. Respectable."
    if win_pct >= 35.0:
        return "You're scrapin along. Tide'll turn if you keep at her."
    return "Rough water for ya lately. Keep your hands steady, deah."


def record_difficulty_win(
    player_name: str,
    difficulty_key: str,
    *,
    path: Path | None = None,
) -> None:
    use_default_path = path is None
    stats_path = _resolve_stats_path(player_name, path)
    _bootstrap_player_store(player_name, stats_path, migrate_legacy=use_default_path)
    store = _load_store(stats_path)

    wins_store = store.setdefault("difficulty_wins", {})
    if not isinstance(wins_store, dict):
        wins_store = {}
        store["difficulty_wins"] = wins_store

    player_key = _player_key(player_name)
    player_bucket = wins_store.setdefault(player_key, {})
    if not isinstance(player_bucket, dict):
        player_bucket = {}
        wins_store[player_key] = player_bucket

    key = str(difficulty_key).strip().lower()
    player_bucket[key] = max(0, int(player_bucket.get(key, 0))) + 1
    _save_store(stats_path, store)


def get_difficulty_wins(
    player_name: str,
    difficulty_key: str,
    *,
    path: Path | None = None,
) -> int:
    use_default_path = path is None
    stats_path = _resolve_stats_path(player_name, path)
    _bootstrap_player_store(player_name, stats_path, migrate_legacy=use_default_path)
    store = _load_store(stats_path)
    wins_store = store.get("difficulty_wins", {})
    if not isinstance(wins_store, dict):
        return 0

    player_key = _player_key(player_name)
    player_bucket = wins_store.get(player_key, {})
    if not isinstance(player_bucket, dict):
        return 0

    key = str(difficulty_key).strip().lower()
    return max(0, int(player_bucket.get(key, 0)))


def get_player_records_list(
    *,
    mode: str = "single_player",
    limit: int = 8,
    stats_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Return a sorted list of player records for leaderboard-style UI.

    Each entry contains: player_name, wins, losses, high_hand, best_game_score, games_played.
    """
    records: list[dict[str, Any]] = []
    search_dir = stats_dir or _PLAYER_STATS_DIR
    mode_key = str(mode).strip() or "single_player"

    profile_paths: list[Path] = []
    if search_dir.exists() and search_dir.is_dir():
        try:
            profile_paths = sorted(search_dir.glob("*.json"))
        except OSError:
            profile_paths = []

    # Fallback to legacy monolithic store when no profile files are present.
    if not profile_paths and _LEGACY_STATS_PATH.exists():
        profile_paths = [_LEGACY_STATS_PATH]

    for path in profile_paths:
        store = _load_store_from(path)
        mode_bucket = store.get(mode_key, {})
        if not isinstance(mode_bucket, dict):
            continue

        for player_name, bucket in mode_bucket.items():
            if not isinstance(bucket, dict):
                continue
            wins = max(0, int(bucket.get("wins", 0)))
            losses = max(0, int(bucket.get("losses", 0)))
            high_hand = max(0, int(bucket.get("high_hand", 0)))
            best_game_score = max(0, int(bucket.get("best_game_score", 0)))
            games_played = max(0, int(bucket.get("games_played", wins + losses)))
            records.append(
                {
                    "player_name": str(player_name),
                    "wins": wins,
                    "losses": losses,
                    "high_hand": high_hand,
                    "best_game_score": best_game_score,
                    "games_played": games_played,
                }
            )

    # De-duplicate by player name, keeping best aggregate row encountered.
    dedup: dict[str, dict[str, Any]] = {}
    for row in records:
        name = str(row.get("player_name", "")).strip() or "Player"
        existing = dedup.get(name)
        if existing is None:
            dedup[name] = row
            continue

        current_key = (
            int(row.get("wins", 0)),
            int(row.get("high_hand", 0)),
            int(row.get("best_game_score", 0)),
            -int(row.get("losses", 0)),
            int(row.get("games_played", 0)),
        )
        existing_key = (
            int(existing.get("wins", 0)),
            int(existing.get("high_hand", 0)),
            int(existing.get("best_game_score", 0)),
            -int(existing.get("losses", 0)),
            int(existing.get("games_played", 0)),
        )
        if current_key > existing_key:
            dedup[name] = row

    ordered = sorted(
        dedup.values(),
        key=lambda row: (
            -int(row.get("wins", 0)),
            int(row.get("losses", 0)),
            -int(row.get("high_hand", 0)),
            -int(row.get("best_game_score", 0)),
            str(row.get("player_name", "")).lower(),
        ),
    )
    return ordered[: max(0, int(limit))]
