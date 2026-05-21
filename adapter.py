from __future__ import annotations

from typing import Any

from engine import CribbageEngine


class EngineAdapter:
    """Bridge layer to synchronize legacy module globals with engine state.

    This keeps migration low-risk: legacy pygame handlers can continue to run
    while selected phases are delegated to the engine.
    """

    def __init__(self, engine: CribbageEngine, legacy_module: Any):
        self.engine = engine
        self.legacy = legacy_module

    def update_engine_from_globals(self) -> None:
        s = self.engine.state
        s.phase = self.legacy.game_phase
        s.dealer = self.legacy.dealer
        s.scores = list(self.legacy.player_scores)
        s.player_hand = list(self.legacy.player1_hand)
        s.ai_hand = list(self.legacy.player2_hand)
        s.crib = list(self.legacy.crib)
        s.pegging_pile = list(self.legacy.pegging_pile)
        s.player_kept = list(self.legacy.player1_kept)
        s.ai_kept = list(self.legacy.player2_kept)
        s.starter_card = self.legacy.starter_card
        s.player_turn = self.legacy.player_turn
        s.pegging_passes = list(self.legacy.pegging_passes)
        s.last_pegging_player = self.legacy.last_pegging_player
        s.message = self.legacy.message
        s.dad_ai_level = self.legacy.dad_ai_level
        s.stock_labels = list(self.legacy._stock_labels)
        s.winner = getattr(self.legacy, "winner", None)
        s.player_name = getattr(self.legacy, "player_name", "")
        s.ai_name = getattr(self.legacy, "ai_name", s.ai_name)

    def update_globals_from_engine(self) -> None:
        s = self.engine.state
        self.legacy.game_phase = s.phase
        self.legacy.dealer = s.dealer
        self.legacy.player_scores[:] = s.scores
        self.legacy.player1_hand[:] = s.player_hand
        self.legacy.player2_hand[:] = s.ai_hand
        self.legacy.crib[:] = s.crib
        self.legacy.pegging_pile[:] = s.pegging_pile
        self.legacy.player1_kept[:] = s.player_kept
        self.legacy.player2_kept[:] = s.ai_kept
        self.legacy.starter_card = s.starter_card
        self.legacy.player_turn = s.player_turn
        self.legacy.pegging_passes[:] = s.pegging_passes
        self.legacy.last_pegging_player = s.last_pegging_player
        self.legacy.message = s.message
        self.legacy.dad_ai_level = s.dad_ai_level
        self.legacy._stock_labels[:] = s.stock_labels
        if hasattr(self.legacy, "winner"):
            self.legacy.winner = s.winner
        if hasattr(self.legacy, "player_name"):
            self.legacy.player_name = s.player_name
        if hasattr(self.legacy, "ai_name"):
            self.legacy.ai_name = s.ai_name
