import pygame
from .base import GameStateBase

class IntroState(GameStateBase):
    def __init__(self):
        self.start_button_rect = None

    def handle_event(self, event, engine, assets):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            from .deal import DealState
            return DealState()
        if event.type == pygame.MOUSEBUTTONDOWN and self.start_button_rect is not None:
            if self.start_button_rect.collidepoint(event.pos):
                from .deal import DealState
                return DealState()
        return self

    def update(self, engine, dt):
        pass

    def draw(self, screen, engine, assets):
        bg = assets.get_background('table.jpg') or assets.get_background('table.png')
        if bg:
            scaled = pygame.transform.smoothscale(bg, screen.get_size())
            screen.blit(scaled, (0, 0))
        else:
            screen.fill((34, 139, 34))

        title_font = pygame.font.SysFont(None, 82)
        help_font = pygame.font.SysFont(None, 34)

        title = title_font.render("Cribbage", True, (255, 255, 255))
        title_rect = title.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2 - 120))
        screen.blit(title, title_rect)

        button_w, button_h = 260, 64
        self.start_button_rect = pygame.Rect(
            screen.get_width() // 2 - button_w // 2,
            screen.get_height() // 2 - button_h // 2,
            button_w,
            button_h,
        )
        pygame.draw.rect(screen, (130, 85, 45), self.start_button_rect, border_radius=12)
        pygame.draw.rect(screen, (240, 210, 150), self.start_button_rect, width=2, border_radius=12)

        start_text = help_font.render("Start Hand", True, (255, 255, 255))
        start_rect = start_text.get_rect(center=self.start_button_rect.center)
        screen.blit(start_text, start_rect)

        hint = help_font.render("Press Enter/Space or click Start Hand", True, (255, 255, 255))
        hint_rect = hint.get_rect(center=(screen.get_width() // 2, self.start_button_rect.bottom + 46))
        screen.blit(hint, hint_rect)
