import sys

import pygame

sys.path.insert(0, ".")
from assets.maine_shape import maine_shape as MAINE_SHAPE

pygame.init()
W, H = 900, 520
screen = pygame.display.set_mode((W, H))
screen.fill((40, 40, 40))

CARD_W, CARD_H = 160, 200
labels = ["Introductory", "From Away", "Native Mainer", "The Wharf"]
colors = [
    (180, 210, 195),
    (210, 175, 130),
    (190, 50, 50),
    (80, 100, 130),
]
badge_text_colors = [(10,44,48),(72,38,10),(245,226,220),(200,220,240)]

font = pygame.font.SysFont("segoe ui", 15)

xs_raw = [p[0] for p in MAINE_SHAPE]
ys_raw = [p[1] for p in MAINE_SHAPE]
raw_sw = max(xs_raw) - min(xs_raw)
raw_sh = max(ys_raw) - min(ys_raw)
min_x = min(xs_raw)
min_y = min(ys_raw)

for i, (label, color, tc) in enumerate(zip(labels, colors, badge_text_colors, strict=False)):
    draw_x = 80 + i * 200
    draw_y = 160
    draw_rect = pygame.Rect(draw_x, draw_y, CARD_W, CARD_H)

    shape_pad = 6
    avail_w = draw_rect.width - shape_pad * 2
    avail_h = draw_rect.height - shape_pad * 2
    ms = min(avail_w / raw_sw, avail_h / raw_sh)
    ox = draw_rect.x + shape_pad + (avail_w - raw_sw * ms) / 2
    oy = draw_rect.y + shape_pad + (avail_h - raw_sh * ms) / 2
    pts = [(int(ox + (p[0]-min_x)*ms), int(oy + (p[1]-min_y)*ms)) for p in MAINE_SHAPE]

    shadow_pts = [(x,y+5) for x,y in pts]
    pygame.draw.polygon(screen, (20,20,20), shadow_pts)
    pygame.draw.polygon(screen, color, pts)
    pygame.draw.aalines(screen, (255,255,255), True, pts)

    # Label above shape
    badge_text = font.render(label, True, tc)
    bg = pygame.Surface((badge_text.get_width() + 18, badge_text.get_height() + 8), pygame.SRCALPHA)
    pygame.draw.rect(bg, (*color, 210), bg.get_rect(), border_radius=9)
    lx = draw_rect.centerx - bg.get_width() // 2
    ly = draw_rect.y - bg.get_height() - 6
    screen.blit(bg, (lx, ly))
    screen.blit(badge_text, (lx + 9, ly + 4))

pygame.display.flip()
pygame.image.save(screen, "screenshots/maine_button_preview.png")
print("saved")
pygame.quit()
