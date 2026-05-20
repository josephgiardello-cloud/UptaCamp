"""Board rendering logic.

This module gradually migrates pygame drawing code from cribbage_pygame.py.
Initially acts as a facade, then contains direct implementations.
"""

from typing import Any, Callable


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

    def draw_gameplay_backdrop(self, *, gameplay_background: Any, playfield_alpha: int) -> None:
        """Draw the gameplay table background for current style."""
        import pygame
        import cribbage_pygame as legacy

        if self.context.screen is None:
            return

        sw = self.context.screen.get_width()
        sh = self.context.screen.get_height()

        if self.context.ui_style != "classic":
            legacy._draw_board_frame(self.context.screen)
            return

        if gameplay_background is None:
            legacy._draw_board_frame(self.context.screen)
            return

        bg = pygame.transform.smoothscale(gameplay_background, (sw, sh))
        self.context.screen.blit(bg, (0, 0))

        atmosphere = pygame.Surface((sw, sh), pygame.SRCALPHA)
        atmosphere.fill((10, 22, 18, 44))
        pygame.draw.ellipse(
            atmosphere,
            (220, 188, 118, 16),
            pygame.Rect(sw // 2 - 420, sh // 2 - 220, 840, 500),
        )
        pygame.draw.ellipse(
            atmosphere,
            (0, 0, 0, 52),
            pygame.Rect(14, 14, sw - 28, sh - 28),
            width=34,
        )
        self.context.screen.blit(atmosphere, (0, 0))

        table_zone = pygame.Rect(42, 88, sw - 84, sh - 136)
        zone_overlay = pygame.Surface((table_zone.width, table_zone.height), pygame.SRCALPHA)
        pygame.draw.rect(
            zone_overlay,
            (15, 45, 33, playfield_alpha),
            zone_overlay.get_rect(),
            border_radius=26,
        )
        pygame.draw.rect(
            zone_overlay,
            (214, 184, 113, 95),
            zone_overlay.get_rect(),
            width=2,
            border_radius=26,
        )
        self.context.screen.blit(zone_overlay, table_zone.topleft)

    def draw_player_hand_lane(self, *, session: Any, sw: int, sh: int) -> None:
        """Draw player's hand cards with hover lift."""
        import pygame
        import cribbage_pygame as legacy

        if self.context.screen is None:
            return

        p1_pos = legacy.fixed_hand_positions(1, len(session.player_hand), sw, sh)
        mouse_pos = pygame.mouse.get_pos()
        for i, card in enumerate(session.player_hand):
            card.rect.topleft = p1_pos[i]
            hovered = (
                card.rect.collidepoint(mouse_pos)
                and session.phase in ("discard", "pegging")
                and session.player_turn == 0
            )
            draw_rect = card.rect.copy()
            if hovered:
                draw_rect.y -= 14

            shadow = pygame.Rect(
                draw_rect.x + 6, draw_rect.y + 8, draw_rect.width, draw_rect.height
            )
            pygame.draw.rect(self.context.screen, (0, 0, 0, 80), shadow, border_radius=12)
            if hovered:
                lifted = pygame.transform.rotozoom(card.image, -3, 1.03)
                lifted_rect = lifted.get_rect(center=draw_rect.center)
                self.context.screen.blit(lifted, lifted_rect)
            else:
                card.draw(self.context.screen)

    def draw_ai_hand_lane(self, *, session: Any, sw: int) -> None:
        """Draw opponent hand backs and label."""
        import pygame
        import cribbage_pygame as legacy

        if self.context.screen is None:
            return

        p2_size = (106, 159)
        p2_pos = legacy._row_positions(len(session.ai_hand), sw, 170, p2_size[0], margin=60)
        if session.ai_hand:
            opp_font = pygame.font.SysFont("segoe ui", 18, bold=True)
            opp_label = opp_font.render("Opponent Hand", True, (218, 206, 174))
            row_center_x = p2_pos[0][0] + ((p2_pos[-1][0] + p2_size[0]) - p2_pos[0][0]) // 2
            label_y = max(124, p2_pos[0][1] - 34)
            self.context.screen.blit(opp_label, opp_label.get_rect(center=(row_center_x, label_y)))
        for i, card in enumerate(session.ai_hand):
            card.rect = pygame.Rect(p2_pos[i][0], p2_pos[i][1], p2_size[0], p2_size[1])
            shadow = pygame.Rect(
                card.rect.x + 5, card.rect.y + 6, card.rect.width, card.rect.height
            )
            pygame.draw.rect(self.context.screen, (0, 0, 0, 80), shadow, border_radius=12)
            legacy._draw_card_back(self.context.screen, card.rect)

    def draw_pegging_lane(
        self,
        *,
        session: Any,
        sw: int,
        sh: int,
        card_height: int,
        pegging_y_base: int,
    ) -> tuple[int, tuple[int, int]]:
        """Draw pegging lane and stacked pegging cards."""
        import pygame
        import cribbage_pygame as legacy

        if self.context.screen is None:
            return pegging_y_base, (92, 138)

        pegging_card_size = (92, 138)
        player_row_top = max(510, sh - card_height - 70)
        pegging_y = min(pegging_y_base, player_row_top - pegging_card_size[1] - 62)
        lane_width = min(620, max(220, 128 + len(session.pegging_pile) * 30))
        pegging_lane = pygame.Rect(
            sw // 2 - lane_width // 2,
            pegging_y - 14,
            lane_width,
            pegging_card_size[1] + 20,
        )
        if session.pegging_pile:
            legacy._draw_shadowed_panel(
                self.context.screen,
                pegging_lane,
                (21, 57, 42),
                (182, 155, 100),
                radius=28,
                shadow=(3, 4),
            )
        for i, card in enumerate(session.pegging_pile):
            card.rect = pygame.Rect(
                sw // 2 - 220 + i * 26, pegging_y, pegging_card_size[0], pegging_card_size[1]
            )
            shadow = pygame.Rect(
                card.rect.x + 4, card.rect.y + 6, card.rect.width, card.rect.height
            )
            pygame.draw.rect(self.context.screen, (0, 0, 0, 75), shadow, border_radius=12)
            legacy._draw_scaled_card(self.context.screen, card.image, card.rect, pegging_card_size)

        return pegging_y, pegging_card_size

    def draw_pegging_total_chip(
        self,
        *,
        sw: int,
        pegging_y: int,
        pegging_card_size: tuple[int, int],
        get_pegging_total: Callable[[], int],
    ) -> None:
        """Draw pegging running total chip."""
        import pygame
        import cribbage_pygame as legacy

        if self.context.screen is None:
            return

        total_font = pygame.font.SysFont("segoe ui", 20, bold=True)
        total_chip = pygame.Rect(sw // 2 - 154, pegging_y + pegging_card_size[1] - 4, 308, 46)
        legacy._draw_shadowed_panel(
            self.context.screen,
            total_chip,
            (24, 36, 29),
            (197, 170, 108),
            radius=23,
            shadow=(4, 5),
        )
        total_surf = total_font.render(
            f"Pegging Total: {get_pegging_total()}", True, (238, 224, 188)
        )
        self.context.screen.blit(
            total_surf,
            (
                total_chip.centerx - total_surf.get_width() // 2,
                total_chip.centery - total_surf.get_height() // 2,
            ),
        )

    def draw_end_phase_scoring(
        self,
        *,
        session: Any,
        round_breakdown: dict[str, tuple[int, list[Any]]],
        player_name: str,
        discard_analysis_message: str,
        sw: int,
        sh: int,
    ) -> None:
        """Draw end-of-hand scoring panels and round summary."""
        import pygame
        import cribbage_pygame as legacy

        if self.context.screen is None:
            return

        p1_pts, p1_breakdown = round_breakdown["player"]
        p2_pts, p2_breakdown = round_breakdown["ai"]
        crib_pts, crib_breakdown = round_breakdown["crib"]

        legacy._draw_scoring_breakdown(self.context.screen, 0, p1_breakdown, p1_pts, player_name)
        legacy._draw_scoring_breakdown(self.context.screen, 1, p2_breakdown, p2_pts, player_name)

        if crib_pts > 0 or crib_breakdown:
            playfield = legacy._playfield_rect(self.context.screen)
            crib_panel = legacy._crib_panel_rect(sw, sh)
            crib_w = 240
            crib_h = 140
            crib_x = crib_panel.centerx - crib_w // 2
            if session.dealer == 0:
                crib_y = crib_panel.top - crib_h - 12
            else:
                crib_y = crib_panel.bottom + 12

            crib_x = max(playfield.left + 12, min(crib_x, playfield.right - crib_w - 12))
            crib_y = max(playfield.top + 12, min(crib_y, playfield.bottom - crib_h - 12))
            crib_rect = pygame.Rect(crib_x, crib_y, crib_w, crib_h)
            legacy._draw_shadowed_panel(self.context.screen, crib_rect, (21, 71, 48), (199, 169, 102), radius=18)

            crib_font = pygame.font.SysFont("segoe ui", 16, bold=True)
            item_font = pygame.font.SysFont("segoe ui", 13)
            crib_label = "Crib" if session.dealer == 1 else "Opponent's Crib"
            legacy._draw_label(
                self.context.screen,
                crib_label,
                (crib_rect.x + 12, crib_rect.y + 10),
                crib_font,
                (240, 227, 188),
            )

            y = crib_rect.y + 38
            for desc, _cards, points in crib_breakdown:
                score_str = f"{desc}: +{points}"
                item_surf = item_font.render(score_str, True, (223, 211, 181))
                self.context.screen.blit(item_surf, (crib_rect.x + 12, y))
                y += 22

            total_font = pygame.font.SysFont("segoe ui", 14, bold=True)
            total_str = f"Total: +{crib_pts}"
            total_surf = total_font.render(total_str, True, (240, 205, 124))
            self.context.screen.blit(total_surf, (crib_rect.x + 12, y + 8))

        legacy._draw_round_summary_popup(
            self.context.screen,
            p1_pts,
            p2_pts,
            crib_pts,
            session.dealer,
            player_name,
            discard_analysis_message,
        )

    def draw_end_or_game_over_button(self, *, phase: str, sw: int, sh: int) -> None:
        """Draw end/game over action button."""
        import pygame
        import cribbage_pygame as legacy

        if self.context.screen is None:
            return

        btn = legacy._primary_button_rect(sw, sh)
        is_hover = btn.collidepoint(pygame.mouse.get_pos())
        if is_hover:
            btn = btn.move(0, -2)
        legacy._draw_shadowed_panel(
            self.context.screen,
            btn,
            (34, 50, 40) if is_hover else (28, 40, 33),
            (223, 190, 115),
            radius=18,
            shadow=(5, 7),
        )

        btn_text = "Next Round" if phase == "end" else "Back to Intro"
        btn_font = pygame.font.SysFont("cambria", 28, bold=True)
        btn_shadow = btn_font.render(btn_text, True, (0, 0, 0))
        btn_label = btn_font.render(btn_text, True, (243, 227, 183))
        tx = btn.centerx - btn_label.get_width() // 2
        ty = btn.centery - btn_label.get_height() // 2
        self.context.screen.blit(btn_shadow, (tx + 2, ty + 2))
        self.context.screen.blit(btn_label, (tx, ty))

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
