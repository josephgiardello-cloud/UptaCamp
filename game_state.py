import json

# pyright: reportUnknownVariableType=false
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast


@dataclass
class GameState:
    phase: str = "intro"
    dealer: int = 0
    scores: list[int] = field(default_factory=lambda: [0, 0])
    player_hand: list[object] = field(default_factory=list)
    ai_hand: list[object] = field(default_factory=list)
    crib: list[object] = field(default_factory=list)
    pegging_pile: list[object] = field(default_factory=list)
    player_kept: list[object] = field(default_factory=list)
    ai_kept: list[object] = field(default_factory=list)
    starter_card: str | None = None
    player_turn: int = 0
    pegging_passes: list[bool] = field(default_factory=lambda: [False, False])
    round_pegging_points: list[int] = field(default_factory=lambda: [0, 0])
    last_pegging_player: int | None = None
    message: str = ""
    dad_ai_level: int = 2
    stock_labels: list[str] = field(default_factory=list)
    deck: object | None = None
    cut_card: object | None = None
    selected_cards: list[int] = field(default_factory=list)
    winner: int | None = None
    ai_level: int = 1
    player_name: str = ""
    ai_name: str = "Dealer"
    ai_last_decision_reason: str = ""
    history: list[object] = field(default_factory=list)
    current_phase: object | None = None
    phase_name: str = "intro"
    last_counting_result: dict[str, int] = field(default_factory=dict)
    last_counting_breakdown: dict[str, object] = field(default_factory=dict)
    counting_resolved: bool = False
    counting_next_phase: str = "end"
    # Online / remote orchestration fields
    deal_ready: list[str] = field(default_factory=list)
    discard_by_player: dict[str, list[str]] = field(default_factory=dict)
    pegging_running_total: int = 0
    phase_progress: int = 0
    phase_index: int = 0
    count_by_player: dict[str, bool] = field(default_factory=dict)
    last_action: dict[str, object] = field(default_factory=dict)

    def reset(self) -> None:
        fresh = type(self)()
        self.__dict__.clear()
        self.__dict__.update(fresh.__dict__)

    def transition_to(self, new_phase_class: type[Any], ctx: Any = None) -> None:
        previous = self.current_phase
        if previous is not None and hasattr(previous, "exit"):
            cast(Any, previous).exit(self, ctx)
        self.current_phase = new_phase_class()
        self.phase_name = new_phase_class.__name__
        self.phase = getattr(self.current_phase, "phase_name", self.phase_name.lower())
        current = self.current_phase
        if current is not None and hasattr(current, "enter"):
            cast(Any, current).enter(self, ctx)

    @staticmethod
    def _serialize_card(card: object) -> str:
        label = getattr(card, "label", None)
        if isinstance(label, str) and label:
            return label
        return str(card)

    def to_dict(self) -> dict[str, Any]:
        # Keep checkpoint schema explicit to avoid accidentally persisting runtime-only internals.
        return {
            "phase": self.phase,
            "dealer": self.dealer,
            "scores": list(self.scores),
            "player_hand": [self._serialize_card(c) for c in self.player_hand],
            "ai_hand": [self._serialize_card(c) for c in self.ai_hand],
            "crib": [self._serialize_card(c) for c in self.crib],
            "pegging_pile": [self._serialize_card(c) for c in self.pegging_pile],
            "player_kept": [self._serialize_card(c) for c in self.player_kept],
            "ai_kept": [self._serialize_card(c) for c in self.ai_kept],
            "starter_card": str(self.starter_card) if self.starter_card else None,
            "player_turn": self.player_turn,
            "pegging_passes": list(self.pegging_passes),
            "round_pegging_points": list(self.round_pegging_points),
            "last_pegging_player": self.last_pegging_player,
            "message": self.message,
            "dad_ai_level": self.dad_ai_level,
            "stock_labels": list(self.stock_labels),
            "ai_level": self.ai_level,
            "player_name": self.player_name,
            "ai_name": self.ai_name,
            "ai_last_decision_reason": self.ai_last_decision_reason,
            "phase_name": self.phase_name,
            "winner": self.winner,
            "last_counting_result": dict(self.last_counting_result),
            "last_counting_breakdown": dict(self.last_counting_breakdown),
            "counting_resolved": self.counting_resolved,
            "counting_next_phase": self.counting_next_phase,
            "deal_ready": list(self.deal_ready),
            "discard_by_player": {k: list(v) for k, v in self.discard_by_player.items()},
            "pegging_running_total": int(self.pegging_running_total),
            "phase_progress": int(self.phase_progress),
            "phase_index": int(self.phase_index),
            "count_by_player": dict(self.count_by_player),
            "last_action": dict(self.last_action),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameState":
        state = cls()
        for key, value in data.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return state

    def save_checkpoint(self, path: str | Path | None = None) -> str:
        """Save game state to checkpoint file.

        Args:
            path: File path for checkpoint (default: game_checkpoint.json)

        Returns:
            Path to saved checkpoint file
        """
        if path is None:
            path = Path("game_checkpoint.json")
        else:
            path = Path(path)

        state_dict = self.to_dict()

        try:
            with open(path, "w") as f:
                json.dump(state_dict, f, indent=2)
            return str(path)
        except Exception as e:
            print(f"Warning: Failed to save checkpoint to {path}: {e}")
            return ""

    @classmethod
    def load_checkpoint(cls, path: str | Path | None = None) -> "GameState | None":
        """Load game state from checkpoint file.

        Args:
            path: File path for checkpoint (default: game_checkpoint.json)

        Returns:
            GameState instance or None if checkpoint not found/invalid
        """
        if path is None:
            path = Path("game_checkpoint.json")
        else:
            path = Path(path)

        if not path.exists():
            return None

        try:
            with open(path) as f:
                data = json.load(f)

            return cls.from_dict(data)
        except Exception as e:
            print(f"Warning: Failed to load checkpoint from {path}: {e}")
            return None
