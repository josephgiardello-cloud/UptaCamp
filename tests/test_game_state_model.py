from __future__ import annotations

from game_state import GameState


def test_game_state_has_engine_and_classic_fields():
    state = GameState()

    assert state.phase == "intro"
    assert state.scores == [0, 0]
    assert state.player_hand == []
    assert state.ai_hand == []
    assert state.crib == []
    assert state.pegging_pile == []
    assert state.player_kept == []
    assert state.ai_kept == []
    assert state.pegging_passes == [False, False]
    assert state.stock_labels == []
    assert state.dad_ai_level == 2
    assert state.last_counting_result == {}
    assert state.last_counting_breakdown == {}
    assert state.counting_resolved is False
    assert state.counting_next_phase == "end"
