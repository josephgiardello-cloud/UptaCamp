from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame


def _ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - pow(1.0 - t, 3)


def _ease_in_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - pow(-2.0 * t + 2.0, 3) / 2.0


@dataclass
class CardFlight:
    image: pygame.Surface
    start: tuple[float, float]
    end: tuple[float, float]
    duration_ms: int
    start_delay_ms: int = 0
    elapsed_ms: int = 0
    _cache: dict[tuple[int, int], pygame.Surface] | None = None

    def _progress(self) -> float:
        active_elapsed = self.elapsed_ms - self.start_delay_ms
        if active_elapsed <= 0:
            return 0.0
        if self.duration_ms <= 0:
            return 1.0
        return max(0.0, min(1.0, active_elapsed / self.duration_ms))

    def _pose_at(self, t: float) -> tuple[float, float, float, float]:
        start_x, start_y = self.start
        end_x, end_y = self.end
        dx = end_x - start_x
        dy = end_y - start_y
        travel = _ease_in_out_cubic(t)
        distance = math.hypot(dx, dy)
        arc_height = min(18.0, max(8.0, distance * 0.035))
        x = start_x + dx * travel
        y = start_y + dy * travel - arc_height * math.sin(math.pi * travel)
        angle = max(-4.0, min(4.0, dx * 0.012)) * (1.0 - travel)
        scale = 0.985 + (0.015 * math.sin(math.pi * travel))
        return (x, y, angle, scale)

    def _transformed_surface(self, angle: float, scale: float) -> pygame.Surface:
        if self._cache is None:
            self._cache = {}
        angle_key = int(round(angle * 2.0))
        scale_key = int(round(scale * 100.0))
        key = (angle_key, scale_key)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        surf = pygame.transform.rotozoom(self.image, angle_key / 2.0, max(0.7, scale_key / 100.0))
        self._cache[key] = surf
        if len(self._cache) > 48:
            self._cache.pop(next(iter(self._cache)))
        return surf

    def update(self, dt_ms: int) -> bool:
        self.elapsed_ms += dt_ms
        if self.elapsed_ms < self.start_delay_ms:
            return False
        return (self.elapsed_ms - self.start_delay_ms) >= self.duration_ms

    def draw(self, target: pygame.Surface) -> None:
        if self.elapsed_ms < self.start_delay_ms:
            return
        x, y, angle, scale = self._pose_at(self._progress())

        shadow_w = 50 + int(8 * (1.0 - self._progress()))
        shadow_h = 18 + int(4 * (1.0 - self._progress()))
        shadow = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 52), shadow.get_rect())
        target.blit(shadow, (int(x - shadow_w // 2), int(y + 12)))

        card_surface = self._transformed_surface(angle, scale)
        card_surface.set_alpha(255)
        rect = card_surface.get_rect(center=(int(x), int(y)))
        target.blit(card_surface, rect)


@dataclass
class FloatingScore:
    text: str
    pos: tuple[float, float]
    color: tuple[int, int, int]
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
        self.flights: list[CardFlight] = []
        self.popups: list[FloatingScore] = []
        self._rng = random.Random()
        self._shake_timer_ms = 0
        self._shake_duration_ms = 0
        self._shake_intensity = 0.0
        self._shake_direction = 0.0
        self._shake_phase = 0.0
        self._font: pygame.font.Font | None = None

    def add_card_flight(
        self,
        image: pygame.Surface,
        start: tuple[float, float],
        end: tuple[float, float],
        duration_ms: int = 280,
        start_delay_ms: int = 0,
    ) -> None:
        self.flights.append(
            CardFlight(
                image=image,
                start=start,
                end=end,
                duration_ms=duration_ms,
                start_delay_ms=max(0, int(start_delay_ms)),
            )
        )

    def add_score_popup(
        self,
        text: str,
        pos: tuple[float, float],
        color: tuple[int, int, int] = (245, 241, 230),
        duration_ms: int = 900,
    ) -> None:
        self.popups.append(FloatingScore(text=text, pos=pos, color=color, duration_ms=duration_ms))

    def trigger_shake(self, intensity: int = 8, duration_ms: int = 220) -> None:
        next_duration = max(40, int(duration_ms))
        self._shake_intensity = max(self._shake_intensity, float(intensity))
        self._shake_timer_ms = max(self._shake_timer_ms, next_duration)
        self._shake_duration_ms = max(self._shake_duration_ms, next_duration)
        self._shake_direction = self._rng.uniform(0.0, 2.0 * math.pi)
        self._shake_phase = self._rng.uniform(0.0, 2.0 * math.pi)

    def update(self, dt_ms: int) -> None:
        if dt_ms <= 0:
            return

        remaining_flights: list[CardFlight] = []
        for f in self.flights:
            if not f.update(dt_ms):
                remaining_flights.append(f)
        self.flights = remaining_flights

        remaining_popups: list[FloatingScore] = []
        for p in self.popups:
            if not p.update(dt_ms):
                remaining_popups.append(p)
        self.popups = remaining_popups

        if self._shake_timer_ms > 0:
            self._shake_timer_ms = max(0, self._shake_timer_ms - dt_ms)
            if self._shake_timer_ms == 0:
                self._shake_intensity = 0.0
                self._shake_duration_ms = 0

    def shake_offset(self) -> tuple[int, int]:
        if self._shake_timer_ms <= 0 or self._shake_intensity <= 0:
            return (0, 0)
        duration = max(1, self._shake_duration_ms)
        progress = 1.0 - (self._shake_timer_ms / float(duration))
        envelope = pow(max(0.0, 1.0 - progress), 1.35)
        swing = math.sin((progress * 17.0) + self._shake_phase)
        magnitude = self._shake_intensity * envelope * (0.65 + 0.35 * abs(swing))
        jitter_x = self._rng.uniform(-0.18, 0.18) * magnitude
        jitter_y = self._rng.uniform(-0.18, 0.18) * magnitude
        ox = math.cos(self._shake_direction) * magnitude * swing + jitter_x
        oy = math.sin(self._shake_direction) * magnitude * swing + jitter_y
        return (int(round(ox)), int(round(oy)))

    def draw(self, target: pygame.Surface) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("arial", 28, bold=True)

        for f in self.flights:
            f.draw(target)
        for p in self.popups:
            p.draw(target, self._font)
