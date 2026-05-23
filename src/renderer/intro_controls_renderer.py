"""Renderer for intro-screen controls and difficulty cards."""

import math
from collections.abc import Sequence
from typing import TypedDict

import pygame


class IntroControlsLayout(TypedDict):
    difficulty_buttons: dict[int, pygame.Rect]
    start_btn_rect: pygame.Rect
    online_btn_rect: pygame.Rect
    settings_btn_rect: pygame.Rect
    high_scores_btn_rect: pygame.Rect


def _pick_font(candidates: Sequence[str], size: int, bold: bool = False, italic: bool = False) -> pygame.font.Font:
    for name in candidates:
        try:
            matched = pygame.font.match_font(name, bold=bold, italic=italic)
            if matched:
                return pygame.font.SysFont(name, size, bold=bold, italic=italic)
        except Exception:
            continue
    return pygame.font.SysFont(None, size, bold=bold, italic=italic)


def _draw_lock_badge(
    screen: pygame.Surface,
    center: tuple[int, int],
    scale: float,
    body_color: tuple[int, int, int],
    accent_color: tuple[int, int, int],
) -> None:
    cx, cy = center

    # Warm glow so the lock pops against the blackout card.
    glow_rect = pygame.Rect(cx - int(30 * scale), cy - int(18 * scale), int(60 * scale), int(60 * scale))
    glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
    pygame.draw.ellipse(glow, (255, 190, 70, 39), glow.get_rect())
    screen.blit(glow, glow_rect.topleft)

    # Cast shadow to make the lock stand out against the dark card.
    shadow_rect = pygame.Rect(
        cx - int(21 * scale),
        cy - int(4 * scale),
        int(42 * scale),
        int(30 * scale),
    )
    shadow = pygame.Surface(shadow_rect.size, pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 110), shadow.get_rect(), border_radius=max(4, int(7 * scale)))
    screen.blit(shadow, (shadow_rect.x + int(2 * scale), shadow_rect.y + int(3 * scale)))

    # Body with a beveled, 3D treatment.
    body_w = int(42 * scale)
    body_h = int(30 * scale)
    body_rect = pygame.Rect(cx - body_w // 2, cy - body_h // 2 + int(10 * scale), body_w, body_h)
    pygame.draw.rect(screen, body_color, body_rect, border_radius=max(4, int(7 * scale)))
    highlight = (min(255, body_color[0] + 70), min(255, body_color[1] + 70), min(255, body_color[2] + 70))
    lowlight = (max(0, body_color[0] - 35), max(0, body_color[1] - 35), max(0, body_color[2] - 35))
    pygame.draw.line(
        screen,
        highlight,
        (body_rect.left + int(3 * scale), body_rect.top + int(5 * scale)),
        (body_rect.right - int(4 * scale), body_rect.top + int(5 * scale)),
        max(1, int(2 * scale)),
    )
    pygame.draw.line(
        screen,
        lowlight,
        (body_rect.left + int(3 * scale), body_rect.bottom - int(4 * scale)),
        (body_rect.right - int(4 * scale), body_rect.bottom - int(4 * scale)),
        max(1, int(2 * scale)),
    )
    plate = pygame.Rect(body_rect.left + int(4 * scale), body_rect.top + int(8 * scale), body_rect.width - int(8 * scale), int(7 * scale))
    plate_color = (min(255, body_color[0] + 35), min(255, body_color[1] + 28), min(255, body_color[2] + 18))
    pygame.draw.rect(screen, plate_color, plate, border_radius=max(2, int(2 * scale)))
    pygame.draw.rect(screen, accent_color, body_rect, width=max(1, int(2 * scale)), border_radius=max(4, int(7 * scale)))

    # Thick shackle with metallic highlight.
    shackle_rect = pygame.Rect(
        cx - int(12 * scale),
        cy - int(14 * scale),
        int(24 * scale),
        int(18 * scale),
    )
    stroke = max(1, int(3 * scale))
    pygame.draw.arc(screen, accent_color, shackle_rect, math.pi, 2 * math.pi, stroke)
    leg_y0 = shackle_rect.centery
    leg_y1 = body_rect.top + int(2 * scale)
    pygame.draw.line(screen, accent_color, (shackle_rect.left, leg_y0), (shackle_rect.left, leg_y1), stroke)
    pygame.draw.line(screen, accent_color, (shackle_rect.right, leg_y0), (shackle_rect.right, leg_y1), stroke)
    shackle_highlight = (min(255, accent_color[0] + 50), min(255, accent_color[1] + 50), min(255, accent_color[2] + 50))
    pygame.draw.arc(screen, shackle_highlight, shackle_rect.inflate(-int(2 * scale), -int(2 * scale)), math.pi, 2 * math.pi, max(1, int(1 * scale)))

    # Keyhole
    pygame.draw.circle(screen, accent_color, (cx, cy + int(14 * scale)), max(2, int(2.5 * scale)))
    pygame.draw.rect(
        screen,
        accent_color,
        (cx - max(1, int(1.5 * scale)), cy + int(14 * scale), max(2, int(3 * scale)), max(5, int(6 * scale))),
        border_radius=max(1, int(1 * scale)),
    )
    keyhole_glint = (min(255, accent_color[0] + 45), min(255, accent_color[1] + 45), min(255, accent_color[2] + 45))
    pygame.draw.circle(screen, keyhole_glint, (cx - max(1, int(1 * scale)), cy + int(13 * scale)), max(1, int(1.2 * scale)))


def draw_intro_controls(
    *,
    screen: pygame.Surface,
    sw: int,
    sh: int,
    mouse_pos: tuple[int, int],
    dad_ai_level: int,
    difficulty_options: Sequence[tuple[int, str]],
    difficulty_descriptions: dict[int, str],
    maine_shape: Sequence[tuple[int, int]],
    locked_levels: set[int] | None = None,
) -> IntroControlsLayout:
    locked_level_set = locked_levels or set()
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

    # Clean modern block stack (with robust fallbacks) for all level cards.
    display_stack = [
        "Bahnschrift",
        "Segoe UI Variable Display",
        "Franklin Gothic Demi",
        "Franklin Gothic Heavy",
        "Trebuchet MS",
        "Verdana",
    ]
    supporting_stack = [
        "Bahnschrift",
        "Segoe UI",
        "Franklin Gothic Medium",
        "Trebuchet MS",
        "Verdana",
    ]

    card_name_font = _pick_font(display_stack, 29, bold=True)
    card_badge_font = _pick_font(supporting_stack, 11, bold=True)
    card_desc_font = _pick_font(supporting_stack, 13, bold=False)

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
        is_locked = level in locked_level_set
        hovered = btn_rect.collidepoint(mouse_pos) and not is_locked
        raise_px = 0
        if hovered:
            raise_px = 3
        if level == dad_ai_level:
            raise_px = max(raise_px, 5)
        if is_locked:
            raise_px = 0
        draw_rect = btn_rect.move(0, -raise_px)

        is_bert_selected = level == 4 and level == dad_ai_level
        is_old_house = level == 5
        is_old_house_selected = is_old_house and level == dad_ai_level
        is_hard_selected = level == 3 and level == dad_ai_level
        is_hunter_selected = level in (1, 2, 3) and level == dad_ai_level

        if is_locked:
            btn_color = (16, 16, 18)
            border_color = (68, 68, 72)
            badge_color = (28, 28, 30)
            badge_text_color = (162, 162, 168)
        elif level == 1 and level == dad_ai_level:
            btn_color = (118, 176, 112)
            border_color = (184, 232, 174)
            badge_color = (150, 202, 142)
            badge_text_color = (26, 52, 22)
        elif is_hard_selected:
            btn_color = (56, 10, 12)
            border_color = (206, 64, 68)
            badge_color = (172, 38, 42)
            badge_text_color = (245, 226, 220)
        elif is_hunter_selected:
            btn_color = (207, 112, 26)
            border_color = (240, 152, 58)
            badge_color = (232, 132, 42)
            badge_text_color = (60, 28, 6)
        elif is_old_house_selected:
            # Monochrome "black and white TV" gothic treatment.
            btn_color = (38, 38, 40)
            border_color = (186, 186, 190)
            badge_color = (122, 122, 128)
            badge_text_color = (18, 18, 20)
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

        if is_locked:
            blackout = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
            blackout.fill((0, 0, 0, 140))
            local_points = [(x - draw_rect.x, y - draw_rect.y) for x, y in maine_points]
            clip_surface = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
            pygame.draw.polygon(clip_surface, (255, 255, 255, 255), local_points)
            blackout.blit(clip_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            screen.blit(blackout, draw_rect.topleft)

        if is_bert_selected:
            plaid = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
            tile = 12
            for py in range(0, draw_rect.height, tile):
                for px in range(0, draw_rect.width, tile):
                    is_dark_cell = ((px // tile) + (py // tile)) % 2 == 0
                    cell_color = (8, 6, 6, 224) if is_dark_cell else (186, 30, 38, 216)
                    pygame.draw.rect(plaid, cell_color, (px, py, tile, tile))

            # Add subtle per-tile edging to make the checkerboard read clearer.
            for py in range(0, draw_rect.height, tile):
                pygame.draw.line(plaid, (0, 0, 0, 34), (0, py), (draw_rect.width, py), 1)
            for px in range(0, draw_rect.width, tile):
                pygame.draw.line(plaid, (0, 0, 0, 34), (px, 0), (px, draw_rect.height), 1)

            for px in range(0, draw_rect.width, tile * 2):
                pygame.draw.rect(plaid, (0, 0, 0, 68), (px, 0, 3, draw_rect.height))
            for py in range(0, draw_rect.height, tile * 2):
                pygame.draw.rect(plaid, (148, 26, 30, 52), (0, py, draw_rect.width, 3))

            local_points = [(x - draw_rect.x, y - draw_rect.y) for x, y in maine_points]
            clip_surface = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
            pygame.draw.polygon(clip_surface, (255, 255, 255, 255), local_points)
            plaid.blit(clip_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            screen.blit(plaid, draw_rect.topleft)

        if is_old_house_selected:
            gothic = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
            # Film grain / static noise on a monochrome pass.
            for py in range(0, draw_rect.height, 3):
                for px in range(0, draw_rect.width, 3):
                    grain = 62 + ((px * 17 + py * 31) % 58)
                    pygame.draw.rect(gothic, (grain, grain, grain, 22), (px, py, 3, 3))

            # Scanlines for the black-and-white TV look.
            for py in range(0, draw_rect.height, 4):
                pygame.draw.line(gothic, (8, 8, 8, 38), (0, py), (draw_rect.width, py), 1)

            # Subtle gothic cross-hatch to avoid flat modern card look.
            step = 14
            for px in range(-draw_rect.height, draw_rect.width, step):
                pygame.draw.line(gothic, (170, 170, 176, 22), (px, 0), (px + draw_rect.height, draw_rect.height), 1)
            for px in range(0, draw_rect.width + draw_rect.height, step):
                pygame.draw.line(gothic, (20, 20, 22, 22), (px, 0), (px - draw_rect.height, draw_rect.height), 1)

            local_points = [(x - draw_rect.x, y - draw_rect.y) for x, y in maine_points]
            clip_surface = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
            pygame.draw.polygon(clip_surface, (255, 255, 255, 255), local_points)
            gothic.blit(clip_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            screen.blit(gothic, draw_rect.topleft)

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
            5: "Camp Collinwood",
            6: "Storm Cellar",
        }
        if is_locked:
            badge_labels[6] = "Locked"
        badge_str = badge_labels.get(level, "Challenge")
        badge_spacing = 1 if len(badge_str) >= 14 else 2
        badge_w = tracked_width(card_badge_font, badge_str, badge_spacing)
        badge_h = card_badge_font.get_height()
        max_pill_w = max(56, button_width - 10)
        pill_w, pill_h = min(max_pill_w, badge_w + 18), badge_h + 10
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
            spacing=badge_spacing,
        )

        text_plate = pygame.Surface((max(40, button_width - 24), 56), pygame.SRCALPHA)
        if is_locked:
            text_plate.fill((8, 10, 14, 148))
        elif level == dad_ai_level:
            text_plate.fill((18, 24, 30, 136))
        else:
            text_plate.fill((10, 16, 20, 118))
        text_plate_rect = text_plate.get_rect(center=(draw_rect.centerx, draw_rect.y + 62))
        screen.blit(text_plate, text_plate_rect)
        pygame.draw.rect(screen, (230, 210, 160, 46), text_plate_rect, width=1, border_radius=6)

        level_color = (196, 198, 204) if is_locked else ((255, 252, 235) if level == dad_ai_level else (246, 239, 220))
        if is_old_house_selected:
            level_color = (226, 226, 232) if level == dad_ai_level else (198, 198, 204)
        name_up = "LOCKED" if is_locked else name.upper()
        spacing_map = {
            "EASY": 2,
            "MEDIUM": 1,
            "HARD": 2,
            "BERT": 2,
            "OLD HOUSE": 1,
            "LOCKED": 2,
            "BARNABUS": 1,
        }
        name_spacing = spacing_map.get(name_up, 1)
        name_width = tracked_width(card_name_font, name_up, name_spacing)
        level_x = draw_rect.x + button_width // 2 - name_width // 2
        level_y = draw_rect.y + 36
        tracked(screen, card_name_font, name_up, (0, 0, 0), draw_rect.centerx + 2, level_y + 2, spacing=name_spacing)
        tracked(screen, card_name_font, name_up, level_color, draw_rect.centerx, level_y, spacing=name_spacing)

        if is_locked:
            _draw_lock_badge(
                screen=screen,
                center=(draw_rect.centerx, draw_rect.centery + 16),
                scale=max(0.8, button_width / 130.0),
                body_color=(186, 122, 34),
                accent_color=(255, 226, 148),
            )

        desc_color = (246, 236, 206) if level == dad_ai_level else (216, 228, 214)
        if is_old_house_selected:
            desc_color = (214, 214, 220) if level == dad_ai_level else (182, 182, 188)
        desc_lines = [] if is_locked else difficulty_descriptions.get(level, "").split("\n")
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

    high_scores_btn_rect = pygame.Rect(panel_rect.right - 164, panel_rect.y + 53, 144, 32)
    scores_hover = high_scores_btn_rect.collidepoint(mouse_pos)
    scores_fill = (42, 58, 18) if not scores_hover else (58, 78, 24)
    pygame.draw.rect(screen, scores_fill, high_scores_btn_rect, border_radius=8)
    pygame.draw.rect(screen, (134, 154, 74), high_scores_btn_rect, width=1, border_radius=8)
    trophy = glyph_font.render("\u2605", True, (230, 212, 142))
    scores_text = subtitle_small_font.render("HIGH SCORES", True, (245, 245, 236))
    screen.blit(
        scores_text,
        (
            high_scores_btn_rect.centerx
            - (scores_text.get_width() + 8 + trophy.get_width()) // 2
            + trophy.get_width()
            + 8,
            high_scores_btn_rect.centery - scores_text.get_height() // 2,
        ),
    )
    screen.blit(
        trophy,
        (
            high_scores_btn_rect.centerx - (scores_text.get_width() + 8 + trophy.get_width()) // 2,
            high_scores_btn_rect.centery - trophy.get_height() // 2 - 1,
        ),
    )

    return {
        "difficulty_buttons": difficulty_buttons,
        "start_btn_rect": start_btn_rect,
        "online_btn_rect": online_btn_rect,
        "settings_btn_rect": settings_btn_rect,
        "high_scores_btn_rect": high_scores_btn_rect,
    }
