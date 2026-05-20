import random

import pygame

from cards import Card
from states.intro import IntroState

from .base import GameStateBase


class DealState(GameStateBase):
    def __init__(self):
        self.dealt = False
        self.player_hand = []
        self.ai_hand = []

    def handle_event(self, event, engine, assets, app):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return IntroState()
            if event.key == pygame.K_r:
                self.dealt = False
                self.player_hand = []
                self.ai_hand = []
        return self

    def update(self, engine, dt, app):
        if not self.dealt:
            # Deal 6 cards to player and AI
            deck = [
                Card(rank, suit)
                for suit in ["Hearts", "Diamonds", "Clubs", "Spades"]
                for rank in ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
            ]
            random.shuffle(deck)
            self.player_hand = deck[:6]
            self.ai_hand = deck[6:12]
            self.dealt = True

    def draw(self, screen, engine, assets, app):
        # Draw background if available
        bg = assets.get_background("table.jpg") or assets.get_background("table.png")
        if bg:
            bg = pygame.transform.smoothscale(bg, screen.get_size())
            screen.blit(bg, (0, 0))
        else:
            screen.fill((34, 139, 34))

        font = pygame.font.SysFont(None, 48)
        text = font.render("Dealing Cards...", True, (255, 255, 255))
        rect = text.get_rect(center=(screen.get_width() // 2, 60))
        screen.blit(text, rect)

        help_font = pygame.font.SysFont(None, 28)
        help_text = help_font.render("R = redeal, Esc = back to intro", True, (255, 255, 255))
        help_rect = help_text.get_rect(center=(screen.get_width() // 2, 95))
        screen.blit(help_text, help_rect)

        # Draw Dealer hand (card backs)
        x = 100
        y = 120
        back_img = assets.get_card_image("back")
        for _ in self.ai_hand:
            if back_img:
                img = pygame.transform.smoothscale(back_img, (80, 120))
                screen.blit(img, (x, y))
            else:
                pygame.draw.rect(screen, (180, 180, 180), (x, y, 80, 120))
            x += 90

        # Draw player hand (face up)
        x = 100
        y = screen.get_height() - 220
        for card in self.player_hand:
            img = assets.get_card_image(f"{card.rank.lower()}_of_{card.suit.lower()}")
            if img:
                img = pygame.transform.smoothscale(img, (80, 120))
                screen.blit(img, (x, y))
            else:
                pygame.draw.rect(screen, (255, 255, 255), (x, y, 80, 120))
            x += 90

        # Add labels for clarity
        small_font = pygame.font.SysFont(None, 32)
        dad_label = small_font.render("Dealer Hand", True, (255, 255, 255))
        player_label = small_font.render("Your Hand", True, (255, 255, 255))
        screen.blit(dad_label, (100, 90))
        screen.blit(player_label, (100, screen.get_height() - 250))
