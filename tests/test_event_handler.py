from __future__ import annotations

import pygame

from src.input import EventHandler


class _FakeSurface:
    def __init__(self, size=(1200, 800)):
        self._size = size

    def get_width(self):
        return self._size[0]

    def get_height(self):
        return self._size[1]


def test_event_handler_maps_touch_events_to_mouse_actions(monkeypatch):
    handler = EventHandler()
    events = [
        pygame.event.Event(pygame.FINGERDOWN, x=0.5, y=0.25),
        pygame.event.Event(pygame.FINGERUP, x=0.5, y=0.25),
        pygame.event.Event(pygame.FINGERMOTION, x=0.5, y=0.25),
    ]

    monkeypatch.setattr(pygame.event, "get", lambda: events)
    monkeypatch.setattr(pygame.display, "get_surface", lambda: _FakeSurface())

    actions = handler.poll_events()

    assert actions[0]["type"] == "MOUSEBUTTONDOWN"
    assert actions[0]["pos"] == (600, 200)
    assert actions[0]["touch"] is True
    assert actions[1]["type"] == "MOUSEBUTTONUP"
    assert actions[1]["pos"] == (600, 200)
    assert actions[1]["touch"] is True
    assert actions[2]["type"] == "MOUSEMOTION"
    assert actions[2]["pos"] == (600, 200)
    assert actions[2]["touch"] is True
