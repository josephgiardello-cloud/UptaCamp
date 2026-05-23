from __future__ import annotations

from stats_manager import (
    get_bert_stats_comment,
    get_player_records_list,
    get_player_profile,
    record_game_result,
    record_hand_stats,
    reset_player_stats,
)


def test_record_hand_stats_accumulates_values(tmp_path):
    stats_file = tmp_path / "player_stats.json"

    record_hand_stats(
        player_name="Player",
        hand_points=12,
        pegging_points=3,
        as_dealer=True,
        mode="single_player",
        path=stats_file,
    )
    record_hand_stats(
        player_name="Player",
        hand_points=8,
        pegging_points=1,
        as_dealer=False,
        mode="single_player",
        path=stats_file,
    )

    profile = get_player_profile("Player", mode="single_player", path=stats_file)

    assert profile["hands_as_dealer"] == 1
    assert profile["hands_as_pone"] == 1
    assert profile["avg_hand_as_dealer"] == 12.0
    assert profile["avg_hand_as_pone"] == 8.0
    assert profile["avg_pegging_points"] == 2.0
    assert profile["high_hand"] == 12


def test_record_game_result_tracks_wins_losses_and_best_score(tmp_path):
    stats_file = tmp_path / "player_stats.json"

    record_game_result(
        player_name="Player",
        won=True,
        skunk_for=False,
        skunk_against=False,
        final_score=121,
        opponent_score=98,
        mode="single_player",
        path=stats_file,
    )
    record_game_result(
        player_name="Player",
        won=False,
        skunk_for=False,
        skunk_against=True,
        final_score=94,
        opponent_score=121,
        mode="single_player",
        path=stats_file,
    )

    profile = get_player_profile("Player", mode="single_player", path=stats_file)

    assert profile["games_played"] == 2
    assert profile["wins"] == 1
    assert profile["losses"] == 1
    assert profile["skunks_against"] == 1
    assert profile["best_game_score"] == 121
    assert profile["win_pct"] == 50.0
    assert profile["current_win_streak"] == 0
    assert profile["best_win_streak"] == 1
    assert profile["avg_margin_win"] == 23.0


def test_record_game_result_backward_compatible_without_opponent_score(tmp_path):
    stats_file = tmp_path / "player_stats.json"

    record_game_result(
        player_name="Player",
        won=True,
        skunk_for=False,
        skunk_against=False,
        final_score=121,
        mode="single_player",
        path=stats_file,
    )

    profile = get_player_profile("Player", mode="single_player", path=stats_file)
    assert profile["games_played"] == 1
    assert profile["wins"] == 1


def test_reset_player_stats_resets_existing_bucket(tmp_path):
    stats_file = tmp_path / "player_stats.json"

    record_game_result(
        player_name="Player",
        won=True,
        skunk_for=True,
        skunk_against=False,
        final_score=121,
        opponent_score=80,
        mode="single_player",
        path=stats_file,
    )

    assert reset_player_stats("Player", mode="single_player", path=stats_file) is True
    profile = get_player_profile("Player", mode="single_player", path=stats_file)
    assert profile["games_played"] == 0
    assert profile["wins"] == 0
    assert profile["skunks_for"] == 0


def test_get_bert_stats_comment_bands() -> None:
    assert "wicked good" in get_bert_stats_comment({"win_pct": 70.0}).lower()
    assert "holdin" in get_bert_stats_comment({"win_pct": 52.0}).lower()
    assert "scrapin" in get_bert_stats_comment({"win_pct": 40.0}).lower()
    assert "rough water" in get_bert_stats_comment({"win_pct": 20.0}).lower()


def test_get_player_records_list_returns_wins_losses_best_hand_sorted(tmp_path):
    # Create two profiles with different outcomes.
    for _ in range(3):
        record_game_result(
            player_name="Alice",
            won=True,
            skunk_for=False,
            skunk_against=False,
            final_score=121,
            opponent_score=95,
            mode="single_player",
            path=tmp_path / "Alice.json",
        )
    record_hand_stats(
        player_name="Alice",
        hand_points=14,
        pegging_points=2,
        as_dealer=True,
        mode="single_player",
        path=tmp_path / "Alice.json",
    )

    for _ in range(2):
        record_game_result(
            player_name="Bob",
            won=True,
            skunk_for=False,
            skunk_against=False,
            final_score=121,
            opponent_score=110,
            mode="single_player",
            path=tmp_path / "Bob.json",
        )
    for _ in range(3):
        record_game_result(
            player_name="Bob",
            won=False,
            skunk_for=False,
            skunk_against=False,
            final_score=98,
            opponent_score=121,
            mode="single_player",
            path=tmp_path / "Bob.json",
        )
    record_hand_stats(
        player_name="Bob",
        hand_points=9,
        pegging_points=1,
        as_dealer=False,
        mode="single_player",
        path=tmp_path / "Bob.json",
    )

    rows = get_player_records_list(mode="single_player", stats_dir=tmp_path)

    assert len(rows) == 2
    assert rows[0]["player_name"] == "Alice"
    assert rows[0]["wins"] == 3
    assert rows[0]["losses"] == 0
    assert rows[0]["high_hand"] == 14
    assert rows[1]["player_name"] == "Bob"
    assert rows[1]["wins"] == 2
    assert rows[1]["losses"] == 3
    assert rows[1]["high_hand"] == 9
