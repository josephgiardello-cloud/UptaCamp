from __future__ import annotations

from cards import Card
from cribbage_engine import CribbageEngine


def test_start_new_game_initializes_orchestrator_state():
    engine = CribbageEngine()

    state = engine.start_new_game(player_name="You", opponent_type="Bert")

    assert state.phase == "discard"
    assert engine.current_phase == "discard"
    assert engine.players == ["You", "Bert"]
    assert len(state.player_hand) == 6
    assert len(state.ai_hand) == 6
    assert len(state.stock_labels) == 40


def test_get_valid_moves_in_discard_returns_two_card_combos():
    engine = CribbageEngine()
    engine.start_new_game()

    moves = engine.get_valid_moves()

    assert len(moves) == 15
    assert all(len(pair) == 2 for pair in moves)


def test_process_discard_moves_to_pegging_and_sets_crib_and_starter():
    engine = CribbageEngine()
    engine.start_new_game()

    ok = engine.process_discard([0, 1])

    assert ok is True
    assert engine.state.phase == "pegging"
    assert engine.current_phase == "pegging"
    assert len(engine.state.player_kept) == 4
    assert len(engine.state.ai_kept) == 4
    assert len(engine.state.crib) == 4
    assert engine.state.starter_card is not None


def test_process_pegging_play_accepts_index_and_scores():
    engine = CribbageEngine()
    engine.start_new_game()

    engine.state.phase = "pegging"
    engine.current_phase = "pegging"
    engine.state.player_turn = 0
    engine.state.player_hand = [Card("5", "Hearts")]
    engine.state.ai_hand = [Card("K", "Clubs")]
    engine.state.pegging_pile = [Card("10", "Diamonds")]

    result = engine.process_pegging_play(0)

    assert result["ok"] is True
    assert result["points"] >= 2
    assert engine.state.scores[0] >= 2


def test_end_hand_counting_scores_hands_and_transitions_to_end():
    engine = CribbageEngine()
    engine.start_new_game()

    engine.state.player_kept = [
        Card("5", "Hearts"),
        Card("5", "Clubs"),
        Card("6", "Diamonds"),
        Card("7", "Spades"),
    ]
    engine.state.ai_kept = [
        Card("A", "Hearts"),
        Card("2", "Clubs"),
        Card("3", "Diamonds"),
        Card("4", "Spades"),
    ]
    engine.state.crib = [
        Card("9", "Hearts"),
        Card("9", "Clubs"),
        Card("K", "Diamonds"),
        Card("6", "Spades"),
    ]
    engine.state.starter_card = "5_of_spades"
    engine.state.dealer = 1

    result = engine.end_hand_counting()

    assert {"player", "ai", "crib", "player_breakdown", "ai_breakdown", "crib_breakdown"} <= set(result)
    assert engine.state.phase == "end"
    assert engine.current_phase == "end"
    assert isinstance(result["player"], int)
    assert isinstance(result["ai"], int)
    assert isinstance(result["crib"], int)


def test_pegging_go_awards_last_card_point_when_both_pass():
    engine = CribbageEngine()
    engine.start_new_game()

    engine.state.phase = "pegging"
    engine.current_phase = "pegging"
    engine.state.player_turn = 0
    engine.state.player_hand = [Card("K", "Hearts")]
    engine.state.ai_hand = [Card("Q", "Clubs")]
    engine.state.pegging_pile = [Card("10", "Diamonds"), Card("10", "Spades"), Card("10", "Hearts")]
    engine.state.last_pegging_player = 1
    engine.state.scores = [0, 0]

    first = engine.process_pegging_play("go")
    second = engine.process_pegging_play("go")

    assert first["ok"] is True
    assert second["ok"] is True
    assert second["go_completed"] is True
    assert second["points"] == 1
    assert engine.state.scores[1] == 1


def test_start_new_game_seed_is_deterministic():
    engine_a = CribbageEngine(seed=42)
    engine_b = CribbageEngine(seed=42)

    state_a = engine_a.start_new_game(seed=42)
    state_b = engine_b.start_new_game(seed=42)

    assert [str(c) for c in state_a.player_hand] == [str(c) for c in state_b.player_hand]
    assert [str(c) for c in state_a.ai_hand] == [str(c) for c in state_b.ai_hand]
