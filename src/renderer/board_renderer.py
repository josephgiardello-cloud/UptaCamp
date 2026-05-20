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
        message = str(getattr(game_state, "message", ""))
        self.draw_header(message)
        self.draw_scores(game_state)
        self.draw_crib(game_state)

    def draw_classic_hud(
        self,
        *,
        message: str,
        dealer: int,
        scores: list[int],
        dad_ai_level: int,
        player_name: str,
        crib_count: int,
        starter_card: Any,
        card_images: dict[str, Any],
        phase: str,
    ) -> None:
        """Draw legacy classic HUD elements through renderer ownership.

        This wrapper is used during migration to reduce direct rendering calls
        in the legacy game loop without changing visual behavior.
        """
        self.draw_header(message)
        self.draw_scores(
            {
                "dealer": dealer,
                "scores": scores,
                "dad_ai_level": dad_ai_level,
                "player_name": player_name,
            }
        )
        self.draw_crib(
            {
                "crib_count": crib_count,
                "starter_card": starter_card,
                "card_images": card_images,
                "dealer": dealer,
                "phase": phase,
            }
        )

    def draw_background(self) -> None:
        """Draw board background based on UI style."""
        import cribbage_pygame as legacy

        if self.context.screen is not None:
            legacy._draw_board_frame(self.context.screen)

    def draw_scores(self, game_state: Any) -> None:
        """Draw score panels.

        Args:
            game_state: Current GameState object
        """
        import cribbage_pygame as legacy

        if self.context.screen is None:
            return

        if isinstance(game_state, dict):
            dealer = int(game_state.get("dealer", 0))
            scores = list(game_state.get("scores", [0, 0]))
            dad_ai_level = int(game_state.get("dad_ai_level", 2))
            player_name = str(game_state.get("player_name", "Player"))
        else:
            dealer = int(getattr(game_state, "dealer", 0))
            scores = list(getattr(game_state, "scores", [0, 0]))
            dad_ai_level = int(getattr(game_state, "dad_ai_level", 2))
            player_name = str(getattr(game_state, "player_name", "Player"))

        legacy._draw_score_panel(self.context.screen, dealer, scores, dad_ai_level, player_name)

    def draw_header(self, message: str) -> None:
        """Draw game header with message.

        Args:
            message: Message to display in header
        """
        import cribbage_pygame as legacy

        if self.context.screen is not None:
            legacy._draw_game_header(self.context.screen, message)

    def draw_crib(self, game_state: Any) -> None:
        """Draw crib area.

        Args:
            game_state: Current GameState object
        """
        import cribbage_pygame as legacy

        if self.context.screen is None:
            return

        if isinstance(game_state, dict):
            crib_count = int(game_state.get("crib_count", 0))
            starter_card = game_state.get("starter_card")
            card_images = dict(game_state.get("card_images", {}))
            dealer = int(game_state.get("dealer", 0))
            phase = str(game_state.get("phase", "intro"))
        else:
            crib = list(getattr(game_state, "crib", []))
            crib_count = len(crib)
            starter_card = getattr(game_state, "starter_card", None)
            card_images = dict(getattr(game_state, "card_images", {}))
            dealer = int(getattr(game_state, "dealer", 0))
            phase = str(getattr(game_state, "phase", "intro"))

        legacy._draw_crib_area(
            self.context.screen,
            crib_count,
            starter_card,
            card_images,
            dealer,
            phase,
        )

    def finalize_frame(self) -> None:
        """Update display after rendering all elements."""
        if self.context.screen:
            import pygame

            pygame.display.flip()
