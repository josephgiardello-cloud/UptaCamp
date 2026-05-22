from types import SimpleNamespace

import cards as cards_mod
from engine import CribbageEngine


def _make_cards(labels):
    return [SimpleNamespace(label=label) for label in labels]


def test_discard_phase_transitions_to_pegging(monkeypatch):
    engine = CribbageEngine()

    p1_labels = [
        "ace_of_spades",
        "2_of_spades",
        "3_of_spades",
        "4_of_spades",
        "5_of_spades",
        "6_of_spades",
    ]
    p2_labels = [
        "ace_of_hearts",
        "2_of_hearts",
        "3_of_hearts",
        "4_of_hearts",
        "5_of_hearts",
        "6_of_hearts",
    ]

    engine.start_new_game(
        player_hand=_make_cards(p1_labels),
        ai_hand=_make_cards(p2_labels),
        stock_labels=["7_of_clubs"],
        dealer=0,
    )
    engine.state.last_pegging_player = 1

    monkeypatch.setattr(engine, "ai_discard", lambda strategy=None: [0, 1])

    engine.handle_discard([0, 1])

    assert engine.state.phase == "pegging"
    assert len(engine.state.player_hand) == 4
    assert len(engine.state.ai_hand) == 4
    assert len(engine.state.crib) == 4
    assert engine.state.starter_card == "7_of_clubs"
    assert engine.state.player_turn == 1
    assert engine.state.pegging_passes == [False, False]
    assert engine.state.last_pegging_player is None


def test_finalize_pegging_moves_to_counting_with_last_card_point():
    engine = CribbageEngine()
    engine.state.phase = "pegging"
    engine.state.player_hand = []
    engine.state.ai_hand = []
    engine.state.pegging_pile = [
        SimpleNamespace(label="10_of_clubs"),
        SimpleNamespace(label="9_of_hearts"),
    ]
    engine.state.scores = [0, 0]
    engine.state.last_pegging_player = 0

    changed = engine.finalize_pegging_if_complete(
        lambda: cards_mod.pegging_total(engine.state.pegging_pile)
    )

    assert changed is True
    assert engine.state.phase == "counting"
    assert engine.state.scores[0] == 1
    assert "Counting hands" in engine.state.message


def test_handle_counting_moves_to_end_when_no_winner():
    engine = CribbageEngine()
    engine.state.phase = "counting"
    engine.state.scores = [10, 12]
    engine.state.dealer = 1

    engine.state.player_kept = _make_cards([
        "2_of_clubs", "3_of_diamonds", "4_of_hearts", "5_of_spades"
    ])
    engine.state.ai_kept = _make_cards([
        "6_of_clubs", "7_of_diamonds", "8_of_hearts", "9_of_spades"
    ])
    engine.state.crib = _make_cards([
        "ace_of_clubs", "2_of_hearts", "3_of_spades", "4_of_diamonds"
    ])
    engine.state.starter_card = "5_of_clubs"

    result = engine.count_hands(cards_mod.label_to_card)

    assert result["player"] >= 0
    assert result["ai"] >= 0
    assert result["crib"] >= 0
    assert engine.state.counting_resolved is True
    assert engine.state.counting_next_phase in {"end", "game_over"}
