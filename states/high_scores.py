from __future__ import annotations

import pygame

from stats_manager import get_player_records_list

from .base import GameStateBase


class HighScoresState(GameStateBase):
    def __init__(self):
        self.back_rect: pygame.Rect | None = None

    def handle_event(self, event, engine, assets, app):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_b):
            from .intro import IntroState

            return IntroState()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_rect is not None and self.back_rect.collidepoint(event.pos):
                from .intro import IntroState

                return IntroState()

        return self

    def update(self, engine, dt: int, app):
        return None

    def draw(self, screen, engine, assets, app):
        bg = (
            assets.get_background("High_score_bg.jpg")
            or assets.get_background("High_score_bg.png")
            or assets.get_background("high_score_bg.jpg")
            or assets.get_background("high_score_bg.png")
            or assets.get_background("welcome_bg.png")
            or assets.get_background("table.jpg")
            or assets.get_background("table.png")
        )
        if bg:
            scaled = pygame.transform.smoothscale(bg, screen.get_size())
            screen.blit(scaled, (0, 0))
        else:
            screen.fill((24, 36, 30))

        sw, sh = screen.get_size()

        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((5, 12, 10, 164))
        screen.blit(overlay, (0, 0))

        title_font = pygame.font.SysFont("constantia", 62, bold=True)
        subtitle_font = pygame.font.SysFont("candara", 28, italic=True)
        row_font = pygame.font.SysFont("consolas", 22)
        header_font = pygame.font.SysFont("segoe ui", 20, bold=True)

        title = title_font.render("High Scores", True, (248, 236, 206))
        title_rect = title.get_rect(center=(sw // 2, 68))
        screen.blit(title, title_rect)

        subtitle = subtitle_font.render("Players, rankings, wins, losses, and top hands", True, (230, 220, 190))
        subtitle_rect = subtitle.get_rect(center=(sw // 2, title_rect.bottom + 20))
        screen.blit(subtitle, subtitle_rect)

        panel_w = min(1040, max(700, sw - 130))
        panel_h = min(560, max(420, sh - 210))
        panel_x = sw // 2 - panel_w // 2
        panel_y = subtitle_rect.bottom + 20
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        panel_surface = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surface.fill((14, 24, 20, 196))
        screen.blit(panel_surface, panel_rect.topleft)
        pygame.draw.rect(screen, (138, 168, 134), panel_rect, width=2, border_radius=12)

        rows = get_player_records_list(mode="single_player", limit=18)

        col_rank = panel_x + 22
        col_player = panel_x + 92
        col_wins = panel_x + 410
        col_losses = panel_x + 510
        col_winpct = panel_x + 620
        col_best_hand = panel_x + 740
        col_best_score = panel_x + 880

        header_y = panel_y + 16
        headers = [
            ("Rank", col_rank),
            ("Player", col_player),
            ("Wins", col_wins),
            ("Losses", col_losses),
            ("Win %", col_winpct),
            ("Best Hand", col_best_hand),
            ("Best Score", col_best_score),
        ]
        for text, x in headers:
            h = header_font.render(text, True, (240, 232, 205))
            screen.blit(h, (x, header_y))

        pygame.draw.line(
            screen,
            (116, 136, 112),
            (panel_x + 16, header_y + 32),
            (panel_x + panel_w - 16, header_y + 32),
            1,
        )

        if not rows:
            empty = row_font.render("No recorded games yet. Finish matches to populate rankings.", True, (228, 220, 194))
            screen.blit(empty, (panel_x + 24, panel_y + 84))
        else:
            current_name = str(getattr(getattr(app, "settings", None), "player_name", "Player")).strip() or "Player"
            row_h = 28
            max_rows = min(16, len(rows))
            for i, row in enumerate(rows[:max_rows]):
                y = panel_y + 54 + i * row_h

                name = str(row.get("player_name", "Player"))[:20]
                wins = int(row.get("wins", 0))
                losses = int(row.get("losses", 0))
                best_hand = int(row.get("high_hand", 0))
                best_score = int(row.get("best_game_score", 0))
                games = max(0, int(row.get("games_played", wins + losses)))
                win_pct = (100.0 * wins / games) if games else 0.0

                is_current = name == current_name
                if is_current:
                    stripe = pygame.Surface((panel_w - 20, row_h - 2), pygame.SRCALPHA)
                    stripe.fill((88, 116, 84, 90))
                    screen.blit(stripe, (panel_x + 10, y))

                color = (244, 240, 220) if is_current else (226, 219, 198)

                screen.blit(row_font.render(str(i + 1), True, color), (col_rank, y))
                screen.blit(row_font.render(name, True, color), (col_player, y))
                screen.blit(row_font.render(str(wins), True, color), (col_wins, y))
                screen.blit(row_font.render(str(losses), True, color), (col_losses, y))
                screen.blit(row_font.render(f"{win_pct:.1f}", True, color), (col_winpct, y))
                screen.blit(row_font.render(str(best_hand), True, color), (col_best_hand, y))
                screen.blit(row_font.render(str(best_score), True, color), (col_best_score, y))

        self.back_rect = pygame.Rect(panel_x + 20, panel_y + panel_h - 56, 180, 40)
        pygame.draw.rect(screen, (50, 76, 56), self.back_rect, border_radius=10)
        pygame.draw.rect(screen, (132, 170, 138), self.back_rect, width=1, border_radius=10)
        back_font = pygame.font.SysFont("bahnschrift", 22, bold=True)
        back_text = back_font.render("BACK", True, (235, 240, 228))
        screen.blit(back_text, back_text.get_rect(center=self.back_rect.center))

        hint_font = pygame.font.SysFont("segoe ui", 18)
        hint = hint_font.render("Esc or B to return", True, (220, 214, 194))
        screen.blit(hint, (panel_x + panel_w - hint.get_width() - 24, panel_y + panel_h - 46))
