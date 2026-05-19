from __future__ import annotations

from game_state import GameState


class _PhaseA:
    phase_name = "intro"

    def __init__(self):
        self.entered = False
        self.exited = False

    def enter(self, state, ctx):
        self.entered = True
        state.message = "A"

    def exit(self, state, ctx):
        self.exited = True


class _PhaseB:
    phase_name = "pegging"

    def __init__(self):
        self.entered = False

    def enter(self, state, ctx):
        self.entered = True
        state.message = "B"


class _Context:
    pass


def test_transition_to_sets_current_phase_and_phase_name():
    state = GameState()

    state.transition_to(_PhaseA, _Context())

    assert isinstance(state.current_phase, _PhaseA)
    assert state.phase_name == "_PhaseA"
    assert state.phase == "intro"
    assert state.message == "A"


def test_transition_to_calls_exit_on_previous_phase():
    state = GameState()
    ctx = _Context()

    state.transition_to(_PhaseA, ctx)
    previous = state.current_phase
    state.transition_to(_PhaseB, ctx)

    assert previous.exited is True
    assert isinstance(state.current_phase, _PhaseB)
    assert state.phase == "pegging"
    assert state.message == "B"
