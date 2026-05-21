from __future__ import annotations

import pygame

import cards as cribbage_cards
from online_client import MatchEventStream

from .base import GameStateBase


class OnlineMatchState(GameStateBase):
    def __init__(self, match_id: str):
        self.match_id = match_id
        self.local_tick = 0
        self.last_action_msg = ""

    def _ensure_stream(self, app) -> None:
        if app.stream is None:
            app.stream = MatchEventStream(app.client, self.match_id, ws_url=app.ws_url)
            app.stream.start()

    @staticmethod
    def _card_labels(cards: list[object] | None) -> list[str]:
        if not isinstance(cards, list):
            return []
        labels: list[str] = []
        for card in cards:
            label = getattr(card, "label", card)
            labels.append(str(label))
        return labels

    @staticmethod
    def _pick_discard_indices(hand_labels: list[str]) -> list[int]:
        if len(hand_labels) < 2:
            return []
        ranked = sorted(
            range(len(hand_labels)),
            key=lambda idx: cribbage_cards.value_for_fifteen(
                cribbage_cards.parse_card_label(hand_labels[idx])[0]
            ),
            reverse=True,
        )
        return sorted(ranked[:2], reverse=True)

    @staticmethod
    def _pick_pegging_card(hand_labels: list[str], running_total: int) -> str | None:
        legal: list[tuple[int, str]] = []
        for label in hand_labels:
            rank, _ = cribbage_cards.parse_card_label(label)
            value = cribbage_cards.value_for_fifteen(rank)
            if running_total + value <= 31:
                legal.append((value, label))
        if legal:
            legal.sort(key=lambda item: item[0])
            return legal[0][1]
        return None

    @staticmethod
    def _hand_from_snapshot(snapshot: dict[str, object], player_id: str | None) -> list[str]:
        game_state = snapshot.get("game_state", {})
        if not isinstance(game_state, dict):
            return []
        if player_id and player_id == snapshot.get("summary", {}).get("player_one_id"):
            return OnlineMatchState._card_labels(game_state.get("player_hand"))
        if player_id and player_id == snapshot.get("summary", {}).get("player_two_id"):
            return OnlineMatchState._card_labels(game_state.get("ai_hand"))
        return OnlineMatchState._card_labels(game_state.get("player_hand"))

    def _pick_count_points(self, snapshot: dict[str, object]) -> int:
        game_state = snapshot.get("game_state", {})
        if not isinstance(game_state, dict):
            return 4
        starter = game_state.get("starter_card")
        player_hand = self._card_labels(game_state.get("player_kept"))
        if not starter or len(player_hand) != 4:
            return 4
        try:
            model_hand = [cribbage_cards.label_to_card(lbl) for lbl in player_hand]
            model_starter = cribbage_cards.label_to_card(str(starter))
            total, _ = cribbage_cards.score_hand(model_hand, model_starter, is_crib=False)
            return int(total)
        except Exception:
            return 4

    def handle_event(self, event, engine, assets, app):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                app.reset_stream()
                from .online_menu import OnlineMenuState

                return OnlineMenuState()
            if event.key == pygame.K_SPACE:
                self._submit_phase_action(app)
                return self
        return self

    def _submit_phase_action(self, app) -> None:
        try:
            snapshot = app.stream.last_snapshot if app.stream else None
            if not snapshot:
                return
            summary = snapshot["summary"]
            if summary["state"] != "active":
                return
            if summary["active_player_id"] != app.player_id:
                app.status_message = "Waiting for opponent turn"
                return

            phase = snapshot["game_state"].get("phase", "deal")
            if phase == "deal":
                app.client.submit_turn(self.match_id, "deal_ready", {"ready": True})
                self.last_action_msg = "Deal ready submitted"
            elif phase == "discard":
                hand_labels = self._hand_from_snapshot(snapshot, app.player_id)
                discard_indices = self._pick_discard_indices(hand_labels)
                discard_cards = [hand_labels[idx] for idx in discard_indices] if discard_indices else [
                    "5_of_hearts",
                    "king_of_clubs",
                ]
                app.client.submit_turn(
                    self.match_id,
                    "discard",
                    {"cards": discard_cards},
                )
                self.last_action_msg = "Discard submitted"
            elif phase == "pegging":
                game_state = snapshot["game_state"] if isinstance(snapshot.get("game_state"), dict) else {}
                running_total = int(game_state.get("pegging_running_total", 0)) if isinstance(game_state, dict) else 0
                hand_labels = self._hand_from_snapshot(snapshot, app.player_id)
                card_label = self._pick_pegging_card(hand_labels, running_total)
                if not card_label:
                    app.client.submit_turn(self.match_id, "go", {})
                    self.last_action_msg = "Go submitted"
                else:
                    app.client.submit_turn(
                        self.match_id,
                        "peg",
                        {"card": card_label},
                    )
                    self.last_action_msg = "Peg submitted"
            elif phase == "counting":
                points = self._pick_count_points(snapshot)
                app.client.submit_turn(self.match_id, "count", {"points": points})
                self.last_action_msg = "Counting submitted"
            else:
                self.last_action_msg = "Match already finished"
        except Exception as exc:
            app.last_error = str(exc)

    def update(self, engine, dt: int, app):
        self._ensure_stream(app)
        self.local_tick += dt

        if app.stream and app.stream.last_error:
            app.status_message = app.stream.last_error
        if app.stream and app.stream.last_snapshot:
            snapshot = app.stream.last_snapshot
            state = snapshot["summary"]["state"]
            if state == "finished":
                winner = snapshot["game_state"].get("winner_player_id") or "Draw"
                app.status_message = f"Match finished. Winner: {winner}. Esc to menu."
            elif snapshot["summary"]["active_player_id"] == app.player_id:
                app.status_message = "Your turn. Press Space to submit phase action."
            else:
                app.status_message = "Waiting for opponent turn..."
        return None

    def draw(self, screen, engine, assets, app):
        screen.fill((16, 20, 30))
        title_font = pygame.font.SysFont(None, 52)
        body_font = pygame.font.SysFont(None, 30)

        title = title_font.render("Online Match", True, (245, 245, 245))
        screen.blit(title, title.get_rect(center=(screen.get_width() // 2, 70)))

        match_text = body_font.render(f"Match: {self.match_id}", True, (205, 225, 245))
        screen.blit(match_text, match_text.get_rect(center=(screen.get_width() // 2, 120)))

        snapshot = app.stream.last_snapshot if app.stream else None
        if snapshot:
            summary = snapshot["summary"]
            game_state = snapshot["game_state"]
            lines = [
                f"Mode: {summary['mode']}  State: {summary['state']}",
                f"Phase: {game_state.get('phase', 'unknown')}",
                f"Turns: {summary['turns_played']}",
                f"Active Player: {summary['active_player_id']}",
                f"Scores: {game_state.get('scores', [0, 0])}",
                "Space = submit legal phase action, Esc = menu",
            ]
            y = 190
            for line in lines:
                s = body_font.render(line, True, (230, 230, 230))
                screen.blit(s, s.get_rect(center=(screen.get_width() // 2, y)))
                y += 44

        if app.status_message:
            msg = body_font.render(app.status_message, True, (180, 220, 180))
            screen.blit(
                msg, msg.get_rect(center=(screen.get_width() // 2, screen.get_height() - 110))
            )

        if self.last_action_msg:
            line = body_font.render(self.last_action_msg, True, (180, 210, 245))
            screen.blit(
                line, line.get_rect(center=(screen.get_width() // 2, screen.get_height() - 76))
            )

        if app.last_error:
            err = body_font.render(app.last_error, True, (230, 110, 110))
            screen.blit(
                err, err.get_rect(center=(screen.get_width() // 2, screen.get_height() - 42))
            )
