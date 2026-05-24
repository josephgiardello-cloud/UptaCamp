"""Board rendering logic.

This module contains migrated board drawing behavior owned by src/renderer.
"""

from collections.abc import Callable
from typing import Any, cast

import bert_persona
from cards import parse_card_label

AI_LEVELS: dict[int, str] = {
    1: "Easy",
    2: "Standard",
    3: "Hard",
    4: "Gumption",
    5: "Barnabas",
}


def _opponent_name_for_level(dad_ai_level: int) -> str:
    if dad_ai_level == 4:
        return "Bert"
    if dad_ai_level >= 5:
        return "Barnabas"
    return "AI"


THEME_OUTER_BG = (36, 22, 14)
PLAYFIELD_ALPHA = 64
CARD_WIDTH = 120
CARD_HEIGHT = 180


class RenderingContext:
    """Encapsulates rendering state and configuration."""

    def __init__(
        self,
        screen: Any,
        assets: Any,
        ui_style: str = "classic",
        background_theme: str = "auto",
    ):
        """Initialize rendering context.

        Args:
            screen: pygame display surface
            assets: AssetManager instance
            ui_style: UI style ("classic", "competitive_minimal", "broadcast_table", "premium_tabletop")
            background_theme: Selected table background theme
        """
        self.screen = screen
        self.assets = assets
        self.ui_style = ui_style
        self.background_theme = background_theme
        self.width = screen.get_width() if screen else 1920
        self.height = screen.get_height() if screen else 1080

    def update_size(self) -> None:
        """Update dimensions from screen."""
        if self.screen:
            self.width = self.screen.get_width()
            self.height = self.screen.get_height()


