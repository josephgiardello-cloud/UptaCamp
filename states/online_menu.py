from __future__ import annotations

import pygame

from .base import GameStateBase


class OnlineMenuState(GameStateBase):
    def __init__(self):
        self.join_code = ""
        self.join_mode = False
        self.host_rect = None
        self.join_rect = None
        self.quick_rect = None
        self.copy_rect = None
        self.copy_toast_text = ""
        self.copy_toast_until_ms = 0

    def _show_copy_toast(self, text: str) -> None:
        self.copy_toast_text = text
        self.copy_toast_until_ms = pygame.time.get_ticks() + 2000

    def _copy_to_clipboard(self, text: str) -> bool:
        try:
            if not pygame.get_init():
                return False
            if not pygame.scrap.get_init():
                pygame.scrap.init()
            pygame.scrap.put(pygame.SCRAP_TEXT, text.encode("utf-8"))
            return True
        except Exception:
            try:
                # Tk fallback when pygame.scrap is unavailable.
                import tkinter as tk

                root = tk.Tk()
                root.withdraw()
                root.clipboard_clear()
                root.clipboard_append(text)
                root.update()
                root.destroy()
                return True
            except Exception:
                return False

    def handle_event(self, event, engine, assets, app):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                app.reset_stream()
                from .intro import IntroState

                return IntroState()

            if event.key in (pygame.K_h, pygame.K_1):
                self.join_mode = False
                return self._create_room(app)
            elif event.key in (pygame.K_j, pygame.K_2):
                self.join_mode = True
                app.status_message = "Enter your friend's code, then press Enter to join."
                return self
            elif event.key in (pygame.K_m, pygame.K_3):
                self.join_mode = False
                return self._quick_match(app)
            elif event.key == pygame.K_c and self.join_code:
                if self._copy_to_clipboard(self.join_code):
                    app.status_message = f"Code copied: {self.join_code}"
                    app.last_error = ""
                    self._show_copy_toast("Copied!")
                else:
                    app.last_error = "Could not copy automatically. Share code manually."
                    self._show_copy_toast("Copy failed")
            elif event.key == pygame.K_LEFT:
                app.preferred_online_ai_level = (
                    3 if app.preferred_online_ai_level == 1 else app.preferred_online_ai_level - 1
                )
            elif event.key == pygame.K_RIGHT:
                app.preferred_online_ai_level = (
                    1 if app.preferred_online_ai_level == 3 else app.preferred_online_ai_level + 1
                )
            elif self.join_mode and event.key == pygame.K_BACKSPACE:
                self.join_code = self.join_code[:-1]
            elif self.join_mode and event.key == pygame.K_RETURN:
                return self._join_room(app)
            else:
                if (
                    self.join_mode
                    and event.unicode
                    and event.unicode.isalnum()
                    and len(self.join_code) < 12
                ):
                    self.join_code += event.unicode.upper()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.host_rect is not None and self.host_rect.collidepoint(event.pos):
                self.join_mode = False
                return self._create_room(app)
            if self.join_rect is not None and self.join_rect.collidepoint(event.pos):
                self.join_mode = True
                app.status_message = "Enter your friend's code, then press Enter to join."
                return self
            if self.quick_rect is not None and self.quick_rect.collidepoint(event.pos):
                self.join_mode = False
                return self._quick_match(app)
            if (
                self.copy_rect is not None
                and self.copy_rect.collidepoint(event.pos)
                and self.join_code
            ):
                if self._copy_to_clipboard(self.join_code):
                    app.status_message = f"Code copied: {self.join_code}"
                    app.last_error = ""
                    self._show_copy_toast("Copied!")
                else:
                    app.last_error = "Could not copy automatically. Share code manually."
                    self._show_copy_toast("Copy failed")
        return self

    def _create_room(self, app):
        try:
            code = app.client.create_room()
            self.join_code = code
            app.status_message = f"Share this code with your friend: {code}"
            app.last_error = ""
        except Exception as exc:
            app.last_error = str(exc)
        return self

    def _join_room(self, app):
        if not self.join_code.strip():
            app.last_error = "Enter a room code first"
            return self
        try:
            match_id = app.client.join_room(self.join_code)
            app.current_match_id = match_id
            app.status_message = "Connected. Starting match..."
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
                app.status_message = "Looking for an opponent..."
                return self
            app.current_match_id = match_id
            app.status_message = "Opponent found. Starting match..."
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
        hint_font = pygame.font.SysFont(None, 28)

        title = title_font.render("Play Online", True, (245, 245, 245))
        screen.blit(title, title.get_rect(center=(screen.get_width() // 2, 80)))

        login = body_font.render(f"Signed in as: {app.display_name}", True, (200, 220, 235))
        screen.blit(login, login.get_rect(center=(screen.get_width() // 2, 130)))

        button_w, button_h = 280, 56
        center_x = screen.get_width() // 2
        self.host_rect = pygame.Rect(center_x - button_w // 2, 185, button_w, button_h)
        self.join_rect = pygame.Rect(center_x - button_w // 2, 255, button_w, button_h)
        self.quick_rect = pygame.Rect(center_x - button_w // 2, 325, button_w, button_h)

        pygame.draw.rect(screen, (48, 92, 126), self.host_rect, border_radius=10)
        pygame.draw.rect(screen, (170, 215, 245), self.host_rect, width=2, border_radius=10)
        pygame.draw.rect(
            screen,
            (72, 110, 74) if self.join_mode else (48, 92, 126),
            self.join_rect,
            border_radius=10,
        )
        pygame.draw.rect(screen, (170, 215, 245), self.join_rect, width=2, border_radius=10)
        pygame.draw.rect(screen, (66, 84, 120), self.quick_rect, border_radius=10)
        pygame.draw.rect(screen, (170, 215, 245), self.quick_rect, width=2, border_radius=10)

        host_text = body_font.render("Host Friend Match", True, (245, 245, 245))
        join_text = body_font.render("Join With Code", True, (245, 245, 245))
        quick_text = body_font.render("Quick Match", True, (245, 245, 245))
        screen.blit(host_text, host_text.get_rect(center=self.host_rect.center))
        screen.blit(join_text, join_text.get_rect(center=self.join_rect.center))
        screen.blit(quick_text, quick_text.get_rect(center=self.quick_rect.center))

        box = pygame.Rect(screen.get_width() // 2 - 180, 412, 360, 54)
        self.copy_rect = pygame.Rect(box.right + 10, box.y, 130, box.height)
        pygame.draw.rect(screen, (245, 245, 245), box, border_radius=10)
        pygame.draw.rect(
            screen,
            (80, 170, 120) if self.join_mode else (80, 120, 160),
            box,
            width=2,
            border_radius=10,
        )
        code_text = body_font.render(self.join_code or "ENTER CODE", True, (22, 22, 22))
        screen.blit(code_text, (box.x + 12, box.y + 12))

        can_copy = bool(self.join_code)
        copy_fill = (70, 120, 78) if can_copy else (70, 70, 70)
        copy_border = (176, 225, 188) if can_copy else (140, 140, 140)
        pygame.draw.rect(screen, copy_fill, self.copy_rect, border_radius=10)
        pygame.draw.rect(screen, copy_border, self.copy_rect, width=2, border_radius=10)
        copy_label = body_font.render("Copy Code", True, (245, 245, 245))
        screen.blit(copy_label, copy_label.get_rect(center=self.copy_rect.center))

        controls = hint_font.render(
            "H=Host  J=Join  M=Quick Match  C=Copy code  |  Enter=Join code  |  Esc=Back",
            True,
            (205, 205, 205),
        )
        screen.blit(controls, controls.get_rect(center=(center_x, 498)))

        ai_pref = hint_font.render(
            f"Optional AI fallback: Left/Right to set ({app.preferred_online_ai_level})",
            True,
            (180, 200, 220),
        )
        screen.blit(ai_pref, ai_pref.get_rect(center=(center_x, 534)))

        if app.status_message:
            msg = body_font.render(app.status_message, True, (170, 220, 170))
            screen.blit(msg, msg.get_rect(center=(screen.get_width() // 2, box.bottom + 86)))

        if app.last_error:
            err = body_font.render(app.last_error, True, (230, 120, 120))
            screen.blit(err, err.get_rect(center=(screen.get_width() // 2, box.bottom + 124)))

        if self.copy_toast_text and pygame.time.get_ticks() < self.copy_toast_until_ms:
            toast = pygame.Rect(screen.get_width() - 190, 18, 170, 44)
            pygame.draw.rect(screen, (34, 74, 48), toast, border_radius=10)
            pygame.draw.rect(screen, (150, 220, 170), toast, width=2, border_radius=10)
            toast_text = hint_font.render(self.copy_toast_text, True, (245, 245, 245))
            screen.blit(toast_text, toast_text.get_rect(center=toast.center))
