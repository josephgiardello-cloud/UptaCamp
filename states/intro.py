import pygame

from assets.maine_shape import maine_shape
from bert_persona import choose_line
from settings_manager import load_settings, save_settings
from src.renderer.intro_controls_renderer import draw_intro_controls
from src.renderer.settings_modal_renderer import draw_settings_modal
from stats_manager import create_player_profile

from .base import GameStateBase


class IntroState(GameStateBase):
    def __init__(self):
        self.start_button_rect: pygame.Rect | None = None
        self.online_button_rect: pygame.Rect | None = None
        self.p2p_button_rect: pygame.Rect | None = None
        self.settings_button_rect: pygame.Rect | None = None
        self.high_scores_button_rect: pygame.Rect | None = None
        self.difficulty_buttons: dict[int, pygame.Rect] = {}
        self.dad_ai_level = 4
        self.settings_open = False
        self.settings_rects: dict[str, pygame.Rect] = {}
        self.player_name_rect: pygame.Rect | None = None
        self.player_name_editing = False
        self.settings = load_settings()

        # Keep labels local to avoid coupling intro state to old monolith globals.
        self.difficulty_descriptions = {
            1: "Random play\nEasy wins",
            2: "Monte Carlo\nMixed strategy",
            3: "Risk simulation\nHard opponent",
            4: "Gumption\nMode",
            5: "Old House\nBarnabas at the table",
        }
        self.ai_level_labels = {1: "Easy", 2: "Medium", 3: "Hard"}
        self.ui_style_labels = {
            "classic": "Classic",
            "competitive_minimal": "Competitive Minimal",
            "broadcast_table": "Broadcast Table",
            "premium_tabletop": "Premium Tabletop",
        }
        self.background_theme_labels = {
            "auto": "Classic Felt (Table)",
            "classic": "Classic Felt (Table)",
            "wharf": "Wharf Boards (Tony)",
            "dark_shadows": "Dark Shadows (Board)",
        }

    def _visible_difficulty_levels(self, app) -> list[tuple[int, str]]:
        levels: list[tuple[int, str]] = [
            (1, "Easy"),
            (2, "Medium"),
            (3, "Hard"),
            (4, "Bert"),
            (5, "Barnabas"),
        ]
        # Migrate legacy difficulty snapshots where level 6 represented Barnabas.
        if self.dad_ai_level >= 6:
            self.dad_ai_level = 5

        if self.dad_ai_level not in {lvl for lvl, _ in levels}:
            self.dad_ai_level = 5
        return levels

    def handle_event(self, event, engine, assets, app):
        if event.type == pygame.KEYDOWN and self.player_name_editing and not self.settings_open:
            if event.key == pygame.K_ESCAPE:
                self.player_name_editing = False
                self._play_audio(app, "card")
                return self
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.player_name_editing = False
                self.settings.player_name = (str(self.settings.player_name).strip() or "Player")[
                    :24
                ]
                save_settings(self.settings)
                try:
                    create_player_profile(self.settings.player_name)
                except Exception:
                    pass
                self._play_audio(app, "score")
                return self
            if event.key == pygame.K_BACKSPACE:
                self.settings.player_name = str(self.settings.player_name)[:-1]
                return self

            ch = getattr(event, "unicode", "")
            if (
                ch
                and ch.isprintable()
                and not ch.isspace()
                and len(str(self.settings.player_name)) < 24
            ):
                self.settings.player_name = f"{self.settings.player_name}{ch}"
                return self
            if ch == " " and len(str(self.settings.player_name)) < 24:
                self.settings.player_name = f"{self.settings.player_name} "
                return self

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and self.settings_open:
            self.settings_open = False
            self._play_audio(app, "card")
            return self

        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._play_audio(app, "score")
            self._speak_event(app, "game_start")
            from .deal import DealState

            return DealState(dad_ai_level=self.dad_ai_level)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_h:
            self._play_audio(app, "card")
            from .high_scores import HighScoresState

            return HighScoresState()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_o:
            self._play_audio(app, "card")
            from .online_login import OnlineLoginState

            return OnlineLoginState()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_p:
            self._play_audio(app, "card")
            from .p2p_lobby import P2PLobbyState

            return P2PLobbyState()
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.settings_open:
                self._handle_settings_click(event.pos, app)
                return self

            if self.player_name_rect is not None and self.player_name_rect.collidepoint(event.pos):
                self.player_name_editing = True
                self._play_audio(app, "card")
                return self
            self.player_name_editing = False

            for level, rect in self.difficulty_buttons.items():
                if rect.collidepoint(event.pos):
                    self.dad_ai_level = int(level)
                    self._play_audio(app, "score")
                    self._speak_event(app, "level_selected")
                    if level in (1, 2, 3):
                        app.preferred_online_ai_level = level
                        self.settings.online_ai_level = level
                        save_settings(self.settings)
                    return self

            if self.start_button_rect is not None and self.start_button_rect.collidepoint(
                event.pos
            ):
                self._play_audio(app, "score")
                self._speak_event(app, "game_start")
                from .deal import DealState

                return DealState(dad_ai_level=self.dad_ai_level)
            if self.online_button_rect is not None and self.online_button_rect.collidepoint(
                event.pos
            ):
                self._play_audio(app, "card")
                from .online_login import OnlineLoginState

                return OnlineLoginState()
            if self.p2p_button_rect is not None and self.p2p_button_rect.collidepoint(event.pos):
                self._play_audio(app, "card")
                from .p2p_lobby import P2PLobbyState

                return P2PLobbyState()
            if self.settings_button_rect is not None and self.settings_button_rect.collidepoint(
                event.pos
            ):
                self.settings_open = True
                self._play_audio(app, "card")
            if (
                self.high_scores_button_rect is not None
                and self.high_scores_button_rect.collidepoint(event.pos)
            ):
                self._play_audio(app, "card")
                from .high_scores import HighScoresState

                return HighScoresState()
        return self

    def update(self, engine, dt, app):
        if hasattr(app, "settings"):
            app.settings = self.settings
        app.volume = self.settings.volume
        app.animations_enabled = self.settings.animations_enabled
        app.preferred_online_ai_level = self.settings.online_ai_level
        self._visible_difficulty_levels(app)

    def _play_audio(self, app, name: str) -> None:
        audio = getattr(app, "audio", None)
        if audio is None:
            return
        try:
            audio.play(name)
        except Exception:
            return

    def _speak_event(self, app, event: str) -> None:
        voice = getattr(app, "voice", None)
        if voice is None:
            return

        if self.dad_ai_level in (1, 2, 3):
            if event == "level_selected":
                level_name = self.ai_level_labels.get(
                    self.dad_ai_level, f"Level {self.dad_ai_level}"
                )
                line = f"{level_name} difficulty selected."
            elif event == "game_start":
                line = "Cards are on the table. Good luck."
            else:
                line = ""
        else:
            line = choose_line(
                event,
                style=self.settings.bert_voice_style,
                dad_ai_level=self.dad_ai_level,
                context=None,
            )
        if not line:
            return
        try:
            voice.speak_bert(
                line,
                dad_ai_level=self.dad_ai_level,
                bypass_cooldown=True,
                voice_style=self.settings.bert_voice_style,
            )
        except Exception:
            return

    def _cycle_value(self, values: list[str], current: str, direction: int) -> str:
        if current not in values:
            return values[0]
        idx = values.index(current)
        return values[(idx + direction) % len(values)]

    def _handle_settings_click(self, pos: tuple[int, int], app) -> None:
        rects = self.settings_rects
        volume_rect = rects.get("settings_volume_rect")
        if volume_rect is not None and volume_rect.collidepoint(pos):
            ratio = (pos[0] - volume_rect.x) / max(1, volume_rect.width)
            self.settings.volume = max(0.0, min(1.0, ratio))
            save_settings(self.settings)
            return

        anim_rect = rects.get("settings_anim_rect")
        if anim_rect is not None and anim_rect.collidepoint(pos):
            self.settings.animations_enabled = not self.settings.animations_enabled
            save_settings(self.settings)
            return

        voice_rect = rects.get("settings_voice_rect")
        if voice_rect is not None and voice_rect.collidepoint(pos):
            self.settings.bert_voice_enabled = not self.settings.bert_voice_enabled
            voice = getattr(app, "voice", None)
            if voice is not None and not self.settings.bert_voice_enabled:
                try:
                    voice.stop()
                except Exception:
                    pass
            save_settings(self.settings)
            return

        ai_left = rects.get("settings_ai_left_rect")
        ai_right = rects.get("settings_ai_right_rect")
        if ai_left is not None and ai_left.collidepoint(pos):
            self.settings.online_ai_level = (
                3 if self.settings.online_ai_level == 1 else self.settings.online_ai_level - 1
            )
            app.preferred_online_ai_level = self.settings.online_ai_level
            save_settings(self.settings)
            return
        if ai_right is not None and ai_right.collidepoint(pos):
            self.settings.online_ai_level = (
                1 if self.settings.online_ai_level == 3 else self.settings.online_ai_level + 1
            )
            app.preferred_online_ai_level = self.settings.online_ai_level
            save_settings(self.settings)
            return

        style_left = rects.get("settings_style_left_rect")
        style_right = rects.get("settings_style_right_rect")
        style_values = list(self.ui_style_labels.keys())
        if style_left is not None and style_left.collidepoint(pos):
            self.settings.ui_style = self._cycle_value(style_values, self.settings.ui_style, -1)
            save_settings(self.settings)
            return
        if style_right is not None and style_right.collidepoint(pos):
            self.settings.ui_style = self._cycle_value(style_values, self.settings.ui_style, 1)
            save_settings(self.settings)
            return

    def draw(self, screen, engine, assets, app):
        bg = (
            assets.get_background("welcome_bg.png")
            or assets.get_background("table.jpg")
            or assets.get_background("table.png")
        )
        if bg:
            scaled = pygame.transform.smoothscale(bg, screen.get_size())
            screen.blit(scaled, (0, 0))
        else:
            screen.fill((34, 139, 34))

        sw, sh = screen.get_size()
        mouse_pos = pygame.mouse.get_pos()

        vignette = pygame.Surface((sw, sh), pygame.SRCALPHA)
        pygame.draw.rect(vignette, (8, 20, 14, 120), vignette.get_rect())
        screen.blit(vignette, (0, 0))

        title_font = pygame.font.SysFont("constantia", 78, bold=True)
        subtitle_font = pygame.font.SysFont("candara", 30, italic=True)

        title = title_font.render("Upta Camp Cribbage", True, (248, 236, 206))
        title_shadow = title_font.render("Upta Camp Cribbage", True, (0, 0, 0))
        title_rect = title.get_rect(center=(sw // 2, 84))
        screen.blit(title_shadow, (title_rect.x + 2, title_rect.y + 2))
        screen.blit(title, title_rect)

        subtitle = subtitle_font.render(
            "Dockside cards, mountain air, and one stubborn Bert.", True, (230, 220, 190)
        )
        subtitle_rect = subtitle.get_rect(center=(sw // 2, title_rect.bottom + 18))
        screen.blit(subtitle, subtitle_rect)

        name_label_font = pygame.font.SysFont("segoe ui", 20, bold=True)
        name_value_font = pygame.font.SysFont("segoe ui", 24)
        name_label = name_label_font.render("Player Name", True, (236, 224, 198))
        name_label_rect = name_label.get_rect(center=(sw // 2, subtitle_rect.bottom + 20))
        screen.blit(name_label, name_label_rect)

        self.player_name_rect = pygame.Rect(sw // 2 - 190, name_label_rect.bottom + 6, 380, 40)
        name_hover = self.player_name_rect.collidepoint(mouse_pos)
        name_active = self.player_name_editing
        box_fill = (56, 49, 42, 210) if (name_active or name_hover) else (42, 36, 31, 200)
        name_box = pygame.Surface(
            (self.player_name_rect.width, self.player_name_rect.height), pygame.SRCALPHA
        )
        name_box.fill(box_fill)
        screen.blit(name_box, self.player_name_rect)
        pygame.draw.rect(
            screen,
            (255, 235, 172) if name_active else (210, 190, 148),
            self.player_name_rect,
            width=2,
            border_radius=10,
        )
        shown_name = str(self.settings.player_name or "Player")
        if name_active:
            shown_name = f"{shown_name}|"
        name_text = name_value_font.render(shown_name, True, (248, 241, 223))
        screen.blit(
            name_text,
            (
                self.player_name_rect.x + 12,
                self.player_name_rect.centery - name_text.get_height() // 2,
            ),
        )

        helper_font = pygame.font.SysFont("segoe ui", 16)
        helper = helper_font.render(
            "Click to edit, Enter to save",
            True,
            (214, 201, 176),
        )
        helper_rect = helper.get_rect(center=(sw // 2, self.player_name_rect.bottom + 14))
        screen.blit(helper, helper_rect)

        layout = draw_intro_controls(
            screen=screen,
            sw=sw,
            sh=sh,
            mouse_pos=mouse_pos,
            dad_ai_level=self.dad_ai_level,
            difficulty_options=self._visible_difficulty_levels(app),
            difficulty_descriptions=self.difficulty_descriptions,
            maine_shape=maine_shape,
            locked_levels=set(),
        )

        self.difficulty_buttons = layout["difficulty_buttons"]
        self.start_button_rect = layout["start_btn_rect"]
        self.online_button_rect = layout["online_btn_rect"]
        self.settings_button_rect = layout["settings_btn_rect"]
        self.high_scores_button_rect = layout["high_scores_btn_rect"]

        button_gap = 12
        # Prefer side-by-side action buttons to preserve vertical room for helper text.
        p2p_x = self.online_button_rect.left - self.online_button_rect.width - button_gap
        if p2p_x >= 24:
            self.p2p_button_rect = pygame.Rect(
                p2p_x,
                self.online_button_rect.y,
                self.online_button_rect.width,
                self.online_button_rect.height,
            )
        else:
            # Fallback for narrow windows: stack below online button.
            self.p2p_button_rect = pygame.Rect(
                self.online_button_rect.left,
                self.online_button_rect.bottom + button_gap,
                self.online_button_rect.width,
                self.online_button_rect.height,
            )
        p2p_hover = self.p2p_button_rect.collidepoint(mouse_pos)
        p2p_draw = self.p2p_button_rect.move(0, -2 if p2p_hover else 0)
        pygame.draw.rect(screen, (0, 0, 0, 80), p2p_draw.move(0, 5), border_radius=10)
        pygame.draw.rect(
            screen, (48, 86, 58) if not p2p_hover else (60, 102, 72), p2p_draw, border_radius=10
        )
        pygame.draw.rect(screen, (114, 178, 126), p2p_draw, width=1, border_radius=10)

        p2p_font = pygame.font.SysFont("bahnschrift", 24, bold=True)
        p2p_text = p2p_font.render("DIRECT P2P", True, (226, 244, 230))
        p2p_rect = p2p_text.get_rect(center=p2p_draw.center)
        screen.blit(p2p_text, p2p_rect)

        if self.settings_open:
            self.settings_rects = draw_settings_modal(
                screen=screen,
                sw=sw,
                sh=sh,
                settings=self.settings,
                settings_text_active=None,
                ai_level_labels=self.ai_level_labels,
                ui_style_labels=self.ui_style_labels,
                background_theme_labels=self.background_theme_labels,
            )
        else:
            self.settings_rects = {}

        help_font = pygame.font.SysFont("segoe ui", 24)
        hint = help_font.render(
            "Enter/Space = local  |  H = high scores  |  O = online  |  P = direct P2P  |  Esc = close settings",
            True,
            (244, 236, 214),
        )
        action_row_bottom = max(self.online_button_rect.bottom, self.p2p_button_rect.bottom)
        preferred_hint_y = action_row_bottom + 14
        hint_y = preferred_hint_y
        max_hint_y = sh - hint.get_height() - 8
        if hint_y > max_hint_y:
            # If space below actions is tight, place hint in the gap below the start button.
            hint_y = min(max_hint_y, self.start_button_rect.bottom + 8)
        hint_rect = hint.get_rect(topleft=(sw // 2 - hint.get_width() // 2, max(8, hint_y)))
        screen.blit(hint, hint_rect)
