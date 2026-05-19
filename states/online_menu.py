from __future__ import annotations

import pygame

from .base import GameStateBase


class OnlineMenuState(GameStateBase):
    def __init__(self):
        self.join_code = ""

    def handle_event(self, event, engine, assets, app):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                app.reset_stream()
                from .intro import IntroState

                return IntroState()
            if event.key == pygame.K_BACKSPACE:
                self.join_code = self.join_code[:-1]
            elif event.key == pygame.K_1:
                return self._create_room(app)
            elif event.key == pygame.K_2:
                return self._join_room(app)
            elif event.key == pygame.K_3:
                return self._quick_match(app)
            elif event.key == pygame.K_LEFT:
                app.preferred_online_ai_level = (
                    3 if app.preferred_online_ai_level == 1 else app.preferred_online_ai_level - 1
                )
            elif event.key == pygame.K_RIGHT:
                app.preferred_online_ai_level = (
                    1 if app.preferred_online_ai_level == 3 else app.preferred_online_ai_level + 1
                )
            else:
                if event.unicode and event.unicode.isalnum() and len(self.join_code) < 12:
                    self.join_code += event.unicode.upper()
        return self

    def _create_room(self, app):
        try:
            code = app.client.create_room()
            app.status_message = f"Room created: {code}. Share code, then wait for join."
            app.last_error = ""
        except Exception as exc:
            app.last_error = str(exc)
        return self

    def _join_room(self, app):
        try:
            match_id = app.client.join_room(self.join_code)
            app.current_match_id = match_id
            app.last_error = ""
            from .online_match import OnlineMatchState

            return OnlineMatchState(match_id)
        except Exception as exc:
            app.last_error = str(exc)
            return self

    def _quick_match(self, app):
        try:
            app.client.enqueue()
            match_id = app.client.trigger_pair()
            if not match_id:
                app.status_message = "Queued. Waiting for another player to pair."
                return self
            app.current_match_id = match_id
            app.last_error = ""
            from .online_match import OnlineMatchState

            return OnlineMatchState(match_id)
        except Exception as exc:
            app.last_error = str(exc)
            return self

    def update(self, engine, dt: int, app):
        return None

    def draw(self, screen, engine, assets, app):
        screen.fill((18, 28, 35))
        title_font = pygame.font.SysFont(None, 56)
        body_font = pygame.font.SysFont(None, 32)

        title = title_font.render("Online Menu", True, (245, 245, 245))
        screen.blit(title, title.get_rect(center=(screen.get_width() // 2, 80)))

        login = body_font.render(
            f"Player: {app.display_name} ({app.player_id})", True, (200, 220, 235)
        )
        screen.blit(login, login.get_rect(center=(screen.get_width() // 2, 130)))

        opts = [
            "1) Create Room",
            "2) Join Room (type code below)",
            "3) Quick Match (queue + pair)",
            f"Left/Right) Online AI pref: {app.preferred_online_ai_level}",
            "Esc) Back",
        ]
        y = 200
        for item in opts:
            line = body_font.render(item, True, (225, 225, 225))
            screen.blit(line, line.get_rect(center=(screen.get_width() // 2, y)))
            y += 46

        box = pygame.Rect(screen.get_width() // 2 - 180, y + 8, 360, 54)
        pygame.draw.rect(screen, (245, 245, 245), box, border_radius=10)
        pygame.draw.rect(screen, (80, 120, 160), box, width=2, border_radius=10)
        code_text = body_font.render(self.join_code or "ROOMCODE", True, (22, 22, 22))
        screen.blit(code_text, (box.x + 12, box.y + 12))

        if app.status_message:
            msg = body_font.render(app.status_message, True, (170, 220, 170))
            screen.blit(msg, msg.get_rect(center=(screen.get_width() // 2, box.bottom + 50)))

        if app.last_error:
            err = body_font.render(app.last_error, True, (230, 120, 120))
            screen.blit(err, err.get_rect(center=(screen.get_width() // 2, box.bottom + 92)))
