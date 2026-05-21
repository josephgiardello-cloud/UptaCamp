from __future__ import annotations

import types

import pygame

import main


class _FakeState:
    def handle_event(self, event, engine, assets, app):
        return self

    def update(self, engine, dt, app):
        return None

    def draw(self, screen, engine, assets, app):
        return None


class _FakeScreen:
    def fill(self, color):
        return None

    def blit(self, surf, pos):
        return None

    def get_size(self):
        return (1200, 800)

    def get_width(self):
        return 1200

    def get_height(self):
        return 800


def test_main_defaults_to_classic_client(monkeypatch):
    called = {"value": False}

    def _classic_runner():
        called["value"] = True
        return 123

    monkeypatch.setattr(main, "_run_state_client", lambda args: 999)
    monkeypatch.setattr(main, "run_classic_client", _classic_runner)
    monkeypatch.setattr(
        main.argparse.ArgumentParser,
        "parse_known_args",
        lambda self: (
            types.SimpleNamespace(
                debug_play=False,
                online_url="http://127.0.0.1:8787",
                online_ws_url="ws://127.0.0.1:8790",
                volume=0.6,
                animations="on",
                online_ai_level=2,
                new_client=False,
            ),
            [],
        ),
    )

    result = main.main()

    assert called["value"] is True
    assert result == 123


def test_main_uses_new_client_path_when_flag_enabled(monkeypatch):
    monkeypatch.setattr(
        main.argparse.ArgumentParser,
        "parse_known_args",
        lambda self: (
            types.SimpleNamespace(
                debug_play=True,
                online_url="http://example.local",
                online_ws_url="ws://example.local",
                volume=0.5,
                animations="off",
                online_ai_level=3,
                new_client=True,
            ),
            [],
        ),
    )

    seen = {}

    def _fake_run_state_client(args):
        seen["args"] = args
        return 777

    monkeypatch.setattr(main, "_run_state_client", _fake_run_state_client)

    result = main.main()

    assert result == 777
    assert seen["args"].new_client is True
    assert seen["args"].online_url == "http://example.local"


def test_runtime_controller_toggles_pause_with_escape():
    controller = main.RuntimeController(
        args=types.SimpleNamespace(debug_play=False),
        logger=types.SimpleNamespace(exception=lambda *args, **kwargs: None),
        screen=_FakeScreen(),
        clock=types.SimpleNamespace(),
        assets=types.SimpleNamespace(),
        engine=types.SimpleNamespace(),
        app=types.SimpleNamespace(last_error=""),
        current_state=_FakeState(),
        mode=main.RuntimeMode.PLAYING,
    )

    controller.handle_input([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)])
    assert controller.mode == main.RuntimeMode.PAUSED

    controller.handle_input([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)])
    assert controller.mode == main.RuntimeMode.PLAYING
