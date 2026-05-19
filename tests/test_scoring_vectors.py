import pytest

import cards as cards_mod


def c(rank: str, suit: str) -> cards_mod.Card:
    return cards_mod.Card(rank, suit)


@pytest.mark.parametrize(
    "hand,starter,is_crib,expected_total,tag",
    [
        # Maximum 29 hand: 5,5,5,J with starter 5 and nobs.
        (
            [c("5", "Clubs"), c("5", "Diamonds"), c("5", "Hearts"), c("J", "Spades")],
            c("5", "Spades"),
            False,
            29,
            "max_29",
        ),
        # Double run of 4 + pair: 3,3,4,5 + 6 => 8 + 2 = 10.
        (
            [c("3", "Hearts"), c("3", "Spades"), c("4", "Clubs"), c("5", "Diamonds")],
            c("6", "Hearts"),
            False,
            14,
            "double_run_4",
        ),
        # Triple run of 3 + three of a kind: 2,3,3,3 + 4 => 9 + 6 = 15.
        (
            [c("2", "Hearts"), c("3", "Spades"), c("3", "Clubs"), c("3", "Diamonds")],
            c("4", "Hearts"),
            False,
            17,
            "triple_run_3",
        ),
        # Non-crib 4-card flush without starter match.
        (
            [c("2", "Hearts"), c("5", "Hearts"), c("9", "Hearts"), c("K", "Hearts")],
            c("A", "Spades"),
            False,
            8,
            "hand_flush_4",
        ),
        # Crib does NOT score 4-card flush.
        (
            [c("2", "Hearts"), c("5", "Hearts"), c("9", "Hearts"), c("K", "Hearts")],
            c("A", "Spades"),
            True,
            4,
            "crib_no_flush_4",
        ),
        # Crib 5-card flush does score.
        (
            [c("2", "Hearts"), c("5", "Hearts"), c("9", "Hearts"), c("K", "Hearts")],
            c("A", "Hearts"),
            True,
            9,
            "crib_flush_5",
        ),
        # Nobs positive.
        (
            [c("J", "Hearts"), c("4", "Clubs"), c("7", "Diamonds"), c("9", "Spades")],
            c("K", "Hearts"),
            False,
            1,
            "nobs_yes",
        ),
        # Nobs negative.
        (
            [c("J", "Clubs"), c("4", "Clubs"), c("7", "Diamonds"), c("9", "Spades")],
            c("K", "Hearts"),
            False,
            0,
            "nobs_no_with_fifteen",
        ),
    ],
)
def test_canonical_scoring_vectors(hand, starter, is_crib, expected_total, tag):
    total, breakdown = cards_mod.score_hand(hand, starter, is_crib=is_crib)
    assert total == expected_total, f"{tag}: expected {expected_total}, got {total}"

    labels = [item[0] for item in breakdown]
    if tag == "hand_flush_4":
        assert "Flush (4)" in labels
    if tag == "crib_no_flush_4":
        assert "Flush (4)" not in labels
        assert "Flush (5 crib)" not in labels
    if tag == "crib_flush_5":
        assert "Flush (5 crib)" in labels
    if tag == "nobs_yes":
        assert "Nobs" in labels
    if tag == "nobs_no_with_fifteen":
        assert "Nobs" not in labels


def test_rank_name_variants_score_equally_for_nobs():
    hand_symbol = [c("J", "Spades"), c("4", "Clubs"), c("7", "Diamonds"), c("9", "Hearts")]
    hand_word = [c("jack", "Spades"), c("4", "Clubs"), c("7", "Diamonds"), c("9", "Hearts")]
    starter = c("K", "Spades")

    total_symbol, _ = cards_mod.score_hand(hand_symbol, starter, is_crib=False)
    total_word, _ = cards_mod.score_hand(hand_word, starter, is_crib=False)

    assert total_symbol == 1
    assert total_word == 1
