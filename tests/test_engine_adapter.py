from types import SimpleNamespace

from adapter import EngineAdapter
from engine import CribbageEngine
from phase_states import PhaseStateMachine


def test_engine_adapter_sync_round_trip():
    engine = CribbageEngine()
    legacy = SimpleNamespace(
        game_phase="discard",
        dealer=1,
        player_scores=[12, 15],
        player1_hand=["p1"],
        player2_hand=["p2"],
        crib=["c1"],
        pegging_pile=["peg1"],
        player1_kept=["k1"],
        player2_kept=["k2"],
        starter_card="ace_of_spades",
        player_turn=0,
        pegging_passes=[False, True],
        last_pegging_player=1,
        message="hello",
        dad_ai_level=3,
        _stock_labels=["2_of_hearts"],
    )

    adapter = EngineAdapter(engine, legacy)
    adapter.update_engine_from_globals()

    assert engine.state.phase == "discard"
    assert engine.state.scores == [12, 15]
    assert engine.state.dad_ai_level == 3

    engine.state.message = "updated"
    engine.state.phase = "pegging"
    engine.state.scores = [20, 21]
    adapter.update_globals_from_engine()

    assert legacy.message == "updated"
    assert legacy.game_phase == "pegging"
    assert legacy.player_scores == [20, 21]


def test_phase_state_machine_tracks_engine_phase():
    engine = CribbageEngine()
    sm = PhaseStateMachine(engine)

    engine.state.phase = "intro"
    assert sm.current.phase_name == "intro"

    engine.state.phase = "discard"
    assert sm.current.phase_name == "discard"
