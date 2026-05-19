from __future__ import annotations

import pygame

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
                app.client.submit_turn(
                    self.match_id,
                    "discard",
                    {"cards": ["5_of_hearts", "king_of_clubs"]},
                )
                self.last_action_msg = "Discard submitted"
            elif phase == "pegging":
                running_total = (snapshot["summary"]["turns_played"] * 3) % 31
                app.client.submit_turn(
                    self.match_id,
                    "peg",
                    {"card": "7_of_spades", "running_total": running_total, "points": 1},
                )
                self.last_action_msg = "Peg submitted"
            elif phase == "counting":
                app.client.submit_turn(self.match_id, "count", {"points": 4})
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
            screen.blit(msg, msg.get_rect(center=(screen.get_width() // 2, screen.get_height() - 110)))

        if self.last_action_msg:
            line = body_font.render(self.last_action_msg, True, (180, 210, 245))
            screen.blit(line, line.get_rect(center=(screen.get_width() // 2, screen.get_height() - 76)))

        if app.last_error:
            err = body_font.render(app.last_error, True, (230, 110, 110))
            screen.blit(err, err.get_rect(center=(screen.get_width() // 2, screen.get_height() - 42)))
