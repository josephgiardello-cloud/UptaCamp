from engine import CribbageEngine
from phase_states import PhaseStateMachine


def test_phase_state_machine_tracks_engine_phase():
    engine = CribbageEngine()
    sm = PhaseStateMachine(engine)

    engine.state.phase = "intro"
    assert sm.current.phase_name == "intro"

    engine.state.phase = "discard"
    assert sm.current.phase_name == "discard"
