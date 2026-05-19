from __future__ import annotations

from dataclasses import dataclass

import pygame

from states.online_login import OnlineLoginState
from states.online_match import OnlineMatchState
from states.online_menu import OnlineMenuState


@dataclass
class _FakeResult:
    player_id: str
    display_name: str
    session_token: str


class _FakeClient:
    def __init__(self):
        self._last_join = None

    def login(self, name: str):
        return {
            "player_id": "p_test",
            "display_name": name,
            "session_token": "tok",
        }

    def create_room(self):
        return "ROOM1234"

    def join_room(self, code: str):
        self._last_join = code
        return "match_joined"

    def enqueue(self):
        return "queue_1"

    def trigger_pair(self):
        return "match_quick"


class _FakeApp:
    def __init__(self):
        self.client = _FakeClient()
        self.online_enabled = False
        self.player_id = None
        self.display_name = None
        self.session_token = None
        self.current_match_id = None
        self.last_error = ""
        self.status_message = ""
        self.stream = None

    def reset_stream(self):
        self.stream = None


def _key_event(key: int, text: str = ""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=text)


def test_online_login_state_logs_in_and_transitions():
    app = _FakeApp()
    state = OnlineLoginState()

    state.handle_event(_key_event(pygame.K_a, "A"), None, None, app)
    state.handle_event(_key_event(pygame.K_l, "l"), None, None, app)
    state.handle_event(_key_event(pygame.K_i, "i"), None, None, app)
    next_state = state.handle_event(_key_event(pygame.K_RETURN), None, None, app)

    assert app.online_enabled is True
    assert app.player_id == "p_test"
    assert app.display_name == "Ali"
    assert isinstance(next_state, OnlineMenuState)


def test_online_menu_join_flow_transitions_to_match():
    app = _FakeApp()
    app.player_id = "p_test"
    app.session_token = "tok"
    app.display_name = "Ali"

    state = OnlineMenuState()
    for ch in "AB12":
        state.handle_event(_key_event(pygame.K_a, ch), None, None, app)

    next_state = state.handle_event(_key_event(pygame.K_2), None, None, app)

    assert app.current_match_id == "match_joined"
    assert isinstance(next_state, OnlineMatchState)


def test_online_menu_quick_match_transitions_to_match():
    app = _FakeApp()
    app.player_id = "p_test"
    app.session_token = "tok"
    app.display_name = "Ali"

    state = OnlineMenuState()
    next_state = state.handle_event(_key_event(pygame.K_3), None, None, app)

    assert app.current_match_id == "match_quick"
    assert isinstance(next_state, OnlineMatchState)
