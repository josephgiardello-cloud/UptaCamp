import pygame

CARD_WIDTH = 80
CARD_HEIGHT = 120

class CardSprite:
    def __init__(self, card, pos, assets):
        self.card = card
        self.rect = pygame.Rect(pos, (CARD_WIDTH, CARD_HEIGHT))
        self.image = assets.images.get(card.id) or assets.images['back']
