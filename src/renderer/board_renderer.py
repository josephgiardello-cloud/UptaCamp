"""Board rendering logic.

This module gradually migrates pygame drawing code from cribbage_pygame.py.
Initially acts as a facade, then contains direct implementations.
"""

from typing import Any


class RenderingContext:
    """Encapsulates rendering state and configuration."""

    def __init__(
        self,
        screen: Any,
        assets: Any,
        ui_style: str = "classic",
    ):
        """Initialize rendering context.

        Args:
            screen: pygame display surface
            assets: AssetManager instance
            ui_style: UI style ("classic", "competitive_minimal", "broadcast_table", "premium_tabletop")
        """
        self.screen = screen
        self.assets = assets
        self.ui_style = ui_style
        self.width = screen.get_width() if screen else 1920
        self.height = screen.get_height() if screen else 1080

    def update_size(self) -> None:
        """Update dimensions from screen."""
        if self.screen:
            self.width = self.screen.get_width()
            self.height = self.screen.get_height()


class BoardRenderer:
    """Handles all game board rendering.

    Facade that delegates to existing cribbage_pygame drawing functions
    while gradually migrating implementations into this class.
    """

    def __init__(self, context: RenderingContext):
        """Initialize renderer with context.

        Args:
            context: RenderingContext with screen, assets, ui_style
        """
        self.context = context

    def draw_board(self, game_state: Any) -> None:
        """Draw the complete game board.

        Args:
            game_state: Current GameState object
        """
        # TODO: Extract draw_background, draw_scores, draw_crib, draw_header
        # For now, this is called from main loop
        pass

    def draw_background(self) -> None:
        """Draw board background based on UI style."""
        # TODO: Migrate _draw_board_frame logic here
        pass

    def draw_scores(self, game_state: Any) -> None:
        """Draw score panels.

        Args:
            game_state: Current GameState object
        """
        # TODO: Migrate _draw_score_panel logic here
        pass

    def draw_header(self, message: str) -> None:
        """Draw game header with message.

        Args:
            message: Message to display in header
        """
        # TODO: Migrate _draw_game_header logic here
        pass

    def draw_crib(self, game_state: Any) -> None:
        """Draw crib area.

        Args:
            game_state: Current GameState object
        """
        # TODO: Migrate _draw_crib_area logic here
        pass

    def finalize_frame(self) -> None:
        """Update display after rendering all elements."""
        if self.context.screen:
            # This would call pygame.display.flip()
            pass
