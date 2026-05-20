import json
from dataclasses import dataclass, field
from pathlib import Path
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
    ai_name: str = "Dealer"
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

        # Prepare serializable data (exclude current_phase which contains state objects)
        state_dict = {
            "phase": self.phase,
            "dealer": self.dealer,
            "scores": self.scores,
            "player_hand": [str(c) for c in self.player_hand],
            "ai_hand": [str(c) for c in self.ai_hand],
            "crib": [str(c) for c in self.crib],
            "pegging_pile": [str(c) for c in self.pegging_pile],
            "player_kept": [str(c) for c in self.player_kept],
            "ai_kept": [str(c) for c in self.ai_kept],
            "starter_card": str(self.starter_card) if self.starter_card else None,
            "player_turn": self.player_turn,
            "pegging_passes": self.pegging_passes,
            "last_pegging_player": self.last_pegging_player,
            "message": self.message,
            "dad_ai_level": self.dad_ai_level,
            "ai_level": self.ai_level,
            "player_name": self.player_name,
            "ai_name": self.ai_name,
            "phase_name": self.phase_name,
            "winner": self.winner,
        }

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

            # Create new GameState with loaded data
            state = cls()
            for key, value in data.items():
                if hasattr(state, key):
                    setattr(state, key, value)
            return state
        except Exception as e:
            print(f"Warning: Failed to load checkpoint from {path}: {e}")
            return None