class BoardRenderer:
    """Handles all game board rendering.

    Rendering is implemented locally in this class to avoid runtime
    dependencies on legacy compatibility modules.
    """

    def __init__(self, context: RenderingContext):
        """Initialize renderer with context.

        Args:
            context: RenderingContext with screen, assets, ui_style
        """
        self.context = context

    @staticmethod
    def _fixed_hand_positions(
        player: int, n: int, screen_width: int, screen_height: int
    ) -> list[tuple[int, int]]:
        margin = 8
        right_reserve = 330
        available_width = screen_width - margin - right_reserve
        spacing = min((available_width - CARD_WIDTH) // (n - 1), CARD_WIDTH + 12) if n > 1 else 0
        y = max(500, screen_height - CARD_HEIGHT - 84) if player == 1 else 160
        start_x = margin
        return [(start_x + i * spacing, y) for i in range(n)]

    @staticmethod
    def _row_positions(
        n: int,
        screen_width: int,
        y: int,
        card_width: int,
        margin: int = 8,
        right_reserve: int = 0,
    ) -> list[tuple[int, int]]:
        available_width = screen_width - margin - right_reserve
        spacing = min((available_width - card_width) // (n - 1), card_width + 12) if n > 1 else 0
        start_x = margin
        return [(start_x + i * spacing, y) for i in range(n)]

    @staticmethod
    def _draw_label(
        screen: Any,
        text: str,
        pos: tuple[int, int],
        font: Any,
        color: tuple[int, int, int],
        shadow: tuple[int, int] = (0, 0),
        align_left: bool = True,
    ) -> None:
        shadow_surf = font.render(text, True, (0, 0, 0))
        text_surf = font.render(text, True, color)
        x, y = pos
        if not align_left:
            x -= text_surf.get_width() // 2
        if shadow != (0, 0):
            screen.blit(shadow_surf, (x + shadow[0], y + shadow[1]))
        screen.blit(text_surf, (x, y))

    @staticmethod
    def _draw_scaled_card(screen: Any, surface: Any, rect: Any, size: tuple[int, int]) -> None:
        import pygame

        scaled = pygame.transform.smoothscale(surface, size)
        screen.blit(scaled, rect.topleft)

    def _draw_card_back(self, screen: Any, rect: Any) -> None:
        import pygame

        if self.context.assets is not None and hasattr(self.context.assets, "card_back"):
            back = self.context.assets.card_back
            if back is not None:
                scaled = pygame.transform.smoothscale(back, (rect.width, rect.height))
                screen.blit(scaled, rect.topleft)
                return

        pygame.draw.rect(screen, (247, 242, 231), rect, border_radius=12)
        pygame.draw.rect(screen, (118, 95, 64), rect, width=2, border_radius=12)

    def _draw_shadowed_panel(
        self,
        screen: Any,
        rect: Any,
        fill: tuple[int, int, int],
        border: tuple[int, int, int],
        radius: int = 18,
        shadow: tuple[int, int] = (6, 7),
    ) -> None:
        import pygame

        if self.context.ui_style == "competitive_minimal":
            pygame.draw.rect(screen, fill, rect, border_radius=radius)
            pygame.draw.rect(screen, border, rect, width=1, border_radius=radius)
            return

        shadow_rect = rect.move(shadow)
        pygame.draw.rect(
            screen, (0, 0, 0, 35), shadow_rect.inflate(10, 10), border_radius=radius + 8
        )
        pygame.draw.rect(screen, (0, 0, 0, 70), shadow_rect.inflate(4, 4), border_radius=radius + 4)
        pygame.draw.rect(screen, (0, 0, 0, 95), shadow_rect, border_radius=radius)
        pygame.draw.rect(screen, fill, rect, border_radius=radius)
        pygame.draw.rect(screen, border, rect, width=2, border_radius=radius)
        pygame.draw.rect(
            screen,
            (255, 255, 255, 40),
            rect.inflate(-6, -6),
            width=1,
            border_radius=max(4, radius - 4),
        )

    @staticmethod
    def _playfield_rect(screen: Any) -> Any:
        import pygame

        sw, sh = screen.get_width(), screen.get_height()
        board_rect = pygame.Rect(24, 24, sw - 48, sh - 48)
        inner_rect = board_rect.inflate(-26, -26)
        return inner_rect.inflate(-28, -28)

    @staticmethod
    def _crib_panel_rect(sw: int, sh: int) -> Any:
        import pygame

        board_rect = pygame.Rect(24, 24, sw - 48, sh - 48)
        inner_rect = board_rect.inflate(-26, -26)
        playfield = inner_rect.inflate(-28, -28)
        right_margin = 8
        crib_w = 224
        crib_h = 174
        crib_x = playfield.right - crib_w - right_margin
        crib_y = playfield.top + 38
        return pygame.Rect(crib_x, crib_y, crib_w, crib_h)

    @staticmethod
    def _primary_button_rect(sw: int, sh: int) -> Any:
        import pygame

        w, h = 260, 60
        return pygame.Rect(sw // 2 - w // 2, sh - 180, w, h)

    def _draw_board_frame(self, screen: Any) -> None:
        import pygame

        sw, sh = screen.get_width(), screen.get_height()

        if self.context.ui_style == "competitive_minimal":
            screen.fill((12, 14, 20))
            playfield = self._playfield_rect(screen)
            for x in range(playfield.left + 20, playfield.right, 140):
                pygame.draw.line(screen, (24, 30, 40), (x, playfield.top), (x, playfield.bottom), 1)
            for y in range(playfield.top + 20, playfield.bottom, 110):
                pygame.draw.line(screen, (24, 30, 40), (playfield.left, y), (playfield.right, y), 1)
            return

        if self.context.ui_style == "broadcast_table":
            screen.fill((11, 38, 28))
            playfield = self._playfield_rect(screen)
            pygame.draw.rect(screen, (8, 29, 22), playfield, border_radius=24)
            pygame.draw.rect(screen, (203, 180, 118), playfield, width=2, border_radius=24)
            for y in range(playfield.top + 30, playfield.bottom, 86):
                pygame.draw.line(
                    screen, (18, 58, 43), (playfield.left + 18, y), (playfield.right - 18, y), 1
                )
            return

        if self.context.ui_style == "premium_tabletop":
            screen.fill((66, 40, 21))
            board_rect = pygame.Rect(20, 20, sw - 40, sh - 40)
            pygame.draw.rect(screen, (92, 58, 31), board_rect, border_radius=36)
            pygame.draw.rect(screen, (186, 134, 74), board_rect, width=3, border_radius=36)
            felt = board_rect.inflate(-40, -40)
            pygame.draw.rect(screen, (26, 86, 56), felt, border_radius=30)
            pygame.draw.rect(screen, (226, 196, 138), felt, width=2, border_radius=30)
            return

        screen.fill(THEME_OUTER_BG)
        board_rect = pygame.Rect(24, 24, sw - 48, sh - 48)
        pygame.draw.rect(screen, (158, 106, 64), board_rect, border_radius=34)
        inner_rect = board_rect.inflate(-26, -26)
        pygame.draw.rect(screen, (92, 60, 34), inner_rect, border_radius=28)

        felt_rect = inner_rect.inflate(-28, -28)
        felt_surface = pygame.Surface((felt_rect.width, felt_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(felt_surface, (18, 82, 54), felt_surface.get_rect(), border_radius=22)

        band_w = max(18, felt_rect.width // 18)
        for x in range(felt_rect.left, felt_rect.right, band_w):
            shade = (14, 68, 45) if ((x - felt_rect.left) // band_w) % 2 == 0 else (20, 90, 58)
            local_band = pygame.Rect(x - felt_rect.left, 0, band_w, felt_rect.height)
            pygame.draw.rect(felt_surface, shade, local_band.clip(felt_surface.get_rect()))

        glow = pygame.Surface((felt_rect.width, felt_rect.height), pygame.SRCALPHA)
        for i in range(5):
            alpha = 22 - i * 4
            pygame.draw.rect(
                glow,
                (226, 198, 122, alpha),
                pygame.Rect(
                    12 + i * 2,
                    12 + i * 2,
                    felt_rect.width - 24 - i * 4,
                    felt_rect.height - 24 - i * 4,
                ),
                width=2,
                border_radius=18,
            )
        felt_surface.blit(glow, (0, 0))

        vignette = pygame.Surface((felt_rect.width, felt_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(vignette, (0, 0, 0, 0), vignette.get_rect(), border_radius=22)
        pygame.draw.rect(vignette, (0, 0, 0, 58), vignette.get_rect(), width=26, border_radius=22)
        felt_surface.blit(vignette, (0, 0))
        felt_surface.set_alpha(PLAYFIELD_ALPHA)
        screen.blit(felt_surface, felt_rect.topleft)

    def draw_board(self, game_state: Any) -> None:
        """Draw the complete game board.

        Args:
            game_state: Current GameState object
        """
        if isinstance(game_state, dict):
            state_map = cast(dict[str, Any], game_state)
            message = str(state_map.get("message", ""))
        else:
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

        if self.context.screen is None:
            return

        sw = self.context.screen.get_width()
        sh = self.context.screen.get_height()

        is_old_house = str(getattr(self.context, "background_theme", "auto")) == "old_house"
        is_oos_camper = str(getattr(self.context, "background_theme", "auto")) == "oos_camper"

        if self.context.ui_style != "classic" and not (is_old_house or is_oos_camper):
            self._draw_board_frame(self.context.screen)
            return

        if gameplay_background is None:
            if is_old_house:
                self.context.screen.fill((10, 10, 12))
                warn_font = pygame.font.SysFont("segoe ui", 22, bold=True)
                warn_text = warn_font.render(
                    "Missing assets/old_house_bg.jpg (or .png)", True, (232, 206, 164)
                )
                self.context.screen.blit(
                    warn_text,
                    (sw // 2 - warn_text.get_width() // 2, sh // 2 - warn_text.get_height() // 2),
                )
                return
            if is_oos_camper:
                self.context.screen.fill((14, 18, 14))
                warn_font = pygame.font.SysFont("segoe ui", 22, bold=True)
                warn_text = warn_font.render(
                    "Missing assets/OOS_Camper_bg.jpg", True, (216, 204, 166)
                )
                self.context.screen.blit(
                    warn_text,
                    (sw // 2 - warn_text.get_width() // 2, sh // 2 - warn_text.get_height() // 2),
                )
                return
            self._draw_board_frame(self.context.screen)
            return

        bg = pygame.transform.smoothscale(gameplay_background, (sw, sh))
        self.context.screen.blit(bg, (0, 0))

        atmosphere = pygame.Surface((sw, sh), pygame.SRCALPHA)
        if is_old_house:
            # Keep level 5 visibly lighter so the custom background reads through.
            atmosphere.fill((10, 22, 18, 16))
            edge_alpha = 22
        elif is_oos_camper:
            atmosphere.fill((16, 18, 14, 24))
            edge_alpha = 38
        else:
            atmosphere.fill((10, 22, 18, 44))
            edge_alpha = 52
        pygame.draw.ellipse(
            atmosphere,
            (220, 188, 118, 16),
            pygame.Rect(sw // 2 - 420, sh // 2 - 220, 840, 500),
        )
        pygame.draw.ellipse(
            atmosphere,
            (0, 0, 0, edge_alpha),
            pygame.Rect(14, 14, sw - 28, sh - 28),
            width=34,
        )
        self.context.screen.blit(atmosphere, (0, 0))

        table_zone = pygame.Rect(42, 88, sw - 84, sh - 136)
        zone_overlay = pygame.Surface((table_zone.width, table_zone.height), pygame.SRCALPHA)
        pygame.draw.rect(
            zone_overlay,
            (44, 48, 54, playfield_alpha),
            zone_overlay.get_rect(),
            border_radius=34,
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

        if self.context.screen is None:
            return

        p1_pos = self._fixed_hand_positions(1, len(session.player_hand), sw, sh)
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

        if self.context.screen is None:
            return

        p2_size = (106, 159)
        p2_pos = self._row_positions(
            len(session.ai_hand), sw, 170, p2_size[0], margin=40, right_reserve=380
        )
        if session.ai_hand:
            opp_font = pygame.font.SysFont("segoe ui", 22, bold=True)
            opp_label = opp_font.render("Opponent Hand", True, (244, 236, 210))
            label_x = p2_pos[0][0]
            label_y = p2_pos[0][1] + p2_size[1] + 2
            self.context.screen.blit(
                opp_font.render("Opponent Hand", True, (16, 12, 8)), (label_x + 2, label_y + 2)
            )
            self.context.screen.blit(opp_label, (label_x, label_y))
        for i, card in enumerate(session.ai_hand):
            card.rect = pygame.Rect(p2_pos[i][0], p2_pos[i][1], p2_size[0], p2_size[1])
            shadow = pygame.Rect(
                card.rect.x + 5, card.rect.y + 6, card.rect.width, card.rect.height
            )
            pygame.draw.rect(self.context.screen, (0, 0, 0, 80), shadow, border_radius=12)
            self._draw_card_back(self.context.screen, card.rect)

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
            self._draw_shadowed_panel(
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
            self._draw_scaled_card(self.context.screen, card.image, card.rect, pegging_card_size)

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

        if self.context.screen is None:
            return

        total_font = pygame.font.SysFont("segoe ui", 20, bold=True)
        total_chip = pygame.Rect(sw // 2 - 154, pegging_y + pegging_card_size[1] - 4, 308, 46)
        self._draw_shadowed_panel(
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

        if self.context.screen is None:
            return

        p1_pts, p1_breakdown = round_breakdown["player"]
        p2_pts, p2_breakdown = round_breakdown["ai"]
        crib_pts, crib_breakdown = round_breakdown["crib"]

        dealer_name = _opponent_name_for_level(int(getattr(session, "dad_ai_level", 2)))
        self._draw_scoring_breakdown(0, p1_breakdown, p1_pts, player_name, dealer_name)
        self._draw_scoring_breakdown(1, p2_breakdown, p2_pts, player_name, dealer_name)

        if crib_pts > 0 or crib_breakdown:
            playfield = self._playfield_rect(self.context.screen)
            crib_panel = self._crib_panel_rect(sw, sh)
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
            self._draw_shadowed_panel(
                self.context.screen, crib_rect, (21, 71, 48), (199, 169, 102), radius=18
            )

            crib_font = pygame.font.SysFont("segoe ui", 16, bold=True)
            item_font = pygame.font.SysFont("segoe ui", 13)
            crib_label = "Crib" if session.dealer == 1 else "Opponent's Crib"
            self._draw_label(
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

        self._draw_round_summary_popup(
            player_points=p1_pts,
            dealer_points=p2_pts,
            crib_points=crib_pts,
            dealer_idx=session.dealer,
            player_name=player_name,
            analysis_text=discard_analysis_message,
            dealer_name=dealer_name,
        )

    def _draw_scoring_breakdown(
        self,
        player_idx: int,
        breakdown_list: list[tuple[str, list[Any], int]],
        total_points: int,
        player_name: str,
        dealer_name: str,
    ) -> None:
        """Draw a breakdown panel for one side during end-of-hand scoring."""
        import pygame

        if self.context.screen is None:
            return

        sh = self.context.screen.get_height()
        playfield = self._playfield_rect(self.context.screen)
        panel_w = 220
        panel_h = 280
        if player_idx == 0:
            panel_x = playfield.left + 14
        else:
            panel_x = playfield.right - panel_w - 14
        panel_y = sh // 2 - panel_h // 2
        panel_y = max(playfield.top + 14, min(panel_y, playfield.bottom - panel_h - 14))
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        self._draw_shadowed_panel(
            self.context.screen, panel_rect, (29, 42, 33), (193, 167, 109), radius=18
        )
        header_font = pygame.font.SysFont("segoe ui", 16, bold=True)
        item_font = pygame.font.SysFont("segoe ui", 13)
        total_font = pygame.font.SysFont("segoe ui", 14, bold=True)

        player_label = player_name if player_idx == 0 else dealer_name
        self._draw_label(
            self.context.screen,
            f"{player_label}'s Score",
            (panel_rect.x + 12, panel_rect.y + 10),
            header_font,
            (236, 222, 186),
        )

        y_offset = panel_rect.y + 38
        if breakdown_list:
            for desc, _cards, points in breakdown_list:
                score_str = f"{desc}: +{points}"
                item_surf = item_font.render(score_str, True, (213, 202, 175))
                self.context.screen.blit(item_surf, (panel_rect.x + 12, y_offset))
                y_offset += 22

        pygame.draw.line(
            self.context.screen,
            (153, 132, 90),
            (panel_rect.x + 12, y_offset),
            (panel_rect.right - 12, y_offset),
            1,
        )
        y_offset += 8
        total_str = f"Hand: +{total_points}"
        total_surf = total_font.render(
            total_str,
            True,
            (120, 189, 255) if player_idx == 0 else (255, 148, 130),
        )
        self.context.screen.blit(total_surf, (panel_rect.x + 12, y_offset))

    def _draw_round_summary_popup(
        self,
        *,
        player_points: int,
        dealer_points: int,
        crib_points: int,
        dealer_idx: int,
        player_name: str,
        analysis_text: str,
        dealer_name: str,
    ) -> None:
        """Draw centered round summary popup."""
        import pygame

        if self.context.screen is None:
            return

        def _wrap_line(font: Any, text: str, max_width: int, max_lines: int = 3) -> list[str]:
            words = text.split()
            if not words:
                return []
            lines: list[str] = []
            current = words[0]
            for word in words[1:]:
                trial = f"{current} {word}"
                if font.size(trial)[0] <= max_width:
                    current = trial
                else:
                    lines.append(current)
                    current = word
                    if len(lines) >= max_lines:
                        return lines
            lines.append(current)
            return lines[:max_lines]

        playfield = self._playfield_rect(self.context.screen)
        panel_w = min(560, playfield.width - 80)
        panel_h = 260
        panel_rect = pygame.Rect(
            playfield.centerx - panel_w // 2,
            playfield.centery - panel_h // 2,
            panel_w,
            panel_h,
        )

        dim = pygame.Surface((playfield.width, playfield.height), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 76))
        self.context.screen.blit(dim, playfield.topleft)
        self._draw_shadowed_panel(
            self.context.screen,
            panel_rect,
            (23, 36, 31),
            (210, 182, 113),
            radius=22,
            shadow=(4, 6),
        )

        title_font = pygame.font.SysFont("cambria", 30, bold=True)
        row_font = pygame.font.SysFont("segoe ui", 19, bold=True)
        meta_font = pygame.font.SysFont("segoe ui", 15)

        self._draw_label(
            self.context.screen,
            "Round Summary",
            (panel_rect.x + 22, panel_rect.y + 16),
            title_font,
            (242, 227, 188),
        )

        crib_owner = "Your Crib" if dealer_idx == 0 else f"{dealer_name} Crib"
        rows = [
            (f"{player_name}: +{player_points}", (174, 214, 255)),
            (f"{dealer_name}: +{dealer_points}", (255, 176, 160)),
            (f"{crib_owner}: +{crib_points}", (241, 206, 132)),
            (f"Round Total: +{player_points + dealer_points + crib_points}", (229, 236, 204)),
        ]
        y = panel_rect.y + 66
        for text, color in rows:
            surf = row_font.render(text, True, color)
            self.context.screen.blit(surf, (panel_rect.x + 24, y))
            y += 34

        analysis = analysis_text.strip()
        if analysis:
            wrapped = _wrap_line(meta_font, analysis, panel_rect.width - 48, max_lines=2)
            for line in wrapped:
                line_surf = meta_font.render(line, True, (211, 201, 175))
                self.context.screen.blit(line_surf, (panel_rect.x + 24, y))
                y += 22

        prompt = meta_font.render("Press R for next round", True, (211, 201, 175))
        self.context.screen.blit(
            prompt, (panel_rect.right - prompt.get_width() - 22, panel_rect.bottom - 28)
        )

    def draw_end_or_game_over_button(self, *, phase: str, sw: int, sh: int) -> None:
        """Draw end/game over action button."""
        import pygame

        if self.context.screen is None:
            return

        btn = self._primary_button_rect(sw, sh)
        is_hover = btn.collidepoint(pygame.mouse.get_pos())
        if is_hover:
            btn = btn.move(0, -2)
        self._draw_shadowed_panel(
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
        if self.context.screen is None:
            return

        theme_key = str(getattr(self.context, "background_theme", "auto"))
        gameplay_background = None
        assets = getattr(self.context, "assets", None)
        if assets is not None:
            if theme_key == "wharf":
                gameplay_background = assets.get_background(
                    "The_wharf_bg.jpg"
                ) or assets.get_background("Tony.jpg")
            elif theme_key == "oos_camper":
                gameplay_background = assets.get_background("OOS_Camper_bg.jpg")
            elif theme_key == "old_house":
                gameplay_background = assets.get_background(
                    "old_house_bg.jpg"
                ) or assets.get_background("old_house_bg.png")
            elif theme_key == "tree_path_bg":
                gameplay_background = assets.get_background("Tree_path_bg.jpg")
            elif theme_key == "dark_shadows":
                gameplay_background = assets.get_background("board.jpg")
            else:
                gameplay_background = assets.get_background("table.jpg") or assets.get_background(
                    "table.png"
                )

            if gameplay_background is None and theme_key not in {
                "old_house",
                "oos_camper",
                "tree_path_bg",
            }:
                gameplay_background = (
                    assets.get_background("table.jpg")
                    or assets.get_background("table.png")
                    or assets.get_background("board.jpg")
                    or assets.get_background("The_wharf_bg.jpg")
                    or assets.get_background("Tony.jpg")
                )

        # Custom level backgrounds should reveal more of their art.
        playfield_alpha = int(255 * 0.20) if theme_key == "old_house" else PLAYFIELD_ALPHA
        self.draw_gameplay_backdrop(
            gameplay_background=gameplay_background,
            playfield_alpha=playfield_alpha,
        )

    def draw_scores(self, game_state: Any) -> None:
        """Draw score panels.

        Args:
            game_state: Current GameState object
        """
        import pygame

        if self.context.screen is None:
            return

        if isinstance(game_state, dict):
            state_map = cast(dict[str, Any], game_state)
            dealer = int(state_map.get("dealer", 0))
            scores = list(cast(list[int], state_map.get("scores", [0, 0])))
            dad_ai_level = int(state_map.get("dad_ai_level", 2))
            player_name = str(state_map.get("player_name", "Player"))
        else:
            dealer = int(getattr(game_state, "dealer", 0))
            scores = list(getattr(game_state, "scores", [0, 0]))
            dad_ai_level = int(getattr(game_state, "dad_ai_level", 2))
            player_name = str(getattr(game_state, "player_name", "Player"))

        dealer_name = _opponent_name_for_level(dad_ai_level)
        playfield = self._playfield_rect(self.context.screen)
        panel_w, panel_h = 224, 194
        panel_margin = 8
        panel_x = playfield.right - panel_w - panel_margin
        panel_y = playfield.bottom - panel_h - panel_margin
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        score_surface = pygame.Surface(self.context.screen.get_size(), pygame.SRCALPHA)
        if self.context.ui_style == "competitive_minimal":
            self._draw_shadowed_panel(
                score_surface, panel_rect, (18, 22, 30), (104, 120, 150), radius=20
            )
        elif self.context.ui_style == "broadcast_table":
            self._draw_shadowed_panel(
                score_surface, panel_rect, (14, 33, 25), (189, 167, 112), radius=22
            )
        elif self.context.ui_style == "premium_tabletop":
            self._draw_shadowed_panel(
                score_surface, panel_rect, (24, 54, 40), (230, 200, 144), radius=24
            )
        else:
            self._draw_shadowed_panel(
                score_surface, panel_rect, (26, 38, 31), (201, 174, 108), radius=26
            )

        title_font = pygame.font.SysFont("cambria", 24, bold=True)
        body_font = pygame.font.SysFont("segoe ui", 16, bold=True)
        small_font = pygame.font.SysFont("segoe ui", 13)
        self._draw_label(
            score_surface,
            "Cribbage",
            (panel_rect.x + 18, panel_rect.y + 12),
            title_font,
            (220, 230, 250) if self.context.ui_style == "competitive_minimal" else (240, 227, 188),
        )
        self._draw_label(
            score_surface,
            f"Dealer: {'You' if dealer == 0 else dealer_name}",
            (panel_rect.x + 18, panel_rect.y + 46),
            body_font,
            (173, 186, 212) if self.context.ui_style == "competitive_minimal" else (213, 202, 174),
        )

        player_chip = pygame.Rect(panel_rect.x + 14, panel_rect.y + 74, panel_rect.width - 28, 32)
        dad_chip = pygame.Rect(panel_rect.x + 14, panel_rect.y + 112, panel_rect.width - 28, 32)
        if self.context.ui_style == "competitive_minimal":
            pygame.draw.rect(score_surface, (26, 38, 56), player_chip, border_radius=16)
            pygame.draw.rect(score_surface, (45, 32, 44), dad_chip, border_radius=16)
            pygame.draw.rect(score_surface, (120, 150, 196), player_chip, width=1, border_radius=16)
            pygame.draw.rect(score_surface, (176, 130, 168), dad_chip, width=1, border_radius=16)
        else:
            pygame.draw.rect(score_surface, (20, 53, 76), player_chip, border_radius=16)
            pygame.draw.rect(score_surface, (37, 22, 20), dad_chip, border_radius=16)
            pygame.draw.rect(score_surface, (153, 205, 255), player_chip, width=1, border_radius=16)
            pygame.draw.rect(score_surface, (255, 159, 141), dad_chip, width=1, border_radius=16)

        player_surf = body_font.render(f"{player_name}: {scores[0]}", True, (185, 222, 255))
        dad_surf = body_font.render(f"{dealer_name} Score: {scores[1]}", True, (255, 176, 160))
        score_surface.blit(
            player_surf,
            (
                player_chip.centerx - player_surf.get_width() // 2,
                player_chip.centery - player_surf.get_height() // 2,
            ),
        )
        score_surface.blit(
            dad_surf,
            (
                dad_chip.centerx - dad_surf.get_width() // 2,
                dad_chip.centery - dad_surf.get_height() // 2,
            ),
        )
        self._draw_label(
            score_surface,
            f"AI Difficulty: {AI_LEVELS.get(min(max(int(dad_ai_level), 1), 5), 'Medium')}",
            (panel_rect.x + 18, panel_rect.y + 150),
            small_font,
            (164, 177, 208) if self.context.ui_style == "competitive_minimal" else (214, 203, 174),
        )

        if dad_ai_level == 5:
            try:
                posture = bert_persona.level5_play_posture(
                    {"player_score": int(scores[0]), "bert_score": int(scores[1])}
                )
            except Exception:
                posture = "balanced"
            self._draw_label(
                score_surface,
                f"Barnabas Posture: {posture.title()}",
                (panel_rect.x + 18, panel_rect.y + 168),
                small_font,
                (
                    (154, 173, 209)
                    if self.context.ui_style == "competitive_minimal"
                    else (196, 215, 174)
                ),
            )

        score_surface.set_alpha(int(255 * 0.75))
        self.context.screen.blit(score_surface, (0, 0))

    def draw_header(self, message: str) -> None:
        """Draw game header with message.

        Args:
                is_tree_path_bg = str(getattr(self.context, "background_theme", "auto")) == "tree_path_bg"
            message: Message to display in header
        """
        import pygame

        if self.context.screen is None:
            return

        sw = self.context.screen.get_width()
        body_font = pygame.font.SysFont("segoe ui", 22, bold=True)
        header_text = message.strip() or "Play the hand. Mind the crib. Beat the table."
        box_w = min(860, sw - 140)
        msg_box = pygame.Rect(sw // 2 - box_w // 2, 22, box_w, 58)
        if self.context.ui_style == "competitive_minimal":
            pygame.draw.rect(self.context.screen, (16, 20, 28), msg_box, border_radius=20)
            pygame.draw.rect(
                self.context.screen, (108, 126, 156), msg_box, width=1, border_radius=20
            )
            msg_surf = body_font.render(header_text, True, (222, 232, 248))
        elif self.context.ui_style == "broadcast_table":
            pygame.draw.rect(self.context.screen, (10, 32, 24), msg_box, border_radius=24)
            pygame.draw.rect(
                self.context.screen, (209, 184, 122), msg_box, width=2, border_radius=24
            )
            msg_surf = body_font.render(header_text, True, (240, 231, 198))
        elif self.context.ui_style == "premium_tabletop":
            pygame.draw.rect(self.context.screen, (19, 56, 40), msg_box, border_radius=30)
            pygame.draw.rect(
                self.context.screen, (236, 206, 147), msg_box, width=2, border_radius=30
            )
            msg_surf = body_font.render(header_text, True, (248, 236, 209))
        else:
            pygame.draw.rect(
                self.context.screen, (0, 0, 0, 78), msg_box.move(3, 5), border_radius=29
            )
            pygame.draw.rect(self.context.screen, (24, 36, 29, 240), msg_box, border_radius=29)
            pygame.draw.rect(
                self.context.screen, (212, 183, 114), msg_box, width=2, border_radius=29
            )
            pygame.draw.line(
                self.context.screen,
                (255, 234, 183),
                (msg_box.left + 24, msg_box.top + 11),
                (msg_box.right - 24, msg_box.top + 11),
                1,
            )
            msg_surf = body_font.render(header_text, True, (238, 225, 191))
        self.context.screen.blit(
            msg_surf,
            (
                msg_box.centerx - msg_surf.get_width() // 2,
                msg_box.centery - msg_surf.get_height() // 2,
            ),
        )

    def draw_crib(self, game_state: Any) -> None:
        """Draw crib area.

        Args:
            game_state: Current GameState object
        """
        import pygame

        if self.context.screen is None:
            return

        if isinstance(game_state, dict):
            state_map = cast(dict[str, Any], game_state)
            crib_count = int(state_map.get("crib_count", 0))
            starter_card = state_map.get("starter_card")
            card_images = dict(cast(dict[str, Any], state_map.get("card_images", {})))
            dealer = int(state_map.get("dealer", 0))
            phase = str(state_map.get("phase", "intro"))
        else:
            crib = list(getattr(game_state, "crib", []))
            crib_count = len(crib)
            starter_card = getattr(game_state, "starter_card", None)
            card_images = dict(getattr(game_state, "card_images", {}))
            dealer = int(getattr(game_state, "dealer", 0))
            phase = str(getattr(game_state, "phase", "intro"))

        sw, sh = self.context.screen.get_width(), self.context.screen.get_height()
        label_font = pygame.font.SysFont("segoe ui", 18, bold=True)
        small_font = pygame.font.SysFont("segoe ui", 15)
        crib_surface = pygame.Surface((sw, sh), pygame.SRCALPHA)

        crib_panel = self._crib_panel_rect(sw, sh)
        if self.context.ui_style == "competitive_minimal":
            self._draw_shadowed_panel(
                crib_surface, crib_panel, (18, 24, 34), (104, 120, 150), radius=20
            )
        elif self.context.ui_style == "broadcast_table":
            self._draw_shadowed_panel(
                crib_surface, crib_panel, (14, 54, 38), (194, 171, 113), radius=22
            )
        elif self.context.ui_style == "premium_tabletop":
            self._draw_shadowed_panel(
                crib_surface, crib_panel, (21, 74, 49), (232, 202, 147), radius=24
            )
        else:
            self._draw_shadowed_panel(
                crib_surface, crib_panel, (20, 66, 45), (206, 176, 108), radius=24
            )
        crib_owner_label = "Your Crib" if dealer == 0 else "Opponent's Crib"
        self._draw_label(
            crib_surface,
            crib_owner_label,
            (crib_panel.x + 18, crib_panel.y + 12),
            label_font,
            (208, 222, 248) if self.context.ui_style == "competitive_minimal" else (240, 227, 188),
        )
        if phase == "discard" and crib_count < 4:
            self._draw_label(
                crib_surface,
                "Drop 2 cards here",
                (crib_panel.x + 18, crib_panel.y + 38),
                small_font,
                (
                    (164, 177, 208)
                    if self.context.ui_style == "competitive_minimal"
                    else (221, 192, 129)
                ),
            )

        card_w, card_h = 60, 88
        card_gap = 12
        card_group_left = crib_panel.x + 18
        for i in range(2):
            card_rect = pygame.Rect(
                card_group_left + i * (card_w + card_gap), crib_panel.y + 70, card_w, card_h
            )
            if i < crib_count:
                self._draw_card_back(crib_surface, card_rect)
            else:
                pygame.draw.rect(
                    crib_surface, (250, 241, 221, 38), card_rect, width=2, border_radius=12
                )
                pygame.draw.rect(
                    crib_surface,
                    (166, 144, 98, 46),
                    card_rect.inflate(-8, -8),
                    width=1,
                    border_radius=9,
                )

        crib_surface.set_alpha(int(255 * 0.75))
        self.context.screen.blit(crib_surface, (0, 0))

        starter_box = pygame.Rect(crib_panel.centerx - 54, crib_panel.bottom + 12, 108, 136)
        starter_surface = pygame.Surface((sw, sh), pygame.SRCALPHA)
        pygame.draw.rect(starter_surface, (31, 43, 35), starter_box, border_radius=18)
        pygame.draw.rect(starter_surface, (214, 184, 114), starter_box, width=2, border_radius=18)
        if starter_card is not None:
            starter_image: Any = card_images.get(str(starter_card))
            if starter_image is None:
                rank_raw, suit_raw = parse_card_label(str(starter_card))
                rank_map = {"a": "ace", "j": "jack", "q": "queen", "k": "king"}
                rank_token = rank_map.get(rank_raw.lower(), rank_raw.lower())
                starter_key = f"{rank_token}_of_{suit_raw.lower()}"
                starter_image = card_images.get(starter_key)
                if (
                    starter_image is None
                    and self.context.assets is not None
                    and hasattr(self.context.assets, "get_card_image")
                ):
                    starter_image = self.context.assets.get_card_image(starter_key)
            if starter_image is not None:
                starter_surf = pygame.transform.smoothscale(starter_image, (64, 90))
                starter_surface.blit(starter_surf, (starter_box.x + 22, starter_box.y + 24))

        starter_surface.set_alpha(int(255 * 0.75))
        self.context.screen.blit(starter_surface, (0, 0))

    def finalize_frame(self) -> None:
        """Update display after rendering all elements."""
        if self.context.screen:
            import pygame

            pygame.display.flip()
