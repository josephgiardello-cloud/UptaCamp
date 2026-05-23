import argparse
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import pygame

from audio_manager import AudioManager
from app_context import AppContext
from asset_manager import AssetManager
from cribbage_engine import CribbageEngine
from settings_manager import load_settings
from states.intro import IntroState
from voice_manager import VoiceManager


class RuntimeMode(str, Enum):
    MENU = "menu"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"


@dataclass
class RuntimeController:
    args: Any
    logger: logging.Logger
    screen: pygame.Surface
    clock: pygame.time.Clock
    assets: AssetManager
    engine: CribbageEngine
    app: AppContext
    current_state: Any
    mode: RuntimeMode = RuntimeMode.MENU
    running: bool = True

    def _sync_mode_for_state(self) -> None:
        if self.mode in {RuntimeMode.PAUSED, RuntimeMode.GAME_OVER}:
            return
        if isinstance(self.current_state, IntroState):
            self.mode = RuntimeMode.MENU
        else:
            self.mode = RuntimeMode.PLAYING

    def handle_input(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
                return

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if self.mode == RuntimeMode.PLAYING:
                    self.mode = RuntimeMode.PAUSED
                    return
                if self.mode == RuntimeMode.PAUSED:
                    self.mode = RuntimeMode.PLAYING
                    return

            if self.mode in {RuntimeMode.PAUSED, RuntimeMode.GAME_OVER}:
                continue

            try:
                new_state = self.current_state.handle_event(
                    event, self.engine, self.assets, self.app
                )
                if new_state is not self.current_state:
                    if self.args.debug_play:
                        print(
                            f"[state] {self.current_state.__class__.__name__} -> {new_state.__class__.__name__} "
                            f"on event={pygame.event.event_name(event.type)}"
                        )
                    self.current_state = new_state
                    self._sync_mode_for_state()
            except Exception as exc:
                self.app.last_error = f"Input handling failed: {exc}"
                self.mode = RuntimeMode.GAME_OVER
                self.logger.exception("state handle_event failed")

    def update(self, dt_ms: int) -> None:
        settings = getattr(self.app, "settings", None)
        audio = getattr(self.app, "audio", None)
        if settings is not None and audio is not None:
            try:
                audio.set_volume(float(getattr(self.app, "volume", 0.6)))
            except Exception:
                pass

        voice = getattr(self.app, "voice", None)
        if settings is not None and voice is not None:
            try:
                voice.set_enabled(bool(settings.bert_voice_enabled))
                voice.configure_backend(
                    str(settings.bert_voice_backend),
                    str(settings.bert_local_model_path),
                    str(settings.barnabas_local_model_path),
                    str(settings.bert_local_exe_path),
                    bool(settings.bert_rvc_enabled),
                    str(settings.bert_rvc_exe_path),
                    str(settings.bert_rvc_model_path),
                    str(settings.bert_rvc_index_path),
                    int(settings.bert_rvc_pitch_shift),
                )
            except Exception:
                pass

        if self.mode in {RuntimeMode.PAUSED, RuntimeMode.GAME_OVER}:
            return
        try:
            self.current_state.update(self.engine, dt_ms, self.app)
            self._sync_mode_for_state()
        except Exception as exc:
            self.app.last_error = f"Render/update failed: {exc}"
            self.mode = RuntimeMode.GAME_OVER
            self.logger.exception("state update failed")

    def render(self) -> None:
        if self.mode == RuntimeMode.GAME_OVER:
            self.screen.fill((20, 20, 20))
            font = pygame.font.SysFont(None, 30)
            msg = font.render(
                self.app.last_error or "Unexpected runtime error", True, (220, 120, 120)
            )
            self.screen.blit(msg, (40, 40))
            return

        try:
            self.current_state.draw(self.screen, self.engine, self.assets, self.app)
        except Exception as exc:
            self.app.last_error = f"Render/update failed: {exc}"
            self.mode = RuntimeMode.GAME_OVER
            self.logger.exception("state draw failed")
            self.screen.fill((20, 20, 20))
            font = pygame.font.SysFont(None, 30)
            msg = font.render(self.app.last_error, True, (220, 120, 120))
            self.screen.blit(msg, (40, 40))
            return

        if self.mode == RuntimeMode.PAUSED:
            overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            self.screen.blit(overlay, (0, 0))
            font = pygame.font.SysFont(None, 56)
            paused = font.render("Paused", True, (245, 245, 245))
            rect = paused.get_rect(
                center=(self.screen.get_width() // 2, self.screen.get_height() // 2)
            )
            self.screen.blit(paused, rect)


def _run_state_client(args: Any) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )
    logger = logging.getLogger(__name__)

    pygame.init()
    screen = pygame.display.set_mode((1200, 800))
    clock = pygame.time.Clock()

    assets = AssetManager()
    engine = CribbageEngine()
    settings = load_settings()
    app = AppContext(
        server_url=args.online_url,
        ws_url=args.online_ws_url,
        volume=float(settings.volume),
        animations_enabled=bool(settings.animations_enabled),
        preferred_online_ai_level=int(settings.online_ai_level),
        fps_cap=max(15, int(args.fps_cap)),
        online_poll_interval_s=max(0.5, float(args.online_poll_interval)),
        online_reconnect_delay_s=max(0.5, float(args.online_reconnect_delay)),
    )
    app.settings = settings
    app.audio = AudioManager(volume=app.volume)
    app.voice = VoiceManager(
        enabled=bool(settings.bert_voice_enabled),
        backend=str(settings.bert_voice_backend),
        local_ai_model_path=str(settings.bert_local_model_path),
        barnabas_local_model_path=str(settings.barnabas_local_model_path),
        local_ai_exe_path=str(settings.bert_local_exe_path),
        rvc_enabled=bool(settings.bert_rvc_enabled),
        rvc_exe_path=str(settings.bert_rvc_exe_path),
        rvc_model_path=str(settings.bert_rvc_model_path),
        rvc_index_path=str(settings.bert_rvc_index_path),
        rvc_pitch_shift=int(settings.bert_rvc_pitch_shift),
    )
    engine.voice = app.voice

    controller = RuntimeController(
        args=args,
        logger=logger,
        screen=screen,
        clock=clock,
        assets=assets,
        engine=engine,
        app=app,
        current_state=IntroState(),
    )

    while controller.running:
        events = list(pygame.event.get())
        controller.handle_input(events)
        controller.update(clock.get_time())
        controller.render()
        pygame.display.flip()
        clock.tick(app.fps_cap)

    return 0


def _run_once(args: Any) -> int:
    return int(_run_state_client(args) or 0)


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--debug-play", action="store_true")
    parser.add_argument("--online-url", default="http://127.0.0.1:8787")
    parser.add_argument("--online-ws-url", default="ws://127.0.0.1:8790")
    parser.add_argument(
        "--fps-cap",
        type=int,
        default=60,
        help="Frame rate cap for the state client.",
    )
    parser.add_argument(
        "--online-poll-interval",
        type=float,
        default=2.0,
        help="Polling interval in seconds when websocket is unavailable.",
    )
    parser.add_argument(
        "--online-reconnect-delay",
        type=float,
        default=2.0,
        help="Delay in seconds between online stream reconnect attempts.",
    )
    parser.add_argument("--volume", type=float, default=0.6)
    parser.add_argument("--animations", choices=["on", "off"], default="on")
    parser.add_argument("--online-ai-level", type=int, default=2)
    relaunch_group = parser.add_mutually_exclusive_group()
    relaunch_group.add_argument(
        "--auto-relaunch",
        dest="auto_relaunch",
        action="store_true",
        default=True,
        help="Relaunch automatically after the game window closes.",
    )
    relaunch_group.add_argument(
        "--no-auto-relaunch",
        dest="auto_relaunch",
        action="store_false",
        help="Disable automatic relaunch after the game window closes.",
    )
    parser.add_argument(
        "--relaunch-delay",
        type=float,
        default=0.75,
        help="Seconds to wait before relaunch when --auto-relaunch is enabled.",
    )
    args, _ = parser.parse_known_args()

    if not bool(getattr(args, "auto_relaunch", False)):
        return _run_once(args)

    delay_s = max(0.0, float(getattr(args, "relaunch_delay", 0.75)))
    while True:
        code = _run_once(args)
        print(f"[main] Game closed (exit={code}). Relaunching in {delay_s:.2f}s...")
        if delay_s > 0:
            time.sleep(delay_s)


if __name__ == "__main__":
    main()
