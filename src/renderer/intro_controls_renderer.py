"""Renderer for intro-screen controls and difficulty cards."""

import math
from typing import TypedDict
from collections.abc import Sequence

import pygame


class IntroControlsLayout(TypedDict):
    difficulty_buttons: dict[int, pygame.Rect]
    start_btn_rect: pygame.Rect
    online_btn_rect: pygame.Rect
    settings_btn_rect: pygame.Rect


def draw_intro_controls(
    *,
    screen: pygame.Surface,
    sw: int,
    sh: int,
    mouse_pos: tuple[int, int],
    dad_ai_level: int,
    difficulty_descriptions: dict[int, str],
    maine_shape: Sequence[tuple[int, int]],
) -> IntroControlsLayout:
    panel_w = min(980, max(640, sw - 120))
    panel_h = min(430, max(330, sh - 250))
    panel_rect = pygame.Rect(sw // 2 - panel_w // 2, sh // 2 - panel_h // 2 + 54, panel_w, panel_h)

    panel_surface = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
    panel_surface.fill((10, 28, 14, 160))
    screen.blit(panel_surface, panel_rect.topleft)
    pygame.draw.rect(screen, (84, 152, 92), panel_rect, width=2, border_radius=18)

    rim = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
    pygame.draw.rect(rim, (140, 200, 148, 40), rim.get_rect().inflate(-4, -4), width=1, border_radius=16)
    screen.blit(rim, panel_rect.topleft)

    panel_pad = 28
    difficulty_options = [(1, "Easy"), (2, "Medium"), (3, "Hard"), (4, "Bert"), (5, "Bert+")]
    button_count = len(difficulty_options)
    available_w = panel_rect.width - panel_pad * 2
    button_spacing = 14
    button_width = max(
        96,
        min(152, (available_w - button_spacing * (button_count - 1)) // max(1, button_count)),
    )
    button_height = 132
    total_width = button_count * button_width + (button_count - 1) * button_spacing
    if total_width > available_w:
        button_spacing = max(8, (available_w - button_count * button_width) // max(1, button_count - 1))
        total_width = button_count * button_width + (button_count - 1) * button_spacing
    if total_width > available_w:
        button_width = max(84, (available_w - button_spacing * (button_count - 1)) // max(1, button_count))
        total_width = button_count * button_width + (button_count - 1) * button_spacing

    start_x = panel_rect.x + panel_pad + max(0, (available_w - total_width) // 2)
    cta_row_y = panel_rect.bottom - 88
    button_y = cta_row_y - button_height - 26

    yankee_font = pygame.font.SysFont("constantia", 22, bold=True, italic=True)
    yankee_line = yankee_font.render("\"Hurry up 'n' pick one there, bub.\"", True, (58, 40, 25))

    speech_w = min(panel_rect.width - 120, yankee_line.get_width() + 42)
    speech_h = 46
    speech_rect = pygame.Rect(sw // 2 - speech_w // 2, panel_rect.y + 12, speech_w, speech_h)

    bubble_scale = 3
    bubble_x = speech_rect.x - 22
    bubble_y = speech_rect.y - 12
    bubble_w = speech_w + 64
    bubble_h = speech_h + 62
    bubble_surface = pygame.Surface((bubble_w * bubble_scale, bubble_h * bubble_scale), pygame.SRCALPHA)

    speech_local = pygame.Rect(
        (speech_rect.x - bubble_x) * bubble_scale,
        (speech_rect.y - bubble_y) * bubble_scale,
        speech_rect.width * bubble_scale,
        speech_rect.height * bubble_scale,
    )

    scale = bubble_scale
    cx = speech_local.centerx
    cy = speech_local.centery
    a = speech_local.width // 2 + 20 * scale
    b = speech_local.height // 2 + 10 * scale
    n = 4.6

    body_points = []
    for i in range(72):
        t = (2 * math.pi * i) / 72
        ct = math.cos(t)
        st = math.sin(t)
        x = cx + a * (1 if ct >= 0 else -1) * (abs(ct) ** (2 / n))
        y = cy + b * (1 if st >= 0 else -1) * (abs(st) ** (2 / n))
        body_points.append((int(x), int(y)))

    shadow_points = [(x, y + 5 * scale) for x, y in body_points]
    pygame.draw.polygon(bubble_surface, (0, 0, 0, 58), shadow_points)
    pygame.draw.polygon(bubble_surface, (245, 239, 225), body_points)
    pygame.draw.polygon(bubble_surface, (124, 96, 64), body_points, width=3 * scale)
    pygame.draw.aalines(bubble_surface, (124, 96, 64), True, body_points)

    inner_points = []
    ia = max(8, a - 14 * scale)
    ib = max(8, b - 12 * scale)
    for i in range(56):
        t = (2 * math.pi * i) / 56
        ct = math.cos(t)
        st = math.sin(t)
        x = cx + ia * (1 if ct >= 0 else -1) * (abs(ct) ** (2 / n))
        y = cy + ib * (1 if st >= 0 else -1) * (abs(st) ** (2 / n))
        inner_points.append((int(x), int(y)))
    pygame.draw.aalines(bubble_surface, (255, 251, 241, 100), True, inner_points)

    bubble_surface = pygame.transform.smoothscale(bubble_surface, (bubble_w, bubble_h))
    screen.blit(bubble_surface, (bubble_x, bubble_y))
    screen.blit(
        yankee_line,
        (speech_rect.centerx - yankee_line.get_width() // 2, speech_rect.centery - yankee_line.get_height() // 2),
    )

    card_name_font = pygame.font.SysFont("segoe ui variable", 29, bold=True)
    card_badge_font = pygame.font.SysFont("segoe ui variable", 11)
    card_desc_font = pygame.font.SysFont("segoe ui variable", 13)

    def outlined(surf: pygame.Surface, font: pygame.font.Font, text: str, color: tuple[int, int, int], ox: int, oy: int, outline_width: int = 2) -> None:
        shadow = font.render(text, True, (0, 0, 0))
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx == 0 and dy == 0:
                    continue
                surf.blit(shadow, (ox + dx, oy + dy))
        surf.blit(font.render(text, True, color), (ox, oy))

    def tracked_width(font: pygame.font.Font, text: str, spacing: int = 4) -> int:
        return sum(font.size(c)[0] for c in text.upper()) + spacing * max(0, len(text) - 1)

    def tracked(surf: pygame.Surface, font: pygame.font.Font, text: str, color: tuple[int, int, int], cx_text: int, y_text: int, spacing: int = 4) -> None:
        x_text = cx_text - tracked_width(font, text, spacing) // 2
        for c in text.upper():
            surf.blit(font.render(c, True, color), (x_text, y_text))
            x_text += font.size(c)[0] + spacing

    difficulty_buttons: dict[int, pygame.Rect] = {}
    for i, (level, name) in enumerate(difficulty_options):
        btn_x = start_x + i * (button_width + button_spacing)
        btn_rect = pygame.Rect(btn_x, button_y, button_width, button_height)
        difficulty_buttons[level] = btn_rect
        hovered = btn_rect.collidepoint(mouse_pos)
        raise_px = 0
        if hovered:
            raise_px = 3
        if level == dad_ai_level:
            raise_px = max(raise_px, 5)
        draw_rect = btn_rect.move(0, -raise_px)

        is_bert_selected = level in (4, 5) and level == dad_ai_level
        is_hunter_selected = level in (1, 2, 3) and level == dad_ai_level

        if is_hunter_selected:
            btn_color = (207, 112, 26)
            border_color = (240, 152, 58)
            badge_color = (232, 132, 42)
            badge_text_color = (60, 28, 6)
        elif is_bert_selected:
            btn_color = (56, 10, 12)
            border_color = (206, 64, 68)
            badge_color = (172, 38, 42)
            badge_text_color = (245, 226, 220)
        elif level == dad_ai_level:
            btn_color = (98, 20, 34)
            border_color = (158, 44, 60)
            badge_color = (158, 44, 60)
            badge_text_color = (16, 6, 8)
        else:
            btn_color = (38, 84, 46)
            border_color = (96, 164, 104)
            badge_color = (58, 118, 66)
            badge_text_color = (224, 244, 222)
            if hovered:
                btn_color = (54, 108, 62)
                border_color = (128, 196, 136)
                badge_color = (74, 140, 82)

        shape_pad = 4
        min_x = min(p[0] for p in maine_shape)
        max_x = max(p[0] for p in maine_shape)
        min_y = min(p[1] for p in maine_shape)
        max_y = max(p[1] for p in maine_shape)
        raw_sw = max(1.0, max_x - min_x)
        raw_sh = max(1.0, max_y - min_y)
        avail_w = draw_rect.width - shape_pad * 2
        avail_h = draw_rect.height - shape_pad * 2
        scale_shape = min(avail_w / raw_sw, avail_h / raw_sh)
        offset_x = draw_rect.x + shape_pad + (avail_w - raw_sw * scale_shape) / 2
        offset_y = draw_rect.y + shape_pad + (avail_h - raw_sh * scale_shape) / 2
        maine_points = []
        for px, py in maine_shape:
            sx = int(offset_x + (px - min_x) * scale_shape)
            sy = int(offset_y + (py - min_y) * scale_shape)
            maine_points.append((sx, sy))

        shadow = pygame.Surface((draw_rect.width + 24, draw_rect.height + 24), pygame.SRCALPHA)
        shadow_pts = [(x - draw_rect.x + 8, y - draw_rect.y + 10) for x, y in maine_points]
        pygame.draw.polygon(shadow, (0, 0, 0, 110), shadow_pts)
        screen.blit(shadow, (draw_rect.x - 4, draw_rect.y - 4))
        pygame.draw.polygon(screen, btn_color, maine_points)

        if is_bert_selected:
            plaid = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
            tile = 12
            for py in range(0, draw_rect.height, tile):
                for px in range(0, draw_rect.width, tile):
                    is_dark_cell = ((px // tile) + (py // tile)) % 2 == 0
                    cell_color = (18, 16, 16, 165) if is_dark_cell else (142, 22, 28, 165)
                    pygame.draw.rect(plaid, cell_color, (px, py, tile, tile))

            for px in range(0, draw_rect.width, tile * 2):
                pygame.draw.rect(plaid, (0, 0, 0, 42), (px, 0, 3, draw_rect.height))
            for py in range(0, draw_rect.height, tile * 2):
                pygame.draw.rect(plaid, (120, 22, 24, 42), (0, py, draw_rect.width, 3))

            local_points = [(x - draw_rect.x, y - draw_rect.y) for x, y in maine_points]
            clip_surface = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
            pygame.draw.polygon(clip_surface, (255, 255, 255, 255), local_points)
            plaid.blit(clip_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            screen.blit(plaid, draw_rect.topleft)

        glow = pygame.Surface((draw_rect.width + 20, draw_rect.height + 20), pygame.SRCALPHA)
        glow_points = [(x - draw_rect.x + 10, y - draw_rect.y + 10) for x, y in maine_points]
        pygame.draw.polygon(glow, (*border_color, 55), glow_points, width=7)
        pygame.draw.polygon(glow, (*border_color, 90), glow_points, width=4)
        screen.blit(glow, (draw_rect.x - 10, draw_rect.y - 10))
        pygame.draw.polygon(screen, border_color, maine_points, width=2)
        hi_border = tuple(min(255, c + 60) for c in border_color)
        pygame.draw.aalines(screen, hi_border, True, maine_points)

        badge_labels = {
            1: "Introductory",
            2: "From Away",
            3: "Native Mainer",
            4: "The Wharf",
            5: "Learning",
        }
        badge_str = badge_labels[level]
        badge_w = tracked_width(card_badge_font, badge_str, 4)
        badge_h = card_badge_font.get_height()
        pill_w, pill_h = badge_w + 24, badge_h + 10
        pill = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
        pygame.draw.rect(pill, (*badge_color, 255), pill.get_rect(), border_radius=10)
        label_cx = draw_rect.centerx
        label_y = draw_rect.y - pill_h - 8
        screen.blit(pill, (label_cx - pill_w // 2, label_y))
        tracked(
            screen,
            card_badge_font,
            badge_str,
            badge_text_color,
            label_cx,
            label_y + (pill_h - badge_h) // 2,
            spacing=4,
        )

        level_color = (255, 252, 235) if level == dad_ai_level else (255, 245, 215)
        name_up = name.upper()
        level_x = draw_rect.x + button_width // 2 - card_name_font.size(name_up)[0] // 2
        level_y = draw_rect.y + 36
        outlined(screen, card_name_font, name_up, level_color, level_x, level_y, outline_width=2)

        desc_color = (255, 245, 210) if level == dad_ai_level else (210, 238, 210)
        desc_lines = difficulty_descriptions[level].split("\n")
        desc_y0 = level_y + card_name_font.get_height() + 5
        for j, line in enumerate(desc_lines):
            desc_x = draw_rect.centerx - card_desc_font.size(line)[0] // 2
            desc_y = desc_y0 + j * 15
            outlined(screen, card_desc_font, line, desc_color, desc_x, desc_y, outline_width=1)

    start_font = pygame.font.SysFont("bahnschrift", 24, bold=True)
    glyph_font = pygame.font.SysFont("segoe ui symbol", 20, bold=True)
    subtitle_small_font = pygame.font.SysFont("candara", 18, bold=True)

    start_button_width = min(320, max(240, panel_rect.width // 3))
    start_button_height = 60
    start_btn_rect = pygame.Rect(
        panel_rect.centerx - start_button_width // 2,
        panel_rect.bottom - start_button_height - 24,
        start_button_width,
        start_button_height,
    )
    start_hover = start_btn_rect.collidepoint(mouse_pos)
    start_draw = start_btn_rect.move(0, -2 if start_hover else 0)
    pygame.draw.rect(screen, (0, 0, 0, 80), start_draw.move(0, 5), border_radius=10)
    pygame.draw.rect(screen, (32, 70, 36) if not start_hover else (42, 88, 48), start_draw, border_radius=10)
    pygame.draw.rect(screen, (96, 152, 102), start_draw, width=1, border_radius=10)

    start_text = start_font.render("START GAME", True, (238, 232, 214))
    start_icon = glyph_font.render("\u25b6", True, (206, 188, 152))
    icon_gap = 10
    screen.blit(
        start_text,
        (
            start_btn_rect.centerx
            - (start_text.get_width() + icon_gap + start_icon.get_width()) // 2
            + start_icon.get_width()
            + icon_gap,
            start_draw.centery - start_text.get_height() // 2,
        ),
    )
    screen.blit(
        start_icon,
        (
            start_btn_rect.centerx - (start_text.get_width() + icon_gap + start_icon.get_width()) // 2,
            start_draw.centery - start_icon.get_height() // 2 - 1,
        ),
    )

    online_button_width = min(230, max(180, panel_rect.width // 4))
    online_button_height = 46
    online_btn_rect = pygame.Rect(
        panel_rect.right - online_button_width,
        panel_rect.bottom + 14,
        online_button_width,
        online_button_height,
    )
    online_hover = online_btn_rect.collidepoint(mouse_pos)
    online_draw = online_btn_rect.move(0, -2 if online_hover else 0)
    pygame.draw.rect(screen, (0, 0, 0, 80), online_draw.move(0, 5), border_radius=10)
    pygame.draw.rect(screen, (44, 72, 108) if not online_hover else (56, 88, 128), online_draw, border_radius=10)
    pygame.draw.rect(screen, (92, 142, 192), online_draw, width=1, border_radius=10)

    online_text = start_font.render("ONLINE MODE", True, (218, 230, 244))
    online_icon = glyph_font.render("\u2606", True, (180, 206, 234))
    screen.blit(
        online_text,
        (
            online_btn_rect.centerx
            - (online_text.get_width() + icon_gap + online_icon.get_width()) // 2
            + online_icon.get_width()
            + icon_gap,
            online_draw.centery - online_text.get_height() // 2,
        ),
    )
    screen.blit(
        online_icon,
        (
            online_btn_rect.centerx - (online_text.get_width() + icon_gap + online_icon.get_width()) // 2,
            online_draw.centery - online_icon.get_height() // 2 - 1,
        ),
    )

    settings_btn_rect = pygame.Rect(panel_rect.right - 144, panel_rect.y + 13, 124, 32)
    settings_hover = settings_btn_rect.collidepoint(mouse_pos)
    settings_fill = (16, 36, 18) if not settings_hover else (26, 52, 30)
    pygame.draw.rect(screen, settings_fill, settings_btn_rect, border_radius=8)
    pygame.draw.rect(screen, (62, 102, 66), settings_btn_rect, width=1, border_radius=8)
    gear = glyph_font.render("\u2699", True, (200, 186, 152))
    settings_text = subtitle_small_font.render("SETTINGS", True, (245, 245, 245))
    screen.blit(
        settings_text,
        (
            settings_btn_rect.centerx
            - (settings_text.get_width() + 8 + gear.get_width()) // 2
            + gear.get_width()
            + 8,
            settings_btn_rect.centery - settings_text.get_height() // 2,
        ),
    )
    screen.blit(
        gear,
        (
            settings_btn_rect.centerx - (settings_text.get_width() + 8 + gear.get_width()) // 2,
            settings_btn_rect.centery - gear.get_height() // 2 - 1,
        ),
    )

    return {
        "difficulty_buttons": difficulty_buttons,
        "start_btn_rect": start_btn_rect,
        "online_btn_rect": online_btn_rect,
        "settings_btn_rect": settings_btn_rect,
    }
