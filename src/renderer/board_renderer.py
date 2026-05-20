"""Board rendering logic (stub for architecture refactoring).

This module will eventually contain all pygame drawing code extracted from cribbage_pygame.py.
For now, it's a placeholder that can be populated incrementally.
"""

from typing import Any


class BoardRenderer:
    """Handles all game board rendering."""

    def __init__(self, screen: Any, assets: Any):
        """Initialize renderer.

        Args:
            screen: pygame display surface
            assets: AssetManager instance
        """
        self.screen = screen
        self.assets = assets

    def draw_board(self, game_state: Any) -> None:
        """Draw the complete game board.

        Args:
            game_state: Current GameState object
        """
        # TODO: Extract from cribbage_pygame._draw_* methods
        pass

    def draw_cards(self, card_objects: list[Any], pos: tuple[int, int]) -> None:
        """Draw cards at specified position.

        Args:
            card_objects: List of card objects to draw
            pos: (x, y) position tuple
        """
        # TODO: Extract from cribbage_pygame._draw_cards
        pass

    def draw_scores(self, scores: tuple[int, int]) -> None:
        """Draw score display.

        Args:
            scores: (player_score, ai_score) tuple
        """
        # TODO: Extract from cribbage_pygame score drawing
        pass
