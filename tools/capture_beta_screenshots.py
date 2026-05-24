from __future__ import annotations

from pathlib import Path
import sys

import pygame

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app_context import AppContext
from asset_manager import AssetManager
from cribbage_engine import CribbageEngine
from settings_manager import load_settings
from states.deal import DealState
from states.intro import IntroState


OUT_DIR = Path("screenshots") / "beta_series_2026_05"
SCREEN_SIZE = (1280, 900)


def _save(screen: pygame.Surface, name: str) -> None:
    path = OUT_DIR / name
    pygame.image.save(screen, str(path))
    print(f"saved {path}")


def _new_app() -> AppContext:
    app = AppContext(server_url="", ws_url="")
    app.settings = load_settings()
    app.audio = None
    app.voice = None
    app.last_error = ""
    app.status_message = ""
    return app


def _capture_intro(screen: pygame.Surface, assets: AssetManager) -> None:
    app = _new_app()
    engine = CribbageEngine(seed=20260523)

    state = IntroState()
    state.dad_ai_level = 4
    state.update(engine, 0, app)
    state.draw(screen, engine, assets, app)
    _save(screen, "01_title_levels.png")

    state = IntroState()
    state.dad_ai_level = 5
    state.update(engine, 0, app)
    state.draw(screen, engine, assets, app)
    _save(screen, "02_title_classic.png")


def _capture_discard_levels(screen: pygame.Surface, assets: AssetManager) -> None:
    levels = [
        (1, "03_level_easy_discard.png"),
        (2, "04_level_medium_discard.png"),
        (3, "05_level_hard_discard.png"),
        (4, "06_level_bert_discard.png"),
        (5, "07_level_barnabas_discard.png"),
    ]

    for level, filename in levels:
        app = _new_app()
        engine = CribbageEngine(seed=20260523 + level)
        state = DealState(dad_ai_level=level)
        state.update(engine, 16, app)
        state.draw(screen, engine, assets, app)
        _save(screen, filename)


def _setup_into_pegging(level: int) -> tuple[AppContext, CribbageEngine, DealState]:
    app = _new_app()
    engine = CribbageEngine(seed=20270000 + level)
    state = DealState(dad_ai_level=level)

    state.update(engine, 16, app)
    valid_discard = engine.get_valid_moves()
    if valid_discard:
        engine.handle_discard(valid_discard[0])
    state._sync_from_engine(engine)
    return app, engine, state


def _capture_pegging_and_counting(screen: pygame.Surface, assets: AssetManager) -> None:
    app, engine, state = _setup_into_pegging(level=2)

    # Let AI make at least one pegging action when applicable.
    for _ in range(3):
        state.update(engine, 450, app)
        if len(getattr(engine.state, "pegging_pile", [])) > 0:
            break

    state.draw(screen, engine, assets, app)
    _save(screen, "08_gameplay_pegging.png")

    engine._sync_phase("counting")
    state._sync_from_engine(engine)
    state.update(engine, 16, app)
    state.draw(screen, engine, assets, app)
    _save(screen, "09_gameplay_counting.png")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pygame.init()
    try:
        screen = pygame.display.set_mode(SCREEN_SIZE)
        pygame.display.set_caption("UptaCamp Screenshot Capture")
        assets = AssetManager()

        _capture_intro(screen, assets)
        _capture_discard_levels(screen, assets)
        _capture_pegging_and_counting(screen, assets)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()