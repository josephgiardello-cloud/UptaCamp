from __future__ import annotations

from pathlib import Path

import pygame

from src.utils.asset_loader import AssetManager


def test_load_image_caches_by_name(tmp_path: Path):
    pygame.init()
    surface = pygame.Surface((8, 8), pygame.SRCALPHA)
    surface.fill((120, 80, 40, 255))
    img_path = tmp_path / "chip.png"
    pygame.image.save(surface, str(img_path))

    mgr = AssetManager(assets_root=tmp_path)
    first = mgr.load_image("chip", "chip.png")
    second = mgr.load_image("chip", "chip.png")

    assert first is second
    assert mgr.get_asset("chip") is first


def test_load_font_caches_by_key():
    pygame.init()
    pygame.font.init()

    mgr = AssetManager()
    first = mgr.load_font("default", 18)
    second = mgr.load_font("default", 18)

    assert first is second


def test_preload_backgrounds_skips_missing_files(tmp_path: Path):
    pygame.init()
    surface = pygame.Surface((4, 4), pygame.SRCALPHA)
    img_path = tmp_path / "table.png"
    pygame.image.save(surface, str(img_path))

    mgr = AssetManager(assets_root=tmp_path)
    loaded = mgr.preload_backgrounds(["table.png", "missing.png"])

    assert "table.png" in loaded
    assert "missing.png" not in loaded
