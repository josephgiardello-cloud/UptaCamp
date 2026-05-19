from dataclasses import dataclass, field
from typing import Any


@dataclass
class GameState:
    phase: str = "intro"
    scores: list[int] = field(default_factory=lambda: [0, 0])
    player_hand: list[Any] = field(default_factory=list)
    ai_hand: list[Any] = field(default_factory=list)
    pegging_pile: list[Any] = field(default_factory=list)
    crib: list[Any] = field(default_factory=list)
    dealer: int = 0
    message: str = ""
    deck: Any | None = None
    cut_card: Any | None = None
    selected_cards: list[int] = field(default_factory=list)
    winner: int | None = None
    ai_level: int = 1
    player_name: str = ""
    ai_name: str = "Dad"
    history: list[Any] = field(default_factory=list)
    starter_card: str | None = None
    pegging_passes: list[bool] = field(default_factory=lambda: [False, False])
    last_pegging_player: int | None = None
    player_kept: list[Any] = field(default_factory=list)
    ai_kept: list[Any] = field(default_factory=list)
