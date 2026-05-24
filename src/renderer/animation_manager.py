"""Animation and frame management.

This module centralizes animation orchestration for migrated renderer code,
while delegating legacy visual effects to the existing EffectsManager.
"""

from __future__ import annotations

from typing import Any

from animations import EffectsManager


class AnimationManager:
    """Manages card animations and frame-based effects."""

    def __init__(self):
        """Initialize animation manager."""
        self.active_animations: dict[str, Any] = {}
        self._effects = EffectsManager()

    def add_animation(self, animation_id: str, animation_data: Any) -> None:
        """Register an animation.

        Args:
            animation_id: Unique animation identifier
            animation_data: Animation configuration dict
        """
        self.active_animations[str(animation_id)] = animation_data

    def remove_animation(self, animation_id: str) -> None:
        self.active_animations.pop(str(animation_id), None)

    def clear(self) -> None:
        self.active_animations.clear()

    def add_card_flight(
        self,
        image: Any,
        start: tuple[float, float],
        end: tuple[float, float],
        duration_ms: int = 280,
    ) -> None:
        self._effects.add_card_flight(image, start, end, duration_ms=duration_ms)

    def add_score_popup(
        self,
        text: str,
        pos: tuple[float, float],
        color: tuple[int, int, int] = (245, 241, 230),
        duration_ms: int = 900,
    ) -> None:
        self._effects.add_score_popup(text, pos, color=color, duration_ms=duration_ms)

    def trigger_shake(self, intensity: int = 8, duration_ms: int = 220) -> None:
        self._effects.trigger_shake(intensity=intensity, duration_ms=duration_ms)

    def shake_offset(self) -> tuple[int, int]:
        raw = self._effects.shake_offset()
        if isinstance(raw, tuple) and len(raw) == 2:
            try:
                return (int(raw[0]), int(raw[1]))
            except (TypeError, ValueError):
                return (0, 0)
        return (0, 0)

    @staticmethod
    def _coerce_delta_ms(delta_time: float) -> int:
        if delta_time <= 0:
            return 0
        # Support both seconds-based and milliseconds-based callers.
        return int(delta_time if delta_time > 10 else delta_time * 1000.0)

    def update(self, delta_time: float) -> None:
        """Update all active animations.

        Args:
            delta_time: Time since last frame (seconds)
        """
        delta_ms = self._coerce_delta_ms(float(delta_time))
        if delta_ms <= 0:
            return

        expired: list[str] = []
        for animation_id, animation_data in self.active_animations.items():
            if not isinstance(animation_data, dict):
                continue

            duration_ms = int(animation_data.get("duration_ms", 0))
            elapsed_ms = int(animation_data.get("elapsed_ms", 0)) + delta_ms
            animation_data["elapsed_ms"] = elapsed_ms
            if duration_ms > 0 and elapsed_ms >= duration_ms:
                expired.append(animation_id)

        for animation_id in expired:
            self.active_animations.pop(animation_id, None)

        self._effects.update(delta_ms)

    def render(self, surface: Any) -> None:
        """Render all active animations.

        Args:
            surface: pygame surface to draw on
        """
        for animation_data in list(self.active_animations.values()):
            if not isinstance(animation_data, dict):
                continue

            render_fn = animation_data.get("render")
            if callable(render_fn):
                render_fn(surface, animation_data)
                continue

            draw_fn = animation_data.get("draw")
            if callable(draw_fn):
                draw_fn(surface)

        self._effects.draw(surface)
