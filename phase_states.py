from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from engine import CribbageEngine


class BasePhaseState:
    phase_name: str = ""

    def handle_event(self, event: Any, engine: CribbageEngine) -> Optional[str]:
        return None

    def update(self, engine: CribbageEngine) -> Optional[str]:
        return None


class IntroState(BasePhaseState):
    phase_name = "intro"


class DiscardState(BasePhaseState):
    phase_name = "discard"


class PeggingState(BasePhaseState):
    phase_name = "pegging"


class CountingState(BasePhaseState):
    phase_name = "counting"


class EndState(BasePhaseState):
    phase_name = "end"


class GameOverState(BasePhaseState):
    phase_name = "game_over"


@dataclass
class PhaseStateMachine:
    engine: CribbageEngine

    def __post_init__(self) -> None:
        self.states: Dict[str, BasePhaseState] = {
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
            self.engine.state.phase = transition

    def update(self) -> None:
        transition = self.current.update(self.engine)
        if transition:
            self.engine.state.phase = transition
