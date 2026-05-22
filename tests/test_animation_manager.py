from __future__ import annotations

import pygame

from src.renderer.animation_manager import AnimationManager


def test_add_animation_expires_after_duration():
    manager = AnimationManager()
    manager.add_animation("flash", {"duration_ms": 50, "elapsed_ms": 0})

    manager.update(0.1)

    assert "flash" not in manager.active_animations


def test_effects_compatibility_methods_render_without_crash():
    pygame.init()
    surface = pygame.Surface((120, 120), pygame.SRCALPHA)
    card = pygame.Surface((30, 40), pygame.SRCALPHA)

    manager = AnimationManager()
    manager.add_card_flight(card, (10, 10), (100, 100), duration_ms=120)
    manager.add_score_popup("+2", (60, 60))
    manager.trigger_shake(intensity=3, duration_ms=100)

    manager.update(50)
    manager.render(surface)

    offset = manager.shake_offset()
    assert isinstance(offset, tuple)
    assert len(offset) == 2
