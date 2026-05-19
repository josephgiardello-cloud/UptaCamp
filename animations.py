from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple
import random

import pygame


def _ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - pow(1.0 - t, 3)


@dataclass
class CardFlight:
    image: pygame.Surface
    start: Tuple[float, float]
    end: Tuple[float, float]
    duration_ms: int
    elapsed_ms: int = 0

    def update(self, dt_ms: int) -> bool:
        self.elapsed_ms += dt_ms
        return self.elapsed_ms >= self.duration_ms

    def draw(self, target: pygame.Surface) -> None:
        t = 1.0 if self.duration_ms <= 0 else self.elapsed_ms / self.duration_ms
        eased = _ease_out_cubic(t)

        x = self.start[0] + (self.end[0] - self.start[0]) * eased
        y = self.start[1] + (self.end[1] - self.start[1]) * eased - 20 * (1.0 - (2 * eased - 1) ** 2)

        angle = (1.0 - eased) * 8
        scaled = pygame.transform.rotozoom(self.image, angle, 0.9 + 0.1 * eased)
        rect = scaled.get_rect(center=(x, y))
        target.blit(scaled, rect)


@dataclass
class FloatingScore:
    text: str
    pos: Tuple[float, float]
    color: Tuple[int, int, int]
    duration_ms: int
    elapsed_ms: int = 0

    def update(self, dt_ms: int) -> bool:
        self.elapsed_ms += dt_ms
        return self.elapsed_ms >= self.duration_ms

    def draw(self, target: pygame.Surface, font: pygame.font.Font) -> None:
        t = 1.0 if self.duration_ms <= 0 else self.elapsed_ms / self.duration_ms
        eased = _ease_out_cubic(t)

        y = self.pos[1] - 50 * eased
        scale = 1.0 + 0.25 * (1.0 - eased)
        alpha = int(255 * (1.0 - t))

        base = font.render(self.text, True, self.color)
        surf = pygame.transform.rotozoom(base, 0, scale)
        surf.set_alpha(max(0, min(255, alpha)))
        rect = surf.get_rect(center=(self.pos[0], y))
        target.blit(surf, rect)


class EffectsManager:
    def __init__(self) -> None:
        self.flights: List[CardFlight] = []
        self.popups: List[FloatingScore] = []
        self._rng = random.Random()
        self._shake_timer_ms = 0
        self._shake_intensity = 0
        self._font: pygame.font.Font | None = None

    def add_card_flight(
        self,
        image: pygame.Surface,
        start: Tuple[float, float],
        end: Tuple[float, float],
        duration_ms: int = 280,
    ) -> None:
        self.flights.append(CardFlight(image=image, start=start, end=end, duration_ms=duration_ms))

    def add_score_popup(
        self,
        text: str,
        pos: Tuple[float, float],
        color: Tuple[int, int, int] = (245, 241, 230),
        duration_ms: int = 900,
    ) -> None:
        self.popups.append(FloatingScore(text=text, pos=pos, color=color, duration_ms=duration_ms))

    def trigger_shake(self, intensity: int = 8, duration_ms: int = 220) -> None:
        self._shake_intensity = max(self._shake_intensity, intensity)
        self._shake_timer_ms = max(self._shake_timer_ms, duration_ms)

    def update(self, dt_ms: int) -> None:
        if dt_ms <= 0:
            return

        remaining_flights: List[CardFlight] = []
        for f in self.flights:
            if not f.update(dt_ms):
                remaining_flights.append(f)
        self.flights = remaining_flights

        remaining_popups: List[FloatingScore] = []
        for p in self.popups:
            if not p.update(dt_ms):
                remaining_popups.append(p)
        self.popups = remaining_popups

        if self._shake_timer_ms > 0:
            self._shake_timer_ms = max(0, self._shake_timer_ms - dt_ms)
            if self._shake_timer_ms == 0:
                self._shake_intensity = 0

    def shake_offset(self) -> Tuple[int, int]:
        if self._shake_timer_ms <= 0 or self._shake_intensity <= 0:
            return (0, 0)
        return (
            self._rng.randint(-self._shake_intensity, self._shake_intensity),
            self._rng.randint(-self._shake_intensity, self._shake_intensity),
        )

    def draw(self, target: pygame.Surface) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("arial", 28, bold=True)

        for f in self.flights:
            f.draw(target)
        for p in self.popups:
            p.draw(target, self._font)
