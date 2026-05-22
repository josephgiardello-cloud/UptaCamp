from __future__ import annotations

import pygame

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

    # Deterministic line for assertion.
    monkeypatch.setattr("states.intro.choose_line", lambda *args, **kwargs: "selection line")

    state.difficulty_buttons = {
        1: pygame.Rect(10, 10, 80, 40),
    }

    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(20, 20), button=1)
    state.handle_event(event, None, None, app)

    assert app.voice.calls
    assert app.voice.calls[0]["text"] == "selection line"
    assert app.voice.calls[0]["dad_ai_level"] == 4
