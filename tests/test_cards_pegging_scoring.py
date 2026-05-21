from __future__ import annotations

import cards
from cards import Card


class _Labeled:
    def __init__(self, label: str):
        self.label = label


def test_pegging_total_uses_card_labels():
    pile = [_Labeled("5_of_hearts"), _Labeled("king_of_clubs")]
    assert cards.pegging_total(pile) == 15


def test_score_pegging_play_scores_15_pair_and_run():
    pile_15 = [_Labeled("5_of_hearts"), _Labeled("king_of_clubs")]
    assert cards.score_pegging_play(pile_15) == 2

    pile_pair = [_Labeled("7_of_hearts"), _Labeled("7_of_clubs")]
    assert cards.score_pegging_play(pile_pair) == 2

    pile_run = [_Labeled("4_of_hearts"), _Labeled("5_of_clubs"), _Labeled("6_of_spades")]
    # Run of 3 (3 points) plus total 15 bonus (2 points).
    assert cards.score_pegging_play(pile_run) == 5


def test_score_pegging_play_scores_31():
    pile = [
        _Labeled("10_of_hearts"),
        _Labeled("king_of_clubs"),
        _Labeled("ace_of_spades"),
        _Labeled("10_of_diamonds"),
    ]
    assert cards.pegging_total(pile) == 31
    assert cards.score_pegging_play(pile) >= 2


def test_tricky_double_run_44556_scores_correctly():
    hand = [Card("4", "Hearts"), Card("4", "Spades"), Card("5", "Clubs"), Card("5", "Diamonds")]
    starter = Card("6", "Hearts")
    total, breakdown = cards.score_hand(hand, starter, is_crib=False)

    run_points = sum(points for name, _, points in breakdown if name.startswith("Run of"))
    pair_points = sum(points for name, _, points in breakdown if name == "Pair")
    assert run_points == 12
    assert pair_points == 4
    assert total >= 16


def test_tricky_triple_run_scores_correctly():
    hand = [Card("2", "Hearts"), Card("3", "Spades"), Card("3", "Clubs"), Card("3", "Diamonds")]
    starter = Card("4", "Hearts")
    total, breakdown = cards.score_hand(hand, starter, is_crib=False)

    run_points = sum(points for name, _, points in breakdown if name.startswith("Run of"))
    assert run_points == 9
    assert total >= 15


def test_tricky_flush_hand_and_crib_behavior():
    hand = [Card("2", "Hearts"), Card("5", "Hearts"), Card("9", "Hearts"), Card("K", "Hearts")]
    non_match_starter = Card("A", "Spades")
    match_starter = Card("A", "Hearts")

    hand_total, hand_breakdown = cards.score_hand(hand, non_match_starter, is_crib=False)
    crib_no_total, crib_no_breakdown = cards.score_hand(hand, non_match_starter, is_crib=True)
    crib_yes_total, crib_yes_breakdown = cards.score_hand(hand, match_starter, is_crib=True)

    assert any(name == "Flush (4)" for name, _, _ in hand_breakdown)
    assert not any(name.startswith("Flush") for name, _, _ in crib_no_breakdown)
    assert any(name == "Flush (5 crib)" for name, _, _ in crib_yes_breakdown)
    assert hand_total >= 4
    assert crib_yes_total >= crib_no_total + 5


def test_pegging_mixed_scoring_path_run_then_pair():
    # First play forms a run (4,5,6), next play forms a pair (6,6).
    run_pile = [_Labeled("4_of_hearts"), _Labeled("5_of_clubs"), _Labeled("6_of_spades")]
    pair_pile = [_Labeled("4_of_hearts"), _Labeled("5_of_clubs"), _Labeled("6_of_spades"), _Labeled("6_of_diamonds")]
    assert cards.score_pegging_play(run_pile) >= 3
    assert cards.score_pegging_play(pair_pile) >= 2
