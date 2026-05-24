from __future__ import annotations

import ai_strategy
from engine import CribbageEngine


class _LabeledCard:
    def __init__(self, label: str):
        self.label = label


def _label_to_model(label: str):
    from cards import label_to_card

    return label_to_card(label)


def test_start_new_game_initializes_discard_phase():
    engine = CribbageEngine()
    engine.start_new_game(
        player_hand=[_LabeledCard("5_of_hearts")] * 6,
        ai_hand=[_LabeledCard("6_of_clubs")] * 6,
        stock_labels=["ace_of_spades"],
        dealer=1,
    )

    assert engine.state.phase == "discard"
    assert engine.state.scores == [0, 0]
    assert len(engine.state.player_hand) == 6
    assert len(engine.state.ai_hand) == 6


def test_handle_discard_moves_to_pegging_and_sets_starter():
    engine = CribbageEngine()
    player = [
        _LabeledCard(lbl)
        for lbl in [
            "5_of_hearts",
            "6_of_hearts",
            "7_of_hearts",
            "8_of_hearts",
            "9_of_hearts",
            "10_of_hearts",
        ]
    ]
    ai = [
        _LabeledCard(lbl)
        for lbl in [
            "ace_of_clubs",
            "2_of_clubs",
            "3_of_clubs",
            "4_of_clubs",
            "5_of_clubs",
            "6_of_clubs",
        ]
    ]

    engine.start_new_game(player, ai, ["jack_of_spades"], dealer=0)
    engine.handle_discard([0, 1])

    assert engine.state.phase == "pegging"
    assert engine.state.starter_card == "jack_of_spades"
    assert len(engine.state.crib) == 4
    assert len(engine.state.player_kept) == 4
    assert len(engine.state.ai_kept) == 4


def test_count_hands_returns_breakdowns():
    engine = CribbageEngine()
    engine.state.player_kept = [
        _LabeledCard("5_of_hearts"),
        _LabeledCard("5_of_clubs"),
        _LabeledCard("6_of_diamonds"),
        _LabeledCard("7_of_spades"),
    ]
    engine.state.ai_kept = [
        _LabeledCard("ace_of_hearts"),
        _LabeledCard("2_of_clubs"),
        _LabeledCard("3_of_diamonds"),
        _LabeledCard("4_of_spades"),
    ]
    engine.state.crib = [
        _LabeledCard("9_of_hearts"),
        _LabeledCard("9_of_clubs"),
        _LabeledCard("king_of_diamonds"),
        _LabeledCard("6_of_spades"),
    ]
    engine.state.starter_card = "5_of_spades"
    engine.state.dealer = 1

    result = engine.count_hands(_label_to_model)

    assert {"player", "ai", "crib", "player_breakdown", "ai_breakdown", "crib_breakdown"} <= set(
        result
    )
    assert isinstance(result["player"], int)
    assert isinstance(result["ai"], int)
    assert isinstance(result["crib"], int)


def test_count_hands_stops_after_first_player_reaches_121():
    engine = CribbageEngine()
    engine.state.scores = [120, 10]
    engine.state.player_kept = [
        _LabeledCard("J_of_spades"),
        _LabeledCard("2_of_clubs"),
        _LabeledCard("7_of_diamonds"),
        _LabeledCard("K_of_hearts"),
    ]
    engine.state.ai_kept = [
        _LabeledCard("5_of_clubs"),
        _LabeledCard("5_of_diamonds"),
        _LabeledCard("5_of_hearts"),
        _LabeledCard("K_of_spades"),
    ]
    engine.state.crib = [
        _LabeledCard("6_of_clubs"),
        _LabeledCard("7_of_diamonds"),
        _LabeledCard("8_of_hearts"),
        _LabeledCard("9_of_spades"),
    ]
    engine.state.starter_card = "A_of_spades"
    engine.state.dealer = 1

    result = engine.count_hands(_label_to_model)

    assert engine.state.phase == "game_over"
    assert engine.state.winner == 0
    assert engine.state.scores[0] == 121
    assert engine.state.scores[1] == 10
    assert result["player"] == 1
    assert result["ai"] == 0
    assert result["crib"] == 0


