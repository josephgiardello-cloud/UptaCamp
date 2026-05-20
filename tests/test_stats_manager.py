from __future__ import annotations

from stats_manager import get_player_profile, record_game_result, record_hand_stats


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
        mode="single_player",
        path=stats_file,
    )
    record_game_result(
        player_name="Player",
        won=False,
        skunk_for=False,
        skunk_against=True,
        final_score=94,
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
