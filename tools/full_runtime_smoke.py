from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pygame

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app_context import AppContext
from asset_manager import AssetManager
from cribbage_engine import CribbageEngine
from settings_manager import load_settings
from states.intro import IntroState


@dataclass
class SmokeIssue:
    step: str
    detail: str


def _mouse_down_at(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": 1})


def main() -> None:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    screen = pygame.display.set_mode((1200, 800))

    issues: list[SmokeIssue] = []

    settings = load_settings()
    app = AppContext(
        volume=float(settings.volume),
        animations_enabled=bool(settings.animations_enabled),
        preferred_online_ai_level=int(settings.online_ai_level),
    )
    app.settings = settings
    assets = AssetManager()
    engine = CribbageEngine(seed=404)

    state = IntroState()

    try:
        state.update(engine, 16, app)
        state.draw(screen, engine, assets, app)
    except Exception as exc:
        issues.append(SmokeIssue("intro_draw", f"exception: {exc}"))

    # Validate option transitions from intro.
    try:
        if state.online_button_rect is not None:
            s = state.handle_event(_mouse_down_at(state.online_button_rect.center), engine, assets, app)
            if s.__class__.__name__ != "OnlineLoginState":
                issues.append(SmokeIssue("online_option", f"unexpected state: {s.__class__.__name__}"))
        else:
            issues.append(SmokeIssue("online_option", "online button rect missing"))
    except Exception as exc:
        issues.append(SmokeIssue("online_option", f"exception: {exc}"))

    try:
        state = IntroState()
        state.draw(screen, engine, assets, app)
        if state.p2p_button_rect is not None:
            s = state.handle_event(_mouse_down_at(state.p2p_button_rect.center), engine, assets, app)
            if s.__class__.__name__ != "P2PLobbyState":
                issues.append(SmokeIssue("p2p_option", f"unexpected state: {s.__class__.__name__}"))
        else:
            issues.append(SmokeIssue("p2p_option", "p2p button rect missing"))
    except Exception as exc:
        issues.append(SmokeIssue("p2p_option", f"exception: {exc}"))

    # Local game flow smoke: start from intro, discard, peg, count.
    try:
        state = IntroState()
        state.draw(screen, engine, assets, app)
        if state.start_button_rect is None:
            issues.append(SmokeIssue("start_option", "start button rect missing"))
        else:
            state = state.handle_event(_mouse_down_at(state.start_button_rect.center), engine, assets, app)
    except Exception as exc:
        issues.append(SmokeIssue("start_option", f"exception: {exc}"))

    if state.__class__.__name__ != "DealState":
        issues.append(SmokeIssue("local_game", f"start did not enter DealState: {state.__class__.__name__}"))

    # Run local gameplay loop via UI events until at least one end phase is observed.
    saw_end = False
    for step in range(1200):
        try:
            state.update(engine, 16, app)
            state.draw(screen, engine, assets, app)
        except Exception as exc:
            issues.append(SmokeIssue("deal_loop", f"exception at step {step}: {exc}"))
            break

        phase = str(getattr(engine.state, "phase", ""))
        if phase == "discard":
            rects = list(getattr(state, "player_card_rects", []))
            if len(rects) >= 2:
                state.handle_event(_mouse_down_at(rects[0][1].center), engine, assets, app)
                state.handle_event(_mouse_down_at(rects[1][1].center), engine, assets, app)
            else:
                issues.append(SmokeIssue("discard", "player card rects missing"))
                break
            continue

        if phase == "pegging" and int(getattr(engine.state, "player_turn", 0)) == 0:
            valid = list(engine.get_valid_moves())
            if valid:
                idx = int(valid[0])
                by_idx = {i: r for i, r in getattr(state, "player_card_rects", [])}
                rect = by_idx.get(idx)
                if rect is None:
                    issues.append(SmokeIssue("pegging", f"missing rect for valid index {idx}"))
                    break
                state.handle_event(_mouse_down_at(rect.center), engine, assets, app)
            else:
                go_rect = getattr(state, "go_button_rect", None)
                if go_rect is None:
                    issues.append(SmokeIssue("pegging", "no valid moves but Go button missing"))
                    break
                state.handle_event(_mouse_down_at(go_rect.center), engine, assets, app)
            continue

        if phase == "end":
            saw_end = True
            break

    if not saw_end:
        issues.append(SmokeIssue("local_game", "did not reach end phase in smoke loop"))

    print("FULL_RUNTIME_SMOKE")
    print(f"Issues found: {len(issues)}")
    for issue in issues[:50]:
        print(f"[{issue.step}] {issue.detail}")


if __name__ == "__main__":
    main()
