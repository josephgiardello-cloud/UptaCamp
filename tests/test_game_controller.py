from types import SimpleNamespace

import pytest

from src.controllers import GameController


class _LegacyStub:
    def __init__(self, phase: str = "intro"):
        self.calls: list[tuple[str, object]] = []
        self._CLASSIC_SESSION = SimpleNamespace(phase=phase)
        self.game_phase = phase

    def handle_discard(self, event):
        self.calls.append(("discard", event))

    def handle_pegging(self, event, auto_player=False):
        self.calls.append(("pegging", (event, auto_player)))

    def handle_counting(self):
        self.calls.append(("counting", None))

    def _transition_phase(self, phase, force=False):
        self.calls.append(("transition", (phase, force)))
        self._CLASSIC_SESSION.phase = phase
        self.game_phase = phase

    def _check_for_winner(self):
        self.calls.append(("check_winner", None))
        return 1


def test_update_dispatches_pegging_handler_for_pegging_phase():
    legacy = _LegacyStub(phase="pegging")
    controller = GameController(engine=None, legacy_module=legacy)

    controller.update(auto_player=True)

    assert legacy.calls == [("pegging", (None, True))]


def test_update_dispatches_counting_handler_for_counting_phase():
    legacy = _LegacyStub(phase="counting")
    controller = GameController(engine=None, legacy_module=legacy)

    controller.update()

    assert legacy.calls == [("counting", None)]


def test_transition_and_check_for_winner_delegate_to_legacy():
    legacy = _LegacyStub(phase="discard")
    controller = GameController(engine=None, legacy_module=legacy)

    controller.transition_phase("intro")
    winner = controller.check_for_winner()

    assert winner == 1
    assert legacy.calls == [
        ("transition", ("intro", False)),
        ("check_winner", None),
    ]


def test_handle_action_transition_requires_phase():
    legacy = _LegacyStub(phase="discard")
    controller = GameController(engine=None, legacy_module=legacy)

    with pytest.raises(ValueError, match="requires a non-empty 'phase'"):
        controller.handle_action("transition", {})


def test_handle_action_rejects_unknown_action():
    legacy = _LegacyStub(phase="discard")
    controller = GameController(engine=None, legacy_module=legacy)

    with pytest.raises(ValueError, match="Unsupported action_type"):
        controller.handle_action("unknown", None)


def test_process_routes_mouse_action_to_discard_when_in_discard_phase():
    legacy = _LegacyStub(phase="discard")
    controller = GameController(engine=None, legacy_module=legacy)

    controller.process([{"type": "MOUSEBUTTONDOWN", "pos": (10, 20), "button": 1}])

    assert legacy.calls == [("discard", {"type": "MOUSEBUTTONDOWN", "pos": (10, 20), "button": 1})]


def test_process_routes_mouse_action_to_pegging_when_in_pegging_phase():
    legacy = _LegacyStub(phase="pegging")
    controller = GameController(engine=None, legacy_module=legacy)

    controller.process([{"type": "MOUSEBUTTONDOWN", "pos": (30, 40), "button": 1}])

    assert legacy.calls == [("pegging", ({"type": "MOUSEBUTTONDOWN", "pos": (30, 40), "button": 1}, False))]
