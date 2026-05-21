from __future__ import annotations

from engine import CribbageEngine
from phase_states import CountingState, DiscardState, PeggingState


class _CardRef:
    def __init__(self, label: str):
        self.label = label


def test_discard_state_handle_event_applies_engine_discard():
    engine = CribbageEngine()
    engine.start_new_game(
        player_hand=[_CardRef("5_of_hearts")] * 6,
        ai_hand=[_CardRef("6_of_clubs")] * 6,
        stock_labels=["ace_of_spades"],
        dealer=0,
    )

    state = DiscardState()
    transition = state.handle_event(
        {"action": "discard", "selected_indices": [0, 1]},
        engine,
    )

    assert transition == "pegging"
    assert engine.state.phase == "pegging"
    assert len(engine.state.crib) == 4


def test_pegging_state_handle_event_plays_card_and_advances_when_done():
    engine = CribbageEngine()
    engine.state.phase = "pegging"
    engine.state.player_turn = 0
    engine.state.player_hand = [_CardRef("ace_of_spades")]
    engine.state.ai_hand = []
    engine.state.pegging_pile = [_CardRef("10_of_hearts"), _CardRef("king_of_clubs")]

    state = PeggingState()
    transition = state.handle_event({"action": "peg_play", "card_index": 0}, engine)

    assert transition == "counting"
    assert engine.state.phase == "counting"


def test_counting_state_update_counts_and_transitions_to_end():
    engine = CribbageEngine()
    engine.state.phase = "counting"
    engine.state.dealer = 1
    engine.state.player_kept = [
        _CardRef("2_of_clubs"),
        _CardRef("3_of_diamonds"),
        _CardRef("4_of_hearts"),
        _CardRef("5_of_spades"),
    ]
    engine.state.ai_kept = [
        _CardRef("6_of_clubs"),
        _CardRef("7_of_diamonds"),
        _CardRef("8_of_hearts"),
        _CardRef("9_of_spades"),
    ]
    engine.state.crib = [
        _CardRef("ace_of_clubs"),
        _CardRef("2_of_hearts"),
        _CardRef("3_of_spades"),
        _CardRef("4_of_diamonds"),
    ]
    engine.state.starter_card = "5_of_clubs"

    transition = CountingState().update(engine)

    assert transition == "end"
    assert engine.state.phase == "end"
    assert "Round counted:" in engine.state.message


def test_counting_state_update_goes_game_over_on_121():
    engine = CribbageEngine()
    engine.state.phase = "counting"
    engine.state.scores = [120, 10]
    engine.state.player_kept = [
        _CardRef("5_of_clubs"),
        _CardRef("5_of_hearts"),
        _CardRef("5_of_spades"),
        _CardRef("J_of_spades"),
    ]
    engine.state.ai_kept = [
        _CardRef("2_of_clubs"),
        _CardRef("3_of_clubs"),
        _CardRef("4_of_clubs"),
        _CardRef("6_of_clubs"),
    ]
    engine.state.crib = [
        _CardRef("A_of_hearts"),
        _CardRef("2_of_hearts"),
        _CardRef("3_of_hearts"),
        _CardRef("4_of_hearts"),
    ]
    engine.state.starter_card = "5_of_diamonds"

    transition = CountingState().update(engine)

    assert transition == "game_over"
    assert engine.state.phase == "game_over"
    assert engine.state.winner == 0
