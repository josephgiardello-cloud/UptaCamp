import pygame
from .sprites import CardSprite

class UIRenderer:
    def __init__(self, assets):
        self.assets = assets

    def draw_hand(self, screen, hand, y, assets):
        x = 100
        for card in hand:
            sprite = CardSprite(card, (x, y), assets)
            screen.blit(sprite.image, sprite.rect)
            x += 90
