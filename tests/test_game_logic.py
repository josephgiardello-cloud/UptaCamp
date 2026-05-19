"""Mechanism tests for cribbage scoring and turn flow."""

from types import SimpleNamespace

import cards as cards_mod
import cribbage_pygame as game


def _mk(rank: str, suit: str = "Hearts") -> cards_mod.Card:
    return cards_mod.Card(rank, suit)


def _peg(label: str):
    return SimpleNamespace(label=label)


def test_parse_label_supports_expected_formats():
    assert game._parse_label("ace of spades") == ("ace", "spades")
    assert game._parse_label("ace_of_spades") == ("ace", "spades")
    assert game._parse_label("ace_spades") == ("ace", "spades")


def test_pegging_score_15_and_31_from_pile_argument():
    pile_15 = [_peg("10_of_hearts"), _peg("5_of_spades")]
    pile_31 = [_peg("10_of_hearts"), _peg("10_of_spades"), _peg("10_of_clubs"), _peg("A_of_diamonds")]
    assert game._score_pegging_play(pile_15) == 2
    assert game._score_pegging_play(pile_31) == 2


def test_pegging_pair_and_run_scoring():
    pair_pile = [_peg("7_of_hearts"), _peg("7_of_spades")]
    run_pile = [_peg("7_of_hearts"), _peg("8_of_clubs"), _peg("9_of_spades")]
    assert game._score_pegging_play(pair_pile) == 2
    assert game._score_pegging_play(run_pile) == 3


def test_crib_flush_requires_starter_match():
    hand = [_mk("2", "Hearts"), _mk("5", "Hearts"), _mk("9", "Hearts"), _mk("K", "Hearts")]
    non_matching = _mk("A", "Spades")
    matching = _mk("A", "Hearts")

    total_non_crib, _ = cards_mod.score_hand(hand, non_matching, is_crib=False)
    total_crib, _ = cards_mod.score_hand(hand, non_matching, is_crib=True)
    total_crib_match, _ = cards_mod.score_hand(hand, matching, is_crib=True)

    # Non-crib gets 4-card flush.
    assert total_non_crib >= 4
    # Crib gets no flush unless starter matches.
    assert total_crib < total_non_crib
    assert total_crib_match >= total_crib + 5


def test_double_run_scoring_with_pair():
    # 3,3,4,5,6 should score double run of 4 (8) plus pair (2) = 10.
    hand = [_mk("3", "Hearts"), _mk("3", "Spades"), _mk("4", "Clubs"), _mk("5", "Diamonds")]
    starter = _mk("6", "Hearts")
    total, _ = cards_mod.score_hand(hand, starter, is_crib=False)
    assert total >= 10


def test_nobs_scores_one_for_jack_matching_starter_suit():
    hand = [_mk("J", "Hearts"), _mk("4", "Clubs"), _mk("7", "Diamonds"), _mk("9", "Spades")]
    starter = _mk("A", "Hearts")
    total, breakdown = cards_mod.score_hand(hand, starter, is_crib=False)
    assert any(item[0] == "Nobs" and item[2] == 1 for item in breakdown)
    assert total >= 1


def test_nobs_handles_rank_name_variant_jack():
    hand = [_mk("jack", "Spades"), _mk("4", "Clubs"), _mk("7", "Diamonds"), _mk("9", "Hearts")]
    starter = _mk("K", "Spades")
    total, breakdown = cards_mod.score_hand(hand, starter, is_crib=False)
    assert any(item[0] == "Nobs" and item[2] == 1 for item in breakdown)
    assert total >= 1


def test_pairs_treat_rank_variants_as_same_rank():
    cards = [_mk("J", "Hearts"), _mk("jack", "Spades"), _mk("4", "Clubs"), _mk("9", "Diamonds"), _mk("2", "Hearts")]
    breakdown = cards_mod.score_pairs(cards)
    assert sum(item[2] for item in breakdown) >= 2


def test_handle_go_awards_last_card_and_resets_count(monkeypatch):
    game.pegging_pile[:] = [_peg("10_of_hearts"), _peg("5_of_clubs")]
    game.pegging_passes[:] = [True, False]
    game.last_pegging_player = 0
    game.player_scores[:] = [0, 0]
    game.player_turn = 1

    game._handle_go(1)

    assert game.player_scores[0] == 1
    assert game.pegging_pile == []
    assert game.pegging_passes == [False, False]
    assert game.player_turn == 1


def test_check_for_winner_player_and_tie():
    game.player_scores[:] = [121, 100]
    assert game._check_for_winner() == 0

    game.player_scores[:] = [121, 121]
    assert game._check_for_winner() == -1
