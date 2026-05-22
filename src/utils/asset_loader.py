"""Asset loading and resource management.

This module provides concrete image/font loading with cache semantics so
runtime code can depend on src/ utilities instead of legacy globals.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pygame


class AssetManager:
    """Manages all game assets."""

    def __init__(self, assets_root: str | Path = "assets"):
        """Initialize asset manager."""
        self.assets_root = Path(assets_root)
        self.assets: dict[str, Any] = {}
        self._image_cache: dict[str, Any] = {}
        self._font_cache: dict[tuple[str, int], Any] = {}

    def _resolve_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        if candidate.exists():
            return candidate
        return self.assets_root / candidate

    @staticmethod
    def _prepare_surface(surface: Any) -> Any:
        # convert_alpha requires a display surface; keep original if unavailable.
        try:
            return surface.convert_alpha()
        except pygame.error:
            try:
                return surface.convert()
            except pygame.error:
                return surface

    def load_image(self, name: str, path: str) -> Any:
        """Load an image asset.

        Args:
            name: Asset identifier
            path: File path

        Returns:
            pygame Surface object
        """
        cached = self._image_cache.get(name)
        if cached is not None:
            return cached

        resolved = self._resolve_path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"Image asset not found: {resolved}")

        loaded = pygame.image.load(str(resolved))
        image = self._prepare_surface(loaded)
        self._image_cache[name] = image
        self.assets[name] = image
        return image

    def load_font(self, name: str, size: int = 36) -> Any:
        """Load a font asset.

        Args:
            name: Font name
            size: Font size in pixels

        Returns:
            pygame font object
        """
        key = (str(name), int(size))
        cached = self._font_cache.get(key)
        if cached is not None:
            return cached

        if not pygame.font.get_init():
            pygame.font.init()

        resolved = self._resolve_path(name)
        if resolved.exists():
            font = pygame.font.Font(str(resolved), int(size))
        else:
            system_name = None if str(name).lower() in {"", "default"} else str(name)
            font = pygame.font.SysFont(system_name, int(size))

        self._font_cache[key] = font
        self.assets[f"font:{name}:{int(size)}"] = font
        return font

    def preload_card_images(self, cards_dir: str | Path = "cards") -> dict[str, Any]:
        """Load canonical card PNG assets under assets/cards."""
        directory = self._resolve_path(cards_dir)
        loaded: dict[str, Any] = {}
        if not directory.exists():
            return loaded

        for png in directory.glob("*.png"):
            stem = png.stem.lower()
            if stem in {"black_joker", "red_joker"} or stem.endswith("2"):
                continue
            loaded[stem] = self.load_image(stem, str(png))
        return loaded

    def preload_backgrounds(self, names: list[str]) -> dict[str, Any]:
        """Best-effort load for a list of background files under assets/."""
        loaded: dict[str, Any] = {}
        for filename in names:
            key = str(filename)
            path = self._resolve_path(filename)
            if not path.exists():
                continue
            try:
                loaded[key] = self.load_image(key, str(path))
            except (pygame.error, FileNotFoundError):
                continue
        return loaded

    def get_asset(self, name: str) -> Any:
        """Retrieve a cached asset.

        Args:
            name: Asset identifier

        Returns:
            Asset object or None if not found
        """
        return self.assets.get(name)
