from __future__ import annotations

import pygame

from .base import GameStateBase


class OnlineLoginState(GameStateBase):
    def __init__(self):
        self.name = ""
        self.info = "Pick a display name and press Enter"

    def handle_event(self, event, engine, assets, app):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                from .intro import IntroState

                return IntroState()
            if event.key == pygame.K_BACKSPACE:
                self.name = self.name[:-1]
            elif event.key == pygame.K_RETURN:
                try:
                    result = app.client.login(self.name.strip() or "Player")
                    app.online_enabled = True
                    app.player_id = result["player_id"]
                    app.display_name = result["display_name"]
                    app.session_token = result["session_token"]
                    app.status_message = f"Logged in as {app.display_name}"
                    app.last_error = ""
                    from .online_menu import OnlineMenuState

                    return OnlineMenuState()
                except Exception as exc:
                    app.last_error = str(exc)
            else:
                if event.unicode and event.unicode.isprintable() and len(self.name) < 24:
                    self.name += event.unicode
        return self

    def update(self, engine, dt: int, app):
        return None

    def draw(self, screen, engine, assets, app):
        screen.fill((22, 34, 40))
        title_font = pygame.font.SysFont(None, 60)
        body_font = pygame.font.SysFont(None, 34)

        title = title_font.render("Play With a Friend", True, (245, 245, 245))
        screen.blit(title, title.get_rect(center=(screen.get_width() // 2, 90)))

        prompt = body_font.render(self.info, True, (210, 210, 210))
        screen.blit(prompt, prompt.get_rect(center=(screen.get_width() // 2, 170)))

        box = pygame.Rect(screen.get_width() // 2 - 250, 220, 500, 56)
        pygame.draw.rect(screen, (250, 250, 250), box, border_radius=10)
        pygame.draw.rect(screen, (90, 140, 200), box, width=2, border_radius=10)
        entry = body_font.render(self.name or "Type name...", True, (20, 20, 20))
        screen.blit(entry, (box.x + 12, box.y + 14))

        hint = body_font.render("Enter=continue  Esc=back", True, (190, 190, 190))
        screen.blit(hint, hint.get_rect(center=(screen.get_width() // 2, 320)))

        if app.last_error:
            err = body_font.render(app.last_error, True, (230, 110, 110))
            screen.blit(err, err.get_rect(center=(screen.get_width() // 2, 390)))
