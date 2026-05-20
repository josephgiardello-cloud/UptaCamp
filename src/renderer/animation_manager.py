"""Animation and frame management (stub for architecture refactoring).

This module will contain animation logic extracted from cribbage_pygame.py.
"""

from typing import Any


class AnimationManager:
    """Manages card animations and frame-based effects."""

    def __init__(self):
        """Initialize animation manager."""
        self.active_animations: dict[str, Any] = {}

    def add_animation(self, animation_id: str, animation_data: Any) -> None:
        """Register an animation.

        Args:
            animation_id: Unique animation identifier
            animation_data: Animation configuration dict
        """
        # TODO: Extract animation logic
        pass

    def update(self, delta_time: float) -> None:
        """Update all active animations.

        Args:
            delta_time: Time since last frame (seconds)
        """
        # TODO: Implement frame-independent animation updates
        pass

    def render(self, surface: Any) -> None:
        """Render all active animations.

        Args:
            surface: pygame surface to draw on
        """
        # TODO: Draw animation frames
        pass
