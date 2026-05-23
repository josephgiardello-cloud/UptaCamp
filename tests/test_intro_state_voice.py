from __future__ import annotations

import pygame

from states.high_scores import HighScoresState
from states.intro import IntroState


class _VoiceSpy:
    def __init__(self):
        self.calls = []

    def speak_bert(self, text, dad_ai_level, bypass_cooldown=False, voice_style="downeast"):
        self.calls.append(
            {
                "text": text,
                "dad_ai_level": dad_ai_level,
                "bypass_cooldown": bool(bypass_cooldown),
                "voice_style": voice_style,
            }
        )


class _AudioSpy:
    def play(self, name: str):
        return None


class _AppStub:
    def __init__(self):
        self.voice = _VoiceSpy()
        self.audio = _AudioSpy()
        self.preferred_online_ai_level = 2


def test_level_selection_speaks_for_easy_level(monkeypatch):
    state = IntroState()
    app = _AppStub()

    # Low levels should not route through Bert/Barnabas persona lines.
    monkeypatch.setattr("states.intro.choose_line", lambda *args, **kwargs: "selection line")

    state.difficulty_buttons = {
        1: pygame.Rect(10, 10, 80, 40),
    }

    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(20, 20), button=1)
    state.handle_event(event, None, None, app)

    assert app.voice.calls
    assert app.voice.calls[0]["text"] == "Easy difficulty selected."
    assert app.voice.calls[0]["dad_ai_level"] == 1


def test_barnabas_unlock_progress_message_when_locked(monkeypatch):
    state = IntroState()
    app = _AppStub()

    monkeypatch.setattr("states.intro.get_difficulty_wins", lambda *_args, **_kwargs: 4)

    state._visible_difficulty_levels(app)

    assert state._barnabas_unlocked is False
    assert state._barnabas_wins == 4
    assert state._barnabas_remaining_wins == 6
    assert "4/10" in state._barnabas_unlock_message()
    assert "6 to go" in state._barnabas_unlock_message()


def test_barnabas_unlocks_at_threshold(monkeypatch):
    state = IntroState()
    app = _AppStub()

    monkeypatch.setattr("states.intro.get_difficulty_wins", lambda *_args, **_kwargs: 10)

    levels = state._visible_difficulty_levels(app)

    assert state._barnabas_unlocked is True
    assert state._barnabas_remaining_wins == 0
    assert (6, "Barnabas") in levels


def test_high_scores_key_opens_high_scores_state():
    state = IntroState()
    app = _AppStub()

    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_h)
    next_state = state.handle_event(event, None, None, app)

    assert isinstance(next_state, HighScoresState)


def test_high_scores_state_escape_returns_to_intro():
    app = _AppStub()
    state = HighScoresState()

    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    next_state = state.handle_event(event, None, None, app)

    assert isinstance(next_state, IntroState)
