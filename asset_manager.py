from pathlib import Path

import pygame

from runtime_paths import resource_path


class AssetManager:
    def __init__(self):
        self.assets_dir = resource_path("assets")
        self.card_images = {}
        self.backgrounds = {}
        self._load_all_assets()

    def _load_all_assets(self):
        self._load_card_images()
        self._load_card_back()
        self._load_backgrounds()

    def _load_card_images(self):
        cards_dir = self.assets_dir / "cards"
        if not cards_dir.exists():
            return
        for path in cards_dir.glob("*.png"):
            stem = path.stem.lower()
            if stem in ("black_joker", "red_joker") or stem.endswith("2"):
                continue
            try:
                img = pygame.image.load(str(path)).convert_alpha()
                self.card_images[stem] = img
            except pygame.error:
                continue

    def _load_card_back(self):
        path = self.assets_dir / "mainecard.jpg"
        if not path.exists():
            return
        try:
            img = pygame.image.load(str(path)).convert()
            self.card_back = img
            self.card_images["back"] = img
        except pygame.error:
            pass

    def _load_backgrounds(self):
        for bg_name in [
            "table.jpg",
            "table.png",
            "board.jpg",
            "welcome_bg.png",
            "High_score_bg.jpg",
            "High_score_bg.png",
            "high_score_bg.jpg",
            "high_score_bg.png",
            "Tony.jpg",
            "The_wharf_bg.jpg",
            "OOS_Camper_bg.jpg",
            "Tree_path_bg.jpg",
            "old_house_bg.jpg",
            "old_house_bg.png",
            "name_entry_bg.jpg",
        ]:
            path = self.assets_dir / bg_name
            if path.exists():
                try:
                    img = pygame.image.load(str(path))
                    self.backgrounds[bg_name] = img
                except pygame.error:
                    continue

    def get_card_image(self, label):
        return self.card_images.get(label)

    def get_background(self, name):
        return self.backgrounds.get(name)
