import pygame
from pathlib import Path

class AssetManager:
    def __init__(self):
        self.assets_dir = Path('assets')
        self.card_images = {}
        self.backgrounds = {}
        self._load_all_assets()

    def _load_all_assets(self):
        self._load_card_images()
        self._load_backgrounds()

    def _load_card_images(self):
        cards_dir = self.assets_dir / 'cards'
        if not cards_dir.exists():
            return
        for path in cards_dir.glob('*.png'):
            stem = path.stem.lower()
            if stem in ('black_joker', 'red_joker') or stem.endswith('2'):
                continue
            try:
                img = pygame.image.load(str(path)).convert_alpha()
                self.card_images[stem] = img
            except pygame.error:
                continue

    def _load_backgrounds(self):
        for bg_name in ['table.jpg', 'table.png', 'board.jpg', 'welcome_bg.png', 'Tony.jpg', 'name_entry_bg.jpg']:
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
