import pygame

from .base import GameStateBase


class IntroState(GameStateBase):
    def __init__(self):
        self.start_button_rect = None
        self.online_button_rect = None
        self.p2p_button_rect = None

    def handle_event(self, event, engine, assets, app):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            from .deal import DealState

            return DealState()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_o:
            from .online_login import OnlineLoginState

            return OnlineLoginState()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_p:
            from .p2p_lobby import P2PLobbyState

            return P2PLobbyState()
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.start_button_rect is not None and self.start_button_rect.collidepoint(event.pos):
                from .deal import DealState

                return DealState()
            if self.online_button_rect is not None and self.online_button_rect.collidepoint(event.pos):
                from .online_login import OnlineLoginState

                return OnlineLoginState()
            if self.p2p_button_rect is not None and self.p2p_button_rect.collidepoint(event.pos):
                from .p2p_lobby import P2PLobbyState

                return P2PLobbyState()
        return self

    def update(self, engine, dt, app):
        pass

    def draw(self, screen, engine, assets, app):
        bg = assets.get_background("table.jpg") or assets.get_background("table.png")
        if bg:
            scaled = pygame.transform.smoothscale(bg, screen.get_size())
            screen.blit(scaled, (0, 0))
        else:
            screen.fill((34, 139, 34))

        title_font = pygame.font.SysFont(None, 82)
        help_font = pygame.font.SysFont(None, 34)

        title = title_font.render("Cribbage", True, (255, 255, 255))
        title_rect = title.get_rect(
            center=(screen.get_width() // 2, screen.get_height() // 2 - 120)
        )
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

        button_w, button_h = 260, 64
        self.online_button_rect = pygame.Rect(
            screen.get_width() // 2 - button_w // 2,
            self.start_button_rect.bottom + 18,
            button_w,
            button_h,
        )
        pygame.draw.rect(screen, (56, 92, 130), self.online_button_rect, border_radius=12)
        pygame.draw.rect(
            screen, (180, 210, 240), self.online_button_rect, width=2, border_radius=12
        )
        online_text = help_font.render("Play With Friend", True, (255, 255, 255))
        online_rect = online_text.get_rect(center=self.online_button_rect.center)
        screen.blit(online_text, online_rect)

        button_w, button_h = 260, 64
        self.p2p_button_rect = pygame.Rect(
            screen.get_width() // 2 - button_w // 2,
            self.online_button_rect.bottom + 18,
            button_w,
            button_h,
        )
        pygame.draw.rect(screen, (56, 100, 56), self.p2p_button_rect, border_radius=12)
        pygame.draw.rect(
            screen, (140, 220, 140), self.p2p_button_rect, width=2, border_radius=12
        )
        p2p_text = help_font.render("Direct P2P", True, (255, 255, 255))
        p2p_rect = p2p_text.get_rect(center=self.p2p_button_rect.center)
        screen.blit(p2p_text, p2p_rect)

        hint = help_font.render(
            "Enter/Space = local  |  O = play with friend online  |  P = direct P2P",
            True,
            (255, 255, 255),
        )
        hint_rect = hint.get_rect(
            center=(screen.get_width() // 2, self.p2p_button_rect.bottom + 36)
        )
        screen.blit(hint, hint_rect)
