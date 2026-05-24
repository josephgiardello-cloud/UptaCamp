"""Renderer for the intro settings modal."""

from typing import Any

import pygame


def draw_settings_modal(
    *,
    screen: pygame.Surface,
    sw: int,
    sh: int,
    settings: Any,
    settings_text_active: str | None,
    ai_level_labels: dict[int, str],
    ui_style_labels: dict[str, str],
    background_theme_labels: dict[str, str],
) -> dict[str, pygame.Rect]:
    overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    screen.blit(overlay, (0, 0))

    modal = pygame.Rect(sw // 2 - 280, max(20, sh // 2 - 235), 560, 470)
    shadow = modal.move(0, 10)
    pygame.draw.rect(screen, (0, 0, 0, 120), shadow, border_radius=28)
    pygame.draw.rect(screen, (24, 20, 18), modal, border_radius=28)
    pygame.draw.rect(screen, (78, 53, 30), modal.inflate(-12, -12), border_radius=22)
    pygame.draw.rect(screen, (233, 205, 153), modal, width=2, border_radius=28)
    pygame.draw.rect(screen, (255, 241, 205), modal.inflate(-18, -18), width=1, border_radius=22)

    title_font = pygame.font.SysFont("constantia", 34, bold=True)
    body_font = pygame.font.SysFont("candara", 22, bold=True)
    small_font = pygame.font.SysFont("segoe ui", 16)
    title = title_font.render("Camp Settings", True, (249, 236, 207))
    screen.blit(title, (modal.centerx - title.get_width() // 2, modal.y + 16))

    strap = small_font.render("Tune the table before the next hand.", True, (216, 198, 171))
    screen.blit(strap, (modal.centerx - strap.get_width() // 2, modal.y + 56))

    vol_label = body_font.render(f"Volume: {int(settings.volume * 100)}%", True, (245, 236, 218))
    screen.blit(vol_label, (modal.x + 28, modal.y + 98))
    settings_volume_rect = pygame.Rect(modal.x + 28, modal.y + 130, 420, 18)
    pygame.draw.rect(screen, (69, 56, 43), settings_volume_rect, border_radius=9)
    fill = settings_volume_rect.copy()
    fill.width = max(8, int(settings_volume_rect.width * settings.volume))
    pygame.draw.rect(screen, (214, 176, 91), fill, border_radius=9)
    knob_x = settings_volume_rect.x + int(settings_volume_rect.width * settings.volume)
    knob_x = max(settings_volume_rect.left + 10, min(settings_volume_rect.right - 10, knob_x))
    pygame.draw.circle(screen, (255, 244, 220), (knob_x, settings_volume_rect.centery), 11)
    pygame.draw.circle(screen, (139, 96, 48), (knob_x, settings_volume_rect.centery), 11, 2)

    anim_text = "On" if settings.animations_enabled else "Off"
    settings_anim_rect = pygame.Rect(modal.x + 28, modal.y + 192, 174, 44)
    anim_label = body_font.render(f"Animations: {anim_text}", True, (245, 236, 218))
    screen.blit(anim_label, (modal.x + 28, modal.y + 164))
    pygame.draw.rect(
        screen,
        (62, 101, 74) if settings.animations_enabled else (121, 72, 66),
        settings_anim_rect,
        border_radius=22,
    )
    pygame.draw.rect(screen, (255, 239, 212), settings_anim_rect, width=2, border_radius=22)
    toggle_text = body_font.render("Toggle", True, (255, 255, 255))
    screen.blit(
        toggle_text,
        (
            settings_anim_rect.centerx - toggle_text.get_width() // 2,
            settings_anim_rect.centery - toggle_text.get_height() // 2,
        ),
    )

    ai_label = body_font.render(
        f"Online AI Pref: {ai_level_labels[settings.online_ai_level]}",
        True,
        (245, 236, 218),
    )
    screen.blit(ai_label, (modal.x + 244, modal.y + 164))
    settings_ai_left_rect = pygame.Rect(modal.x + 244, modal.y + 192, 46, 44)
    settings_ai_right_rect = pygame.Rect(modal.x + 366, modal.y + 192, 46, 44)
    mid_rect = pygame.Rect(modal.x + 300, modal.y + 192, 56, 44)
    for rect, label in ((settings_ai_left_rect, "<"), (settings_ai_right_rect, ">")):
        pygame.draw.rect(screen, (64, 106, 154), rect, border_radius=18)
        pygame.draw.rect(screen, (208, 228, 245), rect, width=2, border_radius=18)
        txt = body_font.render(label, True, (255, 255, 255))
        screen.blit(
            txt, (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2)
        )
    ai_mid = body_font.render(str(settings.online_ai_level), True, (255, 255, 255))
    pygame.draw.rect(screen, (55, 48, 42), mid_rect, border_radius=18)
    pygame.draw.rect(screen, (233, 205, 153), mid_rect, width=2, border_radius=18)
    screen.blit(
        ai_mid,
        (mid_rect.centerx - ai_mid.get_width() // 2, mid_rect.centery - ai_mid.get_height() // 2),
    )

    style_label = body_font.render("Playfield Style:", True, (245, 236, 218))
    screen.blit(style_label, (modal.x + 28, modal.y + 246))
    settings_style_left_rect = pygame.Rect(modal.x + 28, modal.y + 274, 46, 44)
    settings_style_right_rect = pygame.Rect(modal.x + 402, modal.y + 274, 46, 44)
    style_mid_rect = pygame.Rect(modal.x + 84, modal.y + 274, 312, 44)
    for rect, label in ((settings_style_left_rect, "<"), (settings_style_right_rect, ">")):
        pygame.draw.rect(screen, (64, 106, 154), rect, border_radius=18)
        pygame.draw.rect(screen, (208, 228, 245), rect, width=2, border_radius=18)
        txt = body_font.render(label, True, (255, 255, 255))
        screen.blit(
            txt, (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2)
        )
    pygame.draw.rect(screen, (55, 48, 42), style_mid_rect, border_radius=18)
    pygame.draw.rect(screen, (233, 205, 153), style_mid_rect, width=2, border_radius=18)
    style_text = small_font.render(ui_style_labels[settings.ui_style], True, (255, 255, 255))
    screen.blit(
        style_text,
        (
            style_mid_rect.centerx - style_text.get_width() // 2,
            style_mid_rect.centery - style_text.get_height() // 2,
        ),
    )

    voice_text = "On" if settings.bert_voice_enabled else "Off"
    voice_label = body_font.render(f"Narration: {voice_text}", True, (245, 236, 218))
    screen.blit(voice_label, (modal.x + 28, modal.y + 330))
    settings_voice_rect = pygame.Rect(modal.x + 28, modal.y + 358, 174, 44)
    pygame.draw.rect(
        screen,
        (62, 101, 74) if settings.bert_voice_enabled else (121, 72, 66),
        settings_voice_rect,
        border_radius=22,
    )
    pygame.draw.rect(screen, (255, 239, 212), settings_voice_rect, width=2, border_radius=22)
    voice_toggle_text = body_font.render("Toggle", True, (255, 255, 255))
    screen.blit(
        voice_toggle_text,
        (
            settings_voice_rect.centerx - voice_toggle_text.get_width() // 2,
            settings_voice_rect.centery - voice_toggle_text.get_height() // 2,
        ),
    )

    piper_text = "On" if getattr(settings, "bert_voice_backend", "sapi") == "local_ai" else "Off"
    piper_label = body_font.render(f"Piper (Local AI): {piper_text}", True, (245, 236, 218))
    screen.blit(piper_label, (modal.x + 244, modal.y + 330))
    settings_piper_rect = pygame.Rect(modal.x + 244, modal.y + 358, 174, 44)
    pygame.draw.rect(
        screen,
        (62, 101, 74) if piper_text == "On" else (121, 72, 66),
        settings_piper_rect,
        border_radius=22,
    )
    pygame.draw.rect(screen, (255, 239, 212), settings_piper_rect, width=2, border_radius=22)
    piper_toggle_text = body_font.render("Toggle", True, (255, 255, 255))
    screen.blit(
        piper_toggle_text,
        (
            settings_piper_rect.centerx - piper_toggle_text.get_width() // 2,
            settings_piper_rect.centery - piper_toggle_text.get_height() // 2,
        ),
    )

    footer = small_font.render("Esc closes settings", True, (210, 198, 176))
    screen.blit(footer, (modal.centerx - footer.get_width() // 2, modal.bottom - 36))

    return {
        "settings_volume_rect": settings_volume_rect,
        "settings_anim_rect": settings_anim_rect,
        "settings_ai_left_rect": settings_ai_left_rect,
        "settings_ai_right_rect": settings_ai_right_rect,
        "settings_style_left_rect": settings_style_left_rect,
        "settings_style_right_rect": settings_style_right_rect,
        "settings_voice_rect": settings_voice_rect,
        "settings_piper_rect": settings_piper_rect,
    }
