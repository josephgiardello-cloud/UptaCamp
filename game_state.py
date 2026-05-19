from dataclasses import dataclass, field
from typing import Any


@dataclass
class GameState:
    phase: str = "intro"
    dealer: int = 0
    scores: list[int] = field(default_factory=lambda: [0, 0])
    player_hand: list[Any] = field(default_factory=list)
    ai_hand: list[Any] = field(default_factory=list)
    crib: list[Any] = field(default_factory=list)
    pegging_pile: list[Any] = field(default_factory=list)
    player_kept: list[Any] = field(default_factory=list)
    ai_kept: list[Any] = field(default_factory=list)
    starter_card: str | None = None
    player_turn: int = 0
    pegging_passes: list[bool] = field(default_factory=lambda: [False, False])
    last_pegging_player: int | None = None
    message: str = ""
    dad_ai_level: int = 2
    stock_labels: list[str] = field(default_factory=list)
    deck: Any | None = None
    cut_card: Any | None = None
    selected_cards: list[int] = field(default_factory=list)
    winner: int | None = None
    ai_level: int = 1
    player_name: str = ""
    ai_name: str = "Dad"
    history: list[Any] = field(default_factory=list)
    current_phase: Any | None = None
    phase_name: str = "intro"

    def transition_to(self, new_phase_class: type[Any], ctx: Any = None) -> None:
        if self.current_phase is not None and hasattr(self.current_phase, "exit"):
            self.current_phase.exit(self, ctx)
        self.current_phase = new_phase_class()
        self.phase_name = new_phase_class.__name__
        self.phase = getattr(self.current_phase, "phase_name", self.phase_name.lower())
        if hasattr(self.current_phase, "enter"):
            self.current_phase.enter(self, ctx)
