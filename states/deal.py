import pygame

from animations import EffectsManager
from bert_persona import choose_line
from cards import Card
from cards import parse_card_label
from stats_manager import record_difficulty_win
from src.renderer import BoardRenderer, RenderingContext
from states.intro import IntroState

from .base import GameStateBase


class DealState(GameStateBase):
    def __init__(self, dad_ai_level: int = 5):
        self.dealt = False
        self.dad_ai_level = int(dad_ai_level)
        self.back_button_rect: pygame.Rect | None = None
        self.go_button_rect: pygame.Rect | None = None
        self.next_round_rect: pygame.Rect | None = None
        self.player_card_rects: list[tuple[int, pygame.Rect]] = []
        self.ai_card_rects: list[tuple[int, pygame.Rect]] = []
        self.selected_indices: list[int] = []
        self.phase = "discard"
        self.status_message = "Select 2 cards to discard to the crib."
        self.end_hand_summary: dict[str, object] | None = None
        self.game_result_recorded = False
        self.game_over_voice_played = False
        self.ai_action_cooldown_ms = 320
        self.effects = EffectsManager()

    @staticmethod
    def _draw_fallback_back(screen, rect: pygame.Rect) -> None:
        back_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        for y in range(rect.height):
            t = y / max(1, rect.height - 1)
            r = int(24 + 24 * t)
            g = int(45 + 30 * t)
            b = int(78 + 36 * t)
            pygame.draw.line(back_surface, (r, g, b, 255), (0, y), (rect.width, y))

        inset = pygame.Rect(8, 8, rect.width - 16, rect.height - 16)
        pygame.draw.rect(back_surface, (230, 216, 184, 220), inset, width=2, border_radius=10)
        center = (rect.width // 2, rect.height // 2)
        pygame.draw.circle(back_surface, (232, 220, 188, 120), center, 20, width=2)
        pygame.draw.circle(back_surface, (198, 182, 146, 90), center, 30, width=1)

        for y in range(16, rect.height - 16, 12):
            pygame.draw.line(back_surface, (34, 64, 104, 110), (14, y), (rect.width - 14, y), 1)

        screen.blit(back_surface, rect.topleft)

    def _player_has_valid_pegging_play(self, engine) -> bool:
        if self.phase != "pegging":
            return False
        if int(getattr(engine.state, "player_turn", 0)) != 0:
            return False
        try:
            return len(list(engine.get_valid_moves())) > 0
        except Exception:
            return False

    def _instruction_for_phase(self, engine) -> str:
        if self.phase == "discard":
            selected = len(self.selected_indices)
            if selected == 0:
                return "Discard 2 cards to the crib."
            if selected == 1:
                return "Choose 1 more card to discard."
            return "Discarding cards..."
        if self.phase == "pegging":
            if int(getattr(engine.state, "player_turn", 0)) == 0:
                if self._player_has_valid_pegging_play(engine):
                    return "Pegging: play a card up to 31."
                return "Pegging: no valid card, press Go."
            return "Pegging: Bert is playing."
        if self.phase == "counting":
            return "Counting hands..."
        if self.phase == "end":
            return "Hand complete. Review scoring below."
        return "Play cribbage."

    @staticmethod
    def _line_items(breakdown: object, limit: int = 2) -> str:
        if not isinstance(breakdown, list) or not breakdown:
            return "-"
        rendered: list[str] = []
        for row in breakdown[:limit]:
            if not isinstance(row, (list, tuple)) or len(row) < 3:
                continue
            name = str(row[0])
            pts = str(row[2])
            rendered.append(f"{name} (+{pts})")
        return ", ".join(rendered) if rendered else "-"

    @staticmethod
    def _asset_key_for_card(card: Card | str | object) -> str:
        rank_map = {
            "A": "ace",
            "J": "jack",
            "Q": "queen",
            "K": "king",
        }
        if hasattr(card, "rank") and hasattr(card, "suit"):
            raw_rank = str(getattr(card, "rank", ""))
            raw_suit = str(getattr(card, "suit", ""))
        else:
            raw_rank, raw_suit = parse_card_label(str(card))

        upper_rank = raw_rank.upper()
        rank = rank_map.get(upper_rank, raw_rank.lower())
        suit = raw_suit.lower()
        return f"{rank}_of_{suit}"

    def handle_event(self, event, engine, assets, app):
        if event.type != pygame.MOUSEBUTTONDOWN:
            return self

        if self.back_button_rect is not None and self.back_button_rect.collidepoint(event.pos):
            self._play_audio(app, "card")
            return IntroState()

        phase = self.phase
        if phase == "discard":
            clicked_idx = self._clicked_player_index(event.pos)
            if clicked_idx is not None:
                self._handle_discard_click(clicked_idx, engine, app)
            return self

        if phase == "pegging" and int(getattr(engine.state, "player_turn", 0)) == 0:
            if self.go_button_rect is not None and self.go_button_rect.collidepoint(event.pos):
                if not self._player_has_valid_pegging_play(engine):
                    engine.pass_pegging_turn(0)
                    self._play_audio(app, "card")
                    self._sync_from_engine(engine)
                return self

            clicked_idx = self._clicked_player_index(event.pos)
            if clicked_idx is not None:
                self._handle_player_pegging_click(clicked_idx, engine, app)
            return self

        if phase == "end" and self.next_round_rect is not None and self.next_round_rect.collidepoint(event.pos):
            try:
                engine.start_next_round()
                engine.state.dad_ai_level = self.dad_ai_level
                self.selected_indices.clear()
                self.end_hand_summary = None
                self._sync_from_engine(engine)
                self._play_audio(app, "score")
            except Exception:
                return self
        return self

    def _clicked_player_index(self, pos: tuple[int, int]) -> int | None:
        for idx, rect in reversed(self.player_card_rects):
            if rect.collidepoint(pos):
                return idx
        return None

    def _play_audio(self, app, sound_name: str) -> None:
        audio = getattr(app, "audio", None)
        if audio is None:
            return
        try:
            audio.play(sound_name)
        except Exception:
            return

    def _handle_discard_click(self, card_idx: int, engine, app) -> None:
        if card_idx in self.selected_indices:
            self.selected_indices.remove(card_idx)
            self._play_audio(app, "card")
            return

        self.selected_indices.append(card_idx)
        self.selected_indices = sorted(set(self.selected_indices))
        self._play_audio(app, "card")
        if len(self.selected_indices) < 2:
            return

        selected = list(self.selected_indices[:2])
        self.selected_indices.clear()
        try:
            ok = bool(engine.handle_discard(selected))
        except Exception:
            ok = False
        if ok:
            self._play_audio(app, "score")
            self._sync_from_engine(engine)
            return
        self.status_message = "Discard selection failed. Try a different pair."

    def _handle_player_pegging_click(self, card_idx: int, engine, app) -> None:
        start_rect = None
        for idx, rect in self.player_card_rects:
            if idx == card_idx:
                start_rect = rect
                break

        pile_before = len(list(getattr(engine.state, "pegging_pile", [])))
        try:
            points = int(engine.play_pegging_card(0, card_idx) or 0)
        except Exception:
            return

        self._play_audio(app, "card")
        self._sync_from_engine(engine)
        pile_after = len(list(getattr(engine.state, "pegging_pile", [])))

        if start_rect is not None and pile_after >= pile_before:
            player_hand = list(getattr(engine.state, "player_hand", []))
            preview = player_hand[min(card_idx, max(0, len(player_hand) - 1))] if player_hand else None
            if preview is not None:
                key = self._asset_key_for_card(preview)
                self._try_add_flight(start_rect, key, app)

        if points > 0 and start_rect is not None:
            self.effects.add_score_popup(
                f"+{points}",
                (start_rect.centerx, start_rect.top - 8),
                color=(245, 241, 230),
            )
            self.effects.trigger_shake(4, 160)

    def _sync_from_engine(self, engine) -> None:
        if not hasattr(engine, "state"):
            return
        self.phase = str(getattr(engine.state, "phase", self.phase))
        engine_msg = str(getattr(engine.state, "message", "")).strip()
        if engine_msg:
            self.status_message = engine_msg

    def _try_add_flight(self, from_rect: pygame.Rect, card_key: str, app) -> None:
        assets = getattr(app, "assets", None)
        if assets is None:
            return
        img = assets.get_card_image(card_key)
        if img is None:
            return
        target = (from_rect.centerx, max(220, from_rect.centery - 180))
        self.effects.add_card_flight(img, from_rect.center, target, duration_ms=260)

    def update(self, engine, dt, app):
        self.effects.update(max(0, int(dt)))

        if not self.dealt:
            player_name = str(getattr(getattr(app, "settings", None), "player_name", "Player"))
            if hasattr(engine, "start_new_game") and hasattr(engine, "state"):
                try:
                    engine.start_new_game(player_name=player_name, opponent_type="Bert")
                    engine.state.dad_ai_level = self.dad_ai_level
                except Exception:
                    pass
                self._sync_from_engine(engine)

            self.dealt = True
            self._play_audio(app, "card")

            voice = getattr(app, "voice", None)
            settings = getattr(app, "settings", None)
            if voice is not None and settings is not None:
                style = str(getattr(settings, "bert_voice_style", "downeast"))
                line = choose_line("cards_dealt", style=style, dad_ai_level=5, context=None)
                if line:
                    try:
                        voice.speak_bert(
                            line,
                            dad_ai_level=5,
                            bypass_cooldown=True,
                            voice_style=style,
                        )
                    except Exception:
                        pass

        self._sync_from_engine(engine)

        if self.phase == "pegging" and int(getattr(engine.state, "player_turn", 0)) == 1:
            self.ai_action_cooldown_ms = max(0, self.ai_action_cooldown_ms - int(dt))
            if self.ai_action_cooldown_ms == 0:
                valid = []
                try:
                    valid = list(engine.get_valid_moves())
                except Exception:
                    valid = []

                if valid:
                    ai_idx = int(valid[0])
                    ai_cards = list(getattr(engine.state, "ai_hand", []))
                    key = None
                    if 0 <= ai_idx < len(ai_cards):
                        key = self._asset_key_for_card(ai_cards[ai_idx])

                    points = int(engine.play_pegging_card(1, ai_idx) or 0)
                    self._play_audio(app, "card")
                    if points > 0:
                        self.effects.add_score_popup(
                            f"+{points}",
                            (screen_center_x(app), 210),
                            color=(255, 201, 187),
                        )
                    if key is not None and self.ai_card_rects:
                        source_rect = self.ai_card_rects[min(ai_idx, len(self.ai_card_rects) - 1)][1]
                        self._try_add_flight(source_rect, key, app)
                else:
                    engine.pass_pegging_turn(1)

                self.ai_action_cooldown_ms = 350
                self._sync_from_engine(engine)
        else:
            self.ai_action_cooldown_ms = 320

        if self.phase == "counting":
            try:
                result = engine.end_hand_counting()
                if isinstance(result, dict):
                    self.end_hand_summary = {
                        "player": int(result.get("player", 0)),
                        "ai": int(result.get("ai", 0)),
                        "crib": int(result.get("crib", 0)),
                        "player_breakdown": list(result.get("player_breakdown", [])),
                        "ai_breakdown": list(result.get("ai_breakdown", [])),
                        "crib_breakdown": list(result.get("crib_breakdown", [])),
                    }
                self._play_audio(app, "score")
            except Exception:
                pass
            self._sync_from_engine(engine)

        winner = getattr(engine.state, "winner", None)
        if winner is not None and not self.game_over_voice_played:
            voice = getattr(app, "voice", None)
            settings = getattr(app, "settings", None)
            if voice is not None and settings is not None:
                style = str(getattr(settings, "bert_voice_style", "downeast"))
                event = "bert_won" if int(winner) == 1 else "player_won"
                context = {
                    "player_score": int(getattr(engine.state, "scores", [0, 0])[0]),
                    "bert_score": int(getattr(engine.state, "scores", [0, 0])[1]),
                }
                line = choose_line(event, style=style, dad_ai_level=self.dad_ai_level, context=context)
                if line:
                    try:
                        voice.speak_bert(
                            line,
                            dad_ai_level=self.dad_ai_level,
                            bypass_cooldown=True,
                            voice_style=style,
                        )
                    except Exception:
                        pass
            self.game_over_voice_played = True

        if (
            winner is not None
            and not self.game_result_recorded
            and self.dad_ai_level == 5
            and int(winner) == 0
        ):
            player_name = str(getattr(getattr(app, "settings", None), "player_name", "Player")).strip() or "Player"
            record_difficulty_win(player_name, "old_house")
            self.game_result_recorded = True

    def draw(self, screen, engine, assets, app):
        settings = getattr(app, "settings", None)
        ui_style = str(getattr(settings, "ui_style", "classic"))
        background_theme = str(getattr(settings, "background_theme", "auto"))
        if self.dad_ai_level == 1:
            background_theme = "oos_camper"
        if self.dad_ai_level in (2, 3):
            background_theme = "tree_path_bg"
        if self.dad_ai_level == 4:
            background_theme = "wharf"
        if self.dad_ai_level == 5:
            background_theme = "old_house"
        player_name = str(getattr(settings, "player_name", "Player"))

        renderer = BoardRenderer(
            RenderingContext(
                screen=screen,
                assets=assets,
                ui_style=ui_style,
                background_theme=background_theme,
            )
        )
        renderer.draw_background()
        instruction_message = self._instruction_for_phase(engine)
        renderer.draw_board(
            {
            "message": instruction_message,
                "dealer": int(getattr(engine.state, "dealer", 0)),
                "scores": list(getattr(engine.state, "scores", [0, 0])),
                "dad_ai_level": self.dad_ai_level,
                "player_name": player_name,
                "crib_count": len(list(getattr(engine.state, "crib", []))),
                "starter_card": getattr(engine.state, "starter_card", None),
                "card_images": dict(getattr(assets, "card_images", {})),
                "phase": self.phase,
            }
        )

        shake_x, shake_y = self.effects.shake_offset()
        sw, sh = screen.get_width(), screen.get_height()
        card_w, card_h = 120, 180
        playfield = BoardRenderer._playfield_rect(screen)
        top_y = playfield.top + 48
        bot_y = playfield.bottom - card_h - 10
        player_hand = list(getattr(engine.state, "player_hand", []))
        ai_hand = list(getattr(engine.state, "ai_hand", []))

        left_margin = playfield.left + 8
        right_reserve = 330
        usable_width = max(card_w, playfield.width - 16 - right_reserve)
        spacing = min((usable_width - card_w) // max(1, len(player_hand) - 1), card_w + 12)
        start_x = left_margin

        label_font = pygame.font.SysFont("segoe ui", 24, bold=True)
        label_color = (244, 236, 210)
        shadow_color = (16, 12, 8)
        opp_label = label_font.render("Opponent Hand", True, label_color)
        player_label = label_font.render(f"{player_name} Hand", True, label_color)
        opp_label_pos = (start_x, top_y + card_h + 2)
        player_label_pos = (start_x, bot_y - 34)
        screen.blit(label_font.render("Opponent Hand", True, shadow_color), (opp_label_pos[0] + 2, opp_label_pos[1] + 2))
        screen.blit(opp_label, opp_label_pos)
        screen.blit(label_font.render(f"{player_name} Hand", True, shadow_color), (player_label_pos[0] + 2, player_label_pos[1] + 2))
        screen.blit(player_label, player_label_pos)

        back_img = assets.get_card_image("back") or getattr(assets, "card_back", None)
        self.ai_card_rects = []
        for i, _ in enumerate(ai_hand):
            x = start_x + i * spacing
            rect = pygame.Rect(x + shake_x, top_y + shake_y, card_w, card_h)
            self.ai_card_rects.append((i, rect.copy()))
            shadow = rect.move(5, 6)
            pygame.draw.rect(screen, (0, 0, 0, 80), shadow, border_radius=12)
            if back_img:
                img = pygame.transform.smoothscale(back_img, (card_w, card_h))
                screen.blit(img, rect.topleft)
            else:
                self._draw_fallback_back(screen, rect)

        self.player_card_rects = []
        for i, card in enumerate(player_hand):
            x = start_x + i * spacing
            rect = pygame.Rect(x + shake_x, bot_y + shake_y, card_w, card_h)
            selected = i in self.selected_indices
            draw_rect = rect.move(0, -14) if selected else rect
            self.player_card_rects.append((i, draw_rect.copy()))
            shadow = rect.move(5, 6)
            pygame.draw.rect(screen, (0, 0, 0, 80), shadow, border_radius=12)
            img = assets.get_card_image(self._asset_key_for_card(card))
            if img:
                scaled = pygame.transform.smoothscale(img, (card_w, card_h))
                screen.blit(scaled, draw_rect.topleft)
                pygame.draw.rect(screen, (244, 236, 220), draw_rect, width=1, border_radius=12)
            else:
                pygame.draw.rect(screen, (250, 248, 240), draw_rect, border_radius=12)
                pygame.draw.rect(screen, (130, 110, 84), draw_rect, width=2, border_radius=12)
            if selected:
                pygame.draw.rect(screen, (250, 214, 120), draw_rect, width=3, border_radius=12)

        pile = list(getattr(engine.state, "pegging_pile", []))
        if pile:
            pile_w, pile_h = 86, 129
            pile_x = sw // 2 - (pile_w + min(26, max(10, pile_w // 3)) * max(0, len(pile) - 1)) // 2
            pile_y = sh // 2 - 66
            for i, card in enumerate(pile):
                rect = pygame.Rect(pile_x + i * 22 + shake_x, pile_y + shake_y, pile_w, pile_h)
                shadow = rect.move(4, 5)
                pygame.draw.rect(screen, (0, 0, 0, 80), shadow, border_radius=10)
                img = assets.get_card_image(self._asset_key_for_card(card))
                if img is not None:
                    screen.blit(pygame.transform.smoothscale(img, (pile_w, pile_h)), rect.topleft)
                else:
                    pygame.draw.rect(screen, (246, 242, 235), rect, border_radius=10)
                    pygame.draw.rect(screen, (130, 110, 84), rect, width=2, border_radius=10)

            total_font = pygame.font.SysFont("segoe ui", 20, bold=True)
            pegging_total = int(getattr(engine, "_current_pegging_total", lambda: 0)())
            total_text = total_font.render(f"Pegging Total: {pegging_total}", True, (235, 221, 188))
            screen.blit(total_text, (sw // 2 - total_text.get_width() // 2, pile_y - 28))

        show_go = self.phase == "pegging" and int(getattr(engine.state, "player_turn", 0)) == 0 and not self._player_has_valid_pegging_play(engine)
        if show_go:
            self.go_button_rect = pygame.Rect(sw // 2 - 85, sh // 2 + 86, 170, 44)
            go_hover = self.go_button_rect.collidepoint(pygame.mouse.get_pos())
            go_draw = self.go_button_rect.move(0, -2 if go_hover else 0)
            pygame.draw.rect(screen, (0, 0, 0, 80), go_draw.move(0, 4), border_radius=10)
            pygame.draw.rect(screen, (55, 70, 92) if not go_hover else (67, 84, 108), go_draw, border_radius=10)
            pygame.draw.rect(screen, (197, 212, 238), go_draw, width=2, border_radius=10)
            go_font = pygame.font.SysFont("segoe ui", 22, bold=True)
            go_text = go_font.render("Go", True, (235, 241, 252))
            screen.blit(
                go_text,
                (
                    go_draw.centerx - go_text.get_width() // 2,
                    go_draw.centery - go_text.get_height() // 2,
                ),
            )
        else:
            self.go_button_rect = None

        if self.phase == "end":
            self.next_round_rect = pygame.Rect(sw // 2 - 120, sh - 84, 240, 48)
            nr_hover = self.next_round_rect.collidepoint(pygame.mouse.get_pos())
            nr_draw = self.next_round_rect.move(0, -2 if nr_hover else 0)
            pygame.draw.rect(screen, (0, 0, 0, 80), nr_draw.move(0, 4), border_radius=10)
            pygame.draw.rect(screen, (58, 88, 60) if not nr_hover else (70, 102, 72), nr_draw, border_radius=10)
            pygame.draw.rect(screen, (205, 224, 188), nr_draw, width=2, border_radius=10)
            nr_font = pygame.font.SysFont("segoe ui", 22, bold=True)
            nr_text = nr_font.render("Next Round", True, (236, 246, 223))
            screen.blit(
                nr_text,
                (
                    nr_draw.centerx - nr_text.get_width() // 2,
                    nr_draw.centery - nr_text.get_height() // 2,
                ),
            )
        else:
            self.next_round_rect = None

        if self.phase == "end" and self.end_hand_summary is not None:
            panel = pygame.Rect(20, sh - 248, 560, 148)
            pygame.draw.rect(screen, (14, 20, 18, 210), panel, border_radius=12)
            pygame.draw.rect(screen, (198, 177, 128), panel, width=2, border_radius=12)
            title_font = pygame.font.SysFont("segoe ui", 20, bold=True)
            body_font = pygame.font.SysFont("segoe ui", 18)

            title = title_font.render("Hand Scoring", True, (235, 222, 189))
            screen.blit(title, (panel.x + 14, panel.y + 10))

            p = int(self.end_hand_summary.get("player", 0))
            a = int(self.end_hand_summary.get("ai", 0))
            c = int(self.end_hand_summary.get("crib", 0))

            p_items = self._line_items(self.end_hand_summary.get("player_breakdown"))
            a_items = self._line_items(self.end_hand_summary.get("ai_breakdown"))
            c_items = self._line_items(self.end_hand_summary.get("crib_breakdown"))

            lines = [
                f"You: +{p}  ({p_items})",
                f"Bert: +{a}  ({a_items})",
                f"Crib: +{c}  ({c_items})",
            ]
            for i, line in enumerate(lines):
                surf = body_font.render(line, True, (232, 224, 208))
                screen.blit(surf, (panel.x + 14, panel.y + 42 + i * 30))

        btn_w, btn_h = 236, 42
        self.back_button_rect = pygame.Rect(sw - btn_w - 8, sh - btn_h - 6, btn_w, btn_h)
        hovered = self.back_button_rect.collidepoint(pygame.mouse.get_pos())
        draw_rect = self.back_button_rect.move(0, -2 if hovered else 0)

        pygame.draw.rect(screen, (0, 0, 0, 80), draw_rect.move(0, 4), border_radius=12)
        pygame.draw.rect(screen, (42, 62, 52) if not hovered else (54, 78, 66), draw_rect, border_radius=12)
        pygame.draw.rect(screen, (214, 184, 113), draw_rect, width=2, border_radius=12)

        btn_font = pygame.font.SysFont("segoe ui", 21, bold=True)
        btn_text = btn_font.render("Back to Main Menu", True, (242, 230, 196))
        screen.blit(
            btn_text,
            (
                draw_rect.centerx - btn_text.get_width() // 2,
                draw_rect.centery - btn_text.get_height() // 2,
            ),
        )

        self.effects.draw(screen)


def screen_center_x(app) -> int:
    screen = getattr(app, "screen", None)
    if screen is None:
        return 640
    try:
        return int(screen.get_width() // 2)
    except Exception:
        return 640
