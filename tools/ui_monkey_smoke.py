from __future__ import annotations

import argparse
import os
import random
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
class MonkeyIssue:
    session: int
    step: int
    state: str
    phase: str
    detail: str


def _rand_click(rng: random.Random, sw: int, sh: int) -> pygame.event.Event:
    x = rng.randint(0, max(0, sw - 1))
    y = rng.randint(0, max(0, sh - 1))
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (x, y), "button": 1})


def run_session(session_idx: int, steps: int, seed: int) -> list[MonkeyIssue]:
    rng = random.Random(seed)
    issues: list[MonkeyIssue] = []

    settings = load_settings()
    app = AppContext(
        volume=float(settings.volume),
        animations_enabled=bool(settings.animations_enabled),
        preferred_online_ai_level=int(settings.online_ai_level),
    )
    app.settings = settings

    assets = AssetManager()
    engine = CribbageEngine(seed=seed)
    state = IntroState()
    screen = pygame.display.set_mode((1200, 800))

    for step in range(1, steps + 1):
        state_name = state.__class__.__name__
        phase = str(getattr(getattr(engine, "state", None), "phase", "n/a"))

        try:
            state.update(engine, 16, app)
            state.draw(screen, engine, assets, app)
        except Exception as exc:
            issues.append(
                MonkeyIssue(session_idx, step, state_name, phase, f"update/draw exception: {exc}")
            )
            break

        # Weighted actions: mostly random clicks, sometimes keyboard shortcuts on intro.
        action_roll = rng.random()
        try:
            if action_roll < 0.75:
                evt = _rand_click(rng, screen.get_width(), screen.get_height())
                next_state = state.handle_event(evt, engine, assets, app)
                state = next_state if next_state is not None else state
            elif action_roll < 0.9 and state_name == "IntroState":
                key = rng.choice([pygame.K_RETURN, pygame.K_SPACE, pygame.K_o, pygame.K_p])
                evt = pygame.event.Event(pygame.KEYDOWN, {"key": key})
                next_state = state.handle_event(evt, engine, assets, app)
                state = next_state if next_state is not None else state
            else:
                # Keep local play going when monkey enters unsupported states.
                if state_name not in {"IntroState", "DealState"}:
                    state = IntroState()
        except Exception as exc:
            issues.append(
                MonkeyIssue(session_idx, step, state_name, phase, f"handle_event exception: {exc}")
            )
            break

    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Randomized UI monkey smoke for intro/deal flows")
    parser.add_argument("--sessions", type=int, default=30, help="Number of monkey sessions")
    parser.add_argument("--steps", type=int, default=1200, help="Steps per session")
    parser.add_argument(
        "--seed-base", type=int, default=91000, help="Seed base for reproducibility"
    )
    args = parser.parse_args()

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()

    sessions = max(1, int(args.sessions))
    steps = max(10, int(args.steps))
    seed_base = int(args.seed_base)

    all_issues: list[MonkeyIssue] = []
    for idx in range(1, sessions + 1):
        all_issues.extend(run_session(idx, steps, seed_base + idx))

    print("UI_MONKEY_SMOKE")
    print(f"Sessions: {sessions}")
    print(f"Steps/session: {steps}")
    print(f"Issues found: {len(all_issues)}")
    for issue in all_issues[:80]:
        print(
            f"[session {issue.session} step {issue.step} state={issue.state} phase={issue.phase}] {issue.detail}"
        )


if __name__ == "__main__":
    main()
