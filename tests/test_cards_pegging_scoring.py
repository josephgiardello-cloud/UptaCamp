from __future__ import annotations

import cards


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