def test_start_next_round_flips_dealer_and_sets_turn():
    engine = CribbageEngine()
    engine.state.dealer = 0
    engine.start_next_round(
        player_hand=[_LabeledCard("5_of_hearts")] * 6,
        ai_hand=[_LabeledCard("6_of_clubs")] * 6,
        stock_labels=["ace_of_spades"],
    )

    assert engine.state.phase == "discard"
    assert engine.state.dealer == 1
    assert engine.state.player_turn == 0


def test_play_pegging_card_clears_on_31():
    engine = CribbageEngine()
    engine.state.player_hand = [_LabeledCard("ace_of_spades")]
    engine.state.ai_hand = []
    engine.state.pegging_pile = [
        _LabeledCard("10_of_hearts"),
        _LabeledCard("king_of_clubs"),
        _LabeledCard("10_of_diamonds"),
    ]
    engine.state.player_turn = 0

    points = engine.play_pegging_card(
        player_idx=0,
        card_index=0,
        score_pegging_play=lambda pile: 2,
        value_for_15=lambda rank: 1 if rank == "ace" else 10,
        parse_label=lambda label: label.split("_of_", 1),
    )

    assert points == 2
    assert engine.state.pegging_pile == []
    assert "31" in engine.state.message


def test_play_pegging_card_rejects_over_31():
    engine = CribbageEngine()
    engine.state.player_hand = [_LabeledCard("2_of_spades")]
    engine.state.ai_hand = []
    engine.state.pegging_pile = [
        _LabeledCard("10_of_hearts"),
        _LabeledCard("king_of_clubs"),
        _LabeledCard("10_of_diamonds"),
    ]
    engine.state.player_turn = 0

    points = engine.play_pegging_card(
        player_idx=0,
        card_index=0,
        score_pegging_play=lambda pile: 2,
        value_for_15=lambda rank: 2 if rank == "2" else 10,
        parse_label=lambda label: label.split("_of_", 1),
    )

    assert points == 0
    assert len(engine.state.player_hand) == 1
    assert len(engine.state.pegging_pile) == 3


def test_pass_pegging_turn_awards_last_card_and_resets_count():
    engine = CribbageEngine()
    engine.state.phase = "pegging"
    engine.state.pegging_pile = [_LabeledCard("5_of_hearts")]
    engine.state.pegging_passes = [False, False]
    engine.state.last_pegging_player = 0
    engine.state.player_turn = 1

    first = engine.pass_pegging_turn(1)
    second = engine.pass_pegging_turn(0)

    assert first["ok"] is True
    assert second["ok"] is True
    assert second["go_completed"] is True
    assert engine.state.scores[0] == 1
    assert engine.state.pegging_pile == []
    assert engine.state.pegging_passes == [False, False]
    assert engine.state.player_turn == 1


def test_finalize_pegging_if_complete_awards_last_card_point():
    engine = CribbageEngine()
    engine.state.player_hand = []
    engine.state.ai_hand = []
    engine.state.pegging_pile = [_LabeledCard("5_of_hearts")]
    engine.state.last_pegging_player = 0

    changed = engine.finalize_pegging_if_complete(lambda: 20)

    assert changed is True
    assert engine.state.phase == "counting"
    assert engine.state.scores[0] == 1


def test_ai_strategy_delegates(monkeypatch):
    engine = CribbageEngine()
    engine.state.ai_hand = [_LabeledCard("5_of_hearts"), _LabeledCard("6_of_hearts")]

    def _fake_discard(**kwargs):
        assert kwargs["dad_ai_level"] == engine.state.dad_ai_level
        assert kwargs["game_state"] is engine.state
        return [0, 1]

    def _fake_pegging(**kwargs):
        assert "hand_labels" in kwargs
        assert kwargs["game_state"] is engine.state
        return 0

    monkeypatch.setattr(ai_strategy, "choose_discard_indices", _fake_discard)
    monkeypatch.setattr(ai_strategy, "choose_pegging_index", _fake_pegging)

    assert engine.ai_discard() == [0, 1]
    assert (
        engine.ai_pegging_move(
            current_total=10,
            value_for_15=lambda rank: 10,
            parse_label=lambda label: label.split("_of_", 1),
            score_pegging_play=lambda pile: 0,
            label_card_factory=lambda label: _LabeledCard(label),
        )
        == 0
    )


