from __future__ import annotations

from states.online_match import OnlineMatchState


def test_pick_discard_indices_prefers_higher_value_cards():
    indices = OnlineMatchState._pick_discard_indices(
        ["2_of_hearts", "king_of_clubs", "5_of_spades", "10_of_diamonds"]
    )
    assert indices == [3, 1]


def test_pick_pegging_card_chooses_legal_card():
    card = OnlineMatchState._pick_pegging_card(
        ["10_of_hearts", "6_of_clubs", "5_of_spades"],
        running_total=9,
    )
    assert card == "5_of_spades"


def test_pick_pegging_card_falls_back_when_no_legal_card():
    card = OnlineMatchState._pick_pegging_card(
        ["10_of_hearts", "10_of_clubs", "10_of_spades"],
        running_total=31,
    )
    assert card is None
