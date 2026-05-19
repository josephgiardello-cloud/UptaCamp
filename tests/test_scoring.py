from __future__ import annotations

from cards import Card, find_all_runs, score_hand, score_pegging_play


def test_score_29_hand():
    hand = [
        Card("5", "Clubs"),
        Card("5", "Diamonds"),
        Card("5", "Hearts"),
        Card("J", "Spades"),
    ]
    starter = Card("5", "Spades")
    total, _ = score_hand(hand, starter)
    assert total == 29


def test_double_run_scores_with_multiplicity():
    hand = [Card("3", "Clubs"), Card("3", "Hearts"), Card("4", "Diamonds"), Card("5", "Spades")]
    starter = Card("6", "Clubs")
    total, breakdown = score_hand(hand, starter)
    run_points = sum(points for name, _, points in breakdown if name.startswith("Run of"))
    assert run_points == 8
    assert total >= 8


def test_crib_flush_requires_starter_match():
    hand = [Card("2", "Hearts"), Card("4", "Hearts"), Card("6", "Hearts"), Card("8", "Hearts")]
    starter_off_suit = Card("K", "Clubs")
    starter_match = Card("K", "Hearts")

    total_off, _ = score_hand(hand, starter_off_suit, is_crib=True)
    total_on, _ = score_hand(hand, starter_match, is_crib=True)

    assert total_off == 0
    assert total_on >= 5


def test_nobs_scores_one_point():
    hand = [Card("J", "Spades"), Card("4", "Hearts"), Card("6", "Clubs"), Card("8", "Diamonds")]
    starter = Card("K", "Spades")
    total, breakdown = score_hand(hand, starter)

    assert any(name == "Nobs" and points == 1 for name, _, points in breakdown)
    assert total >= 1


def test_pegging_pair_and_15_and_31_scoring():
    assert score_pegging_play(["7_of_hearts", "7_of_clubs"]) == 2
    assert score_pegging_play(["5_of_hearts", "king_of_clubs"]) == 2
    assert (
        score_pegging_play(
            [
                "10_of_hearts",
                "king_of_clubs",
                "ace_of_spades",
                "10_of_diamonds",
            ]
        )
        >= 2
    )


def test_pegging_score_with_new_card_parameter():
    pile = ["4_of_hearts", "5_of_clubs"]
    assert score_pegging_play(pile, "6_of_spades") >= 3


def test_find_all_runs_returns_longest_runs_only():
    cards = [
        Card("3", "Clubs"),
        Card("3", "Diamonds"),
        Card("4", "Hearts"),
        Card("5", "Spades"),
        Card("6", "Clubs"),
    ]
    runs = find_all_runs(cards)
    assert runs
    assert all(run_len == 4 for run_len, _, _ in runs)
    assert sum(mult for _, mult, _ in runs) == 2