def test_ai_discard_allows_strategy_injection():
    engine = CribbageEngine()
    engine.state.ai_hand = [_LabeledCard("5_of_hearts"), _LabeledCard("6_of_hearts")]

    class _InjectedStrategy:
        @staticmethod
        def choose_discard_indices(**kwargs):
            assert kwargs["dad_labels"] == ["5_of_hearts", "6_of_hearts"]
            return [1, 0]

    assert engine.ai_discard(strategy=_InjectedStrategy) == [1, 0]


def test_debug_validation_runs_after_state_mutation(monkeypatch):
    engine = CribbageEngine(debug_validate=True)
    calls = {"count": 0}

    monkeypatch.setattr(
        engine,
        "_validate_state",
        lambda: calls.__setitem__("count", calls["count"] + 1),
    )

    engine.start_new_game(
        player_hand=[_LabeledCard("5_of_hearts")] * 6,
        ai_hand=[_LabeledCard("6_of_clubs")] * 6,
        stock_labels=["ace_of_spades"],
        dealer=1,
    )

    assert calls["count"] == 1


def test_level5_count_hands_updates_and_saves_barnabas(monkeypatch):
    engine = CribbageEngine()
    engine.state.dad_ai_level = 5
    engine.state.player_kept = [
        _LabeledCard("5_of_hearts"),
        _LabeledCard("5_of_clubs"),
        _LabeledCard("6_of_diamonds"),
        _LabeledCard("7_of_spades"),
    ]
    engine.state.ai_kept = [
        _LabeledCard("ace_of_hearts"),
        _LabeledCard("2_of_clubs"),
        _LabeledCard("3_of_diamonds"),
        _LabeledCard("4_of_spades"),
    ]
    engine.state.crib = [
        _LabeledCard("9_of_hearts"),
        _LabeledCard("9_of_clubs"),
        _LabeledCard("king_of_diamonds"),
        _LabeledCard("6_of_spades"),
    ]
    engine.state.starter_card = "5_of_spades"
    engine.state.dealer = 1

    called = {"update": 0, "save": 0}

    class _FakeBarnabas:
        def end_of_hand_update(self, reward):
            called["update"] += 1
            assert isinstance(reward, float)

    monkeypatch.setattr(ai_strategy, "get_barnabas_agent", lambda: _FakeBarnabas())
    monkeypatch.setattr(ai_strategy, "save_barnabas_agent", lambda: called.__setitem__("save", 1))

    engine.count_hands(_label_to_model)

    assert called["update"] == 1
    assert called["save"] == 1


def test_legacy_level6_count_hands_updates_and_saves_barnabas(monkeypatch):
    engine = CribbageEngine()
    engine.state.dad_ai_level = 6
    engine.state.player_kept = [
        _LabeledCard("5_of_hearts"),
        _LabeledCard("5_of_clubs"),
        _LabeledCard("6_of_diamonds"),
        _LabeledCard("7_of_spades"),
    ]
    engine.state.ai_kept = [
        _LabeledCard("ace_of_hearts"),
        _LabeledCard("2_of_clubs"),
        _LabeledCard("3_of_diamonds"),
        _LabeledCard("4_of_spades"),
    ]
    engine.state.crib = [
        _LabeledCard("9_of_hearts"),
        _LabeledCard("9_of_clubs"),
        _LabeledCard("king_of_diamonds"),
        _LabeledCard("6_of_spades"),
    ]
    engine.state.starter_card = "5_of_spades"
    engine.state.dealer = 1

    called = {"update": 0, "save": 0}

    class _FakeBarnabas:
        def end_of_hand_update(self, reward):
            called["update"] += 1
            assert isinstance(reward, float)

    monkeypatch.setattr(ai_strategy, "get_barnabas_agent", lambda: _FakeBarnabas())
    monkeypatch.setattr(ai_strategy, "save_barnabas_agent", lambda: called.__setitem__("save", 1))

    engine.count_hands(_label_to_model)

    assert called["update"] == 1
    assert called["save"] == 1
