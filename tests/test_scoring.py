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


def test_find_all_runs_includes_multiple_lengths_and_multiplicity():
    cards = [
        Card("3", "Clubs"),
        Card("3", "Diamonds"),
        Card("4", "Hearts"),
        Card("5", "Spades"),
        Card("6", "Clubs"),
    ]
    runs = find_all_runs(cards)
    assert runs
    assert len(runs) == 1
    run_len, multiplicity, run_cards = runs[0]
    assert run_len == 4
    assert multiplicity == 2
    assert sorted(str(card) for card in run_cards) == [
        "3 of Clubs",
        "3 of Diamonds",
        "4 of Hearts",
        "5 of Spades",
        "6 of Clubs",
    ]


def test_score_hand_counts_separated_runs_independently():
    hand = [
        Card("2", "Clubs"),
        Card("3", "Diamonds"),
        Card("4", "Hearts"),
        Card("7", "Spades"),
        Card("8", "Clubs"),
        Card("9", "Diamonds"),
    ]
    starter = Card("K", "Spades")
    total, breakdown = score_hand(hand, starter)

    run_points = sum(points for name, _, points in breakdown if name.startswith("Run of"))
    assert run_points == 6
    assert total >= 6


def test_score_hand_counts_overlapping_run_multiplicity():
    hand = [
        Card("3", "Clubs"),
        Card("3", "Diamonds"),
        Card("4", "Hearts"),
        Card("5", "Spades"),
        Card("6", "Clubs"),
        Card("6", "Diamonds"),
    ]
    starter = Card("A", "Hearts")
    total, breakdown = score_hand(hand, starter)

    run_points = sum(points for name, _, points in breakdown if name.startswith("Run of"))
    pair_points = sum(points for name, _, points in breakdown if name == "Pair")
    assert run_points == 16
    assert pair_points == 4
    assert total >= 20


def test_longest_run_only_no_double_counting_shorter_subruns():
    hand = [
        Card("3", "Clubs"),
        Card("3", "Diamonds"),
        Card("4", "Hearts"),
        Card("5", "Spades"),
        Card("6", "Clubs"),
    ]
    starter = Card("K", "Hearts")
    total, breakdown = score_hand(hand, starter)

    run_points = sum(points for name, _, points in breakdown if name.startswith("Run of"))
    assert run_points == 8
    assert total >= 10


def test_find_all_runs_returns_separate_longest_groups():
    cards = [
        Card("2", "Clubs"),
        Card("3", "Diamonds"),
        Card("4", "Hearts"),
        Card("7", "Spades"),
        Card("8", "Clubs"),
        Card("9", "Diamonds"),
    ]

    runs = find_all_runs(cards)

    assert len(runs) == 2
    assert all(run_len == 3 for run_len, _, _ in runs)
    assert all(multiplicity == 1 for _, multiplicity, _ in runs)
