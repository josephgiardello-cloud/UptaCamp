from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine import CribbageEngine


class BasePhaseState:
    phase_name: str = ""
    allowed_transitions: set[str] = set()

    def handle_event(self, event: Any, engine: CribbageEngine) -> str | None:
        return None

    def update(self, engine: CribbageEngine) -> str | None:
        return None


class IntroState(BasePhaseState):
    phase_name = "intro"
    allowed_transitions = {"discard", "pegging", "game_over"}


class DiscardState(BasePhaseState):
    phase_name = "discard"
    allowed_transitions = {"pegging", "intro", "game_over"}


class PeggingState(BasePhaseState):
    phase_name = "pegging"
    allowed_transitions = {"counting", "discard", "game_over"}


class CountingState(BasePhaseState):
    phase_name = "counting"
    allowed_transitions = {"end", "game_over"}


class EndState(BasePhaseState):
    phase_name = "end"
    allowed_transitions = {"discard", "intro", "game_over"}


class GameOverState(BasePhaseState):
    phase_name = "game_over"
    allowed_transitions = {"intro", "discard"}


@dataclass
class PhaseStateMachine:
    engine: CribbageEngine

    def __post_init__(self) -> None:
        self.states: dict[str, BasePhaseState] = {
            "intro": IntroState(),
            "discard": DiscardState(),
            "pegging": PeggingState(),
            "counting": CountingState(),
            "end": EndState(),
            "game_over": GameOverState(),
        }

    @property
    def current(self) -> BasePhaseState:
        return self.states.get(self.engine.state.phase, self.states["intro"])

    def handle_event(self, event: Any) -> None:
        transition = self.current.handle_event(event, self.engine)
        if transition:
            self.transition(transition)

    def update(self) -> None:
        transition = self.current.update(self.engine)
        if transition:
            self.transition(transition)

    def transition(self, target_phase: str, force: bool = False) -> bool:
        if target_phase not in self.states:
            return False
        current = self.current
        if not force and current.allowed_transitions and target_phase not in current.allowed_transitions:
            return False
        self.engine.state.phase = target_phase
        return True
