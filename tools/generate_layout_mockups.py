from __future__ import annotations

import pygame

WIDTH, HEIGHT = 1280, 900
OUT = "screenshots"


def save(surface: pygame.Surface, name: str) -> None:
    pygame.image.save(surface, f"{OUT}/{name}")


def draw_title(surface: pygame.Surface, text: str) -> None:
    font = pygame.font.SysFont("segoe ui", 42, bold=True)
    subtitle = pygame.font.SysFont("segoe ui", 24)
    t = font.render(text, True, (245, 245, 245))
    s = subtitle.render("Concept mockup (visual direction only)", True, (196, 196, 196))
    surface.blit(t, (48, 30))
    surface.blit(s, (48, 82))


def broadcast_table() -> pygame.Surface:
    s = pygame.Surface((WIDTH, HEIGHT))
    s.fill((21, 39, 29))

    # Top strip
    pygame.draw.rect(s, (11, 27, 20), (36, 126, WIDTH - 72, 70), border_radius=22)
    pygame.draw.rect(s, (210, 188, 125), (36, 126, WIDTH - 72, 70), 2, border_radius=22)

    # Center lane
    pygame.draw.rect(s, (16, 54, 40), (250, 280, 780, 230), border_radius=30)
    pygame.draw.rect(s, (196, 171, 105), (250, 280, 780, 230), 2, border_radius=30)
    pygame.draw.circle(s, (23, 67, 50), (640, 395), 92)
    pygame.draw.circle(s, (230, 206, 149), (640, 395), 2, 92)

    # Side dock
    pygame.draw.rect(s, (18, 34, 27), (1046, 236, 190, 390), border_radius=24)
    pygame.draw.rect(s, (211, 188, 125), (1046, 236, 190, 390), 2, border_radius=24)

    # Bottom player rail
    pygame.draw.rect(s, (14, 29, 22), (100, 650, 1080, 180), border_radius=24)
    pygame.draw.rect(s, (198, 173, 109), (100, 650, 1080, 180), 2, border_radius=24)
    x = 160
    for _ in range(6):
        pygame.draw.rect(s, (238, 238, 238), (x, 680, 132, 138), border_radius=12)
        pygame.draw.rect(s, (60, 60, 60), (x, 680, 132, 138), 1, border_radius=12)
        x += 160

    draw_title(s, "Style 1: Broadcast Table")
    return s


def competitive_minimal() -> pygame.Surface:
    s = pygame.Surface((WIDTH, HEIGHT))
    s.fill((15, 16, 20))

    # Minimal grid accents
    for x in range(80, WIDTH, 140):
        pygame.draw.line(s, (28, 30, 36), (x, 130), (x, HEIGHT - 80), 1)
    for y in range(180, HEIGHT, 120):
        pygame.draw.line(s, (28, 30, 36), (60, y), (WIDTH - 60, y), 1)

    # Compact HUD chips
    pygame.draw.rect(s, (23, 27, 34), (52, 32, 180, 54), border_radius=20)
    pygame.draw.rect(s, (23, 27, 34), (WIDTH - 232, 32, 180, 54), border_radius=20)

    # Center board
    pygame.draw.rect(s, (21, 24, 31), (300, 250, 680, 330), border_radius=18)
    pygame.draw.rect(s, (96, 110, 136), (300, 250, 680, 330), 1, border_radius=18)
    pygame.draw.circle(s, (27, 35, 45), (640, 415), 110)
    pygame.draw.circle(s, (135, 160, 204), (640, 415), 2, 110)

    # Bottom hand rail
    pygame.draw.rect(s, (18, 20, 27), (180, 660, 920, 150), border_radius=14)
    pygame.draw.rect(s, (100, 115, 140), (180, 660, 920, 150), 1, border_radius=14)
    x = 240
    for _ in range(6):
        pygame.draw.rect(s, (240, 240, 240), (x, 686, 110, 112), border_radius=8)
        pygame.draw.rect(s, (70, 70, 70), (x, 686, 110, 112), 1, border_radius=8)
        x += 136

    draw_title(s, "Style 2: Competitive Minimal")
    return s


def premium_tabletop() -> pygame.Surface:
    s = pygame.Surface((WIDTH, HEIGHT))
    s.fill((58, 36, 20))

    # Felt inlaid board
    pygame.draw.rect(s, (92, 58, 30), (26, 26, WIDTH - 52, HEIGHT - 52), border_radius=36)
    pygame.draw.rect(s, (25, 79, 52), (58, 58, WIDTH - 116, HEIGHT - 116), border_radius=30)
    pygame.draw.rect(s, (225, 191, 124), (58, 58, WIDTH - 116, HEIGHT - 116), 2, border_radius=30)

    # Curved message bar
    pygame.draw.rect(s, (14, 43, 31), (210, 96, 860, 74), border_radius=34)
    pygame.draw.rect(s, (233, 207, 151), (210, 96, 860, 74), 2, border_radius=34)

    # Crib/starter panel
    pygame.draw.rect(s, (18, 68, 43), (208, 366, 690, 170), border_radius=28)
    pygame.draw.rect(s, (226, 198, 142), (208, 366, 690, 170), 2, border_radius=28)

    # Right score plaque
    pygame.draw.rect(s, (17, 45, 34), (936, 280, 256, 260), border_radius=26)
    pygame.draw.rect(s, (236, 208, 149), (936, 280, 256, 260), 2, border_radius=26)

    # Premium cards
    x = 332
    for _ in range(4):
        pygame.draw.rect(s, (245, 245, 245), (x, 644, 134, 170), border_radius=14)
        pygame.draw.rect(s, (72, 72, 72), (x, 644, 134, 170), 1, border_radius=14)
        x += 156

    # Opponent cards
    x = 372
    for _ in range(4):
        pygame.draw.rect(s, (217, 224, 217), (x, 204, 116, 148), border_radius=12)
        pygame.draw.rect(s, (90, 90, 90), (x, 204, 116, 148), 1, border_radius=12)
        x += 142

    draw_title(s, "Style 3: Premium Tabletop")
    return s


def main() -> None:
    pygame.init()
    pygame.font.init()

    save(broadcast_table(), "layout_broadcast_table.png")
    save(competitive_minimal(), "layout_competitive_minimal.png")
    save(premium_tabletop(), "layout_premium_tabletop.png")
    print("Saved 3 layout mockups to screenshots/")


if __name__ == "__main__":
    main()
