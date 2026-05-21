"""Renderer for the intro settings modal."""

import shutil
from pathlib import Path
from typing import Any

import pygame


def path_preview(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return "<not set>"
    if len(cleaned) <= 62:
        return cleaned
    return "..." + cleaned[-59:]


def voice_startup_warning_text(settings: Any) -> str:
    if settings.bert_voice_backend != "local_ai":
        return ""

    model_path = settings.bert_local_model_path.strip()
    exe_path = settings.bert_local_exe_path.strip() or "piper"
    model_ok = bool(model_path) and Path(model_path).exists()
    exe_ok = shutil.which(exe_path) is not None or Path(exe_path).exists()

    if not model_ok:
        return "Local AI voice is selected but Piper model path is missing/invalid. SAPI fallback active."
    if not exe_ok:
        return "Local AI voice is selected but Piper executable was not found. SAPI fallback active."
    if settings.bert_rvc_enabled:
        rvc_model_ok = bool(settings.bert_rvc_model_path.strip()) and Path(
            settings.bert_rvc_model_path.strip()
        ).exists()
        rvc_exe_path = settings.bert_rvc_exe_path.strip() or "rvc_infer"
        rvc_exe_ok = shutil.which(rvc_exe_path) is not None or Path(rvc_exe_path).exists()
        if not rvc_model_ok or not rvc_exe_ok:
            return "RVC is enabled but not fully configured. Voice runs without RVC until paths are fixed."
    return ""


def draw_settings_modal(
    *,
    screen: pygame.Surface,
    sw: int,
    sh: int,
    settings: Any,
    settings_text_active: str | None,
    ai_level_labels: dict[int, str],
    ui_style_labels: dict[str, str],
) -> dict[str, pygame.Rect]:
    overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    screen.blit(overlay, (0, 0))

    modal = pygame.Rect(sw // 2 - 280, max(10, sh // 2 - 430), 560, 860)
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

    name_label = small_font.render("Your Name:", True, (216, 198, 171))
    screen.blit(name_label, (modal.x + 28, modal.y + 82))
    settings_player_name_rect = pygame.Rect(modal.x + 122, modal.y + 76, 196, 28)
    name_active = settings_text_active == "player_name"
    pygame.draw.rect(
        screen,
        (68, 60, 52) if name_active else (48, 42, 36),
        settings_player_name_rect,
        border_radius=10,
    )
    pygame.draw.rect(
        screen,
        (255, 237, 172) if name_active else (180, 162, 130),
        settings_player_name_rect,
        width=2,
        border_radius=10,
    )
    name_disp = small_font.render(
        (settings.player_name or "Player") + ("|" if name_active else ""),
        True,
        (239, 234, 222),
    )
    screen.blit(
        name_disp,
        (settings_player_name_rect.x + 8, settings_player_name_rect.centery - name_disp.get_height() // 2),
    )

    vol_label = body_font.render(f"Volume: {int(settings.volume * 100)}%", True, (245, 236, 218))
    screen.blit(vol_label, (modal.x + 28, modal.y + 122))
    settings_volume_rect = pygame.Rect(modal.x + 28, modal.y + 154, 420, 18)
    pygame.draw.rect(screen, (69, 56, 43), settings_volume_rect, border_radius=9)
    fill = settings_volume_rect.copy()
    fill.width = max(8, int(settings_volume_rect.width * settings.volume))
    pygame.draw.rect(screen, (214, 176, 91), fill, border_radius=9)
    knob_x = settings_volume_rect.x + int(settings_volume_rect.width * settings.volume)
    knob_x = max(settings_volume_rect.left + 10, min(settings_volume_rect.right - 10, knob_x))
    pygame.draw.circle(screen, (255, 244, 220), (knob_x, settings_volume_rect.centery), 11)
    pygame.draw.circle(screen, (139, 96, 48), (knob_x, settings_volume_rect.centery), 11, 2)

    anim_text = "On" if settings.animations_enabled else "Off"
    settings_anim_rect = pygame.Rect(modal.x + 28, modal.y + 216, 174, 44)
    anim_label = body_font.render(f"Animations: {anim_text}", True, (245, 236, 218))
    screen.blit(anim_label, (modal.x + 28, modal.y + 188))
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
    screen.blit(ai_label, (modal.x + 244, modal.y + 188))
    settings_ai_left_rect = pygame.Rect(modal.x + 244, modal.y + 216, 46, 44)
    settings_ai_right_rect = pygame.Rect(modal.x + 366, modal.y + 216, 46, 44)
    mid_rect = pygame.Rect(modal.x + 300, modal.y + 216, 56, 44)
    for rect, label in ((settings_ai_left_rect, "<"), (settings_ai_right_rect, ">")):
        pygame.draw.rect(screen, (64, 106, 154), rect, border_radius=18)
        pygame.draw.rect(screen, (208, 228, 245), rect, width=2, border_radius=18)
        txt = body_font.render(label, True, (255, 255, 255))
        screen.blit(txt, (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2))
    ai_mid = body_font.render(str(settings.online_ai_level), True, (255, 255, 255))
    pygame.draw.rect(screen, (55, 48, 42), mid_rect, border_radius=18)
    pygame.draw.rect(screen, (233, 205, 153), mid_rect, width=2, border_radius=18)
    screen.blit(
        ai_mid,
        (mid_rect.centerx - ai_mid.get_width() // 2, mid_rect.centery - ai_mid.get_height() // 2),
    )

    style_label = body_font.render("Playfield Style:", True, (245, 236, 218))
    screen.blit(style_label, (modal.x + 28, modal.y + 270))
    settings_style_left_rect = pygame.Rect(modal.x + 28, modal.y + 298, 46, 44)
    settings_style_right_rect = pygame.Rect(modal.x + 402, modal.y + 298, 46, 44)
    style_mid_rect = pygame.Rect(modal.x + 84, modal.y + 298, 312, 44)
    for rect, label in ((settings_style_left_rect, "<"), (settings_style_right_rect, ">")):
        pygame.draw.rect(screen, (64, 106, 154), rect, border_radius=18)
        pygame.draw.rect(screen, (208, 228, 245), rect, width=2, border_radius=18)
        txt = body_font.render(label, True, (255, 255, 255))
        screen.blit(txt, (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2))
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

    voice_style_label = body_font.render("Bert Voice Style:", True, (245, 236, 218))
    screen.blit(voice_style_label, (modal.x + 28, modal.y + 350))
    settings_voice_style_rect = pygame.Rect(modal.x + 216, modal.y + 346, 196, 44)
    pygame.draw.rect(screen, (66, 94, 132), settings_voice_style_rect, border_radius=18)
    pygame.draw.rect(screen, (224, 234, 244), settings_voice_style_rect, width=2, border_radius=18)
    voice_text = small_font.render(f"{settings.bert_voice_style.title()} (click)", True, (255, 255, 255))
    screen.blit(
        voice_text,
        (
            settings_voice_style_rect.centerx - voice_text.get_width() // 2,
            settings_voice_style_rect.centery - voice_text.get_height() // 2,
        ),
    )

    backend_label = body_font.render("Bert Voice Backend:", True, (245, 236, 218))
    screen.blit(backend_label, (modal.x + 28, modal.y + 402))
    settings_voice_backend_rect = pygame.Rect(modal.x + 216, modal.y + 398, 196, 44)
    pygame.draw.rect(screen, (88, 94, 66), settings_voice_backend_rect, border_radius=18)
    pygame.draw.rect(screen, (244, 239, 188), settings_voice_backend_rect, width=2, border_radius=18)
    backend_text = "Local AI" if settings.bert_voice_backend == "local_ai" else "Windows SAPI"
    backend_note = small_font.render(f"{backend_text} (click)", True, (255, 255, 255))
    screen.blit(
        backend_note,
        (
            settings_voice_backend_rect.centerx - backend_note.get_width() // 2,
            settings_voice_backend_rect.centery - backend_note.get_height() // 2,
        ),
    )

    rvc_label = body_font.render("RVC Accent Pass:", True, (245, 236, 218))
    screen.blit(rvc_label, (modal.x + 28, modal.y + 454))
    settings_rvc_toggle_rect = pygame.Rect(modal.x + 216, modal.y + 450, 196, 44)
    rvc_fill = (62, 101, 74) if settings.bert_rvc_enabled else (121, 72, 66)
    pygame.draw.rect(screen, rvc_fill, settings_rvc_toggle_rect, border_radius=18)
    pygame.draw.rect(screen, (244, 239, 188), settings_rvc_toggle_rect, width=2, border_radius=18)
    rvc_text = "Enabled (click)" if settings.bert_rvc_enabled else "Disabled (click)"
    rvc_note = small_font.render(rvc_text, True, (255, 255, 255))
    screen.blit(
        rvc_note,
        (
            settings_rvc_toggle_rect.centerx - rvc_note.get_width() // 2,
            settings_rvc_toggle_rect.centery - rvc_note.get_height() // 2,
        ),
    )

    pitch_label = body_font.render("RVC Pitch Shift:", True, (245, 236, 218))
    screen.blit(pitch_label, (modal.x + 28, modal.y + 506))
    settings_rvc_pitch_left_rect = pygame.Rect(modal.x + 216, modal.y + 502, 46, 44)
    settings_rvc_pitch_right_rect = pygame.Rect(modal.x + 366, modal.y + 502, 46, 44)
    pitch_mid_rect = pygame.Rect(modal.x + 272, modal.y + 502, 84, 44)
    for rect, label in ((settings_rvc_pitch_left_rect, "<"), (settings_rvc_pitch_right_rect, ">")):
        pygame.draw.rect(screen, (64, 106, 154), rect, border_radius=18)
        pygame.draw.rect(screen, (208, 228, 245), rect, width=2, border_radius=18)
        txt = body_font.render(label, True, (255, 255, 255))
        screen.blit(txt, (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2))
    pygame.draw.rect(screen, (55, 48, 42), pitch_mid_rect, border_radius=18)
    pygame.draw.rect(screen, (233, 205, 153), pitch_mid_rect, width=2, border_radius=18)
    pitch_text = body_font.render(str(settings.bert_rvc_pitch_shift), True, (255, 255, 255))
    screen.blit(
        pitch_text,
        (
            pitch_mid_rect.centerx - pitch_text.get_width() // 2,
            pitch_mid_rect.centery - pitch_text.get_height() // 2,
        ),
    )

    settings_voice_test_rect = pygame.Rect(modal.x + 116, modal.y + 556, 248, 44)
    pygame.draw.rect(screen, (90, 74, 142), settings_voice_test_rect, border_radius=18)
    pygame.draw.rect(screen, (222, 212, 248), settings_voice_test_rect, width=2, border_radius=18)
    test_text = body_font.render("Test Bert Voice", True, (255, 255, 255))
    screen.blit(
        test_text,
        (
            settings_voice_test_rect.centerx - test_text.get_width() // 2,
            settings_voice_test_rect.centery - test_text.get_height() // 2,
        ),
    )

    field_font = pygame.font.SysFont("consolas", 16)

    field_col_gap = 16
    field_col_w = (modal.width - 56 - field_col_gap) // 2
    field_left_x = modal.x + 28
    field_right_x = field_left_x + field_col_w + field_col_gap

    local_exe_label = body_font.render("Piper Executable:", True, (245, 236, 218))
    screen.blit(local_exe_label, (field_left_x, modal.y + 614))
    settings_local_exe_rect = pygame.Rect(field_left_x, modal.y + 640, field_col_w, 30)
    local_exe_active = settings_text_active == "local_exe"
    pygame.draw.rect(
        screen,
        (58, 52, 45) if not local_exe_active else (68, 60, 52),
        settings_local_exe_rect,
        border_radius=10,
    )
    pygame.draw.rect(
        screen,
        (222, 212, 188) if not local_exe_active else (255, 237, 172),
        settings_local_exe_rect,
        width=2,
        border_radius=10,
    )
    local_exe_text = field_font.render(path_preview(settings.bert_local_exe_path), True, (239, 234, 222))
    screen.blit(local_exe_text, (settings_local_exe_rect.x + 10, settings_local_exe_rect.y + 6))

    local_model_label = body_font.render("Piper Model Path:", True, (245, 236, 218))
    screen.blit(local_model_label, (field_right_x, modal.y + 614))
    settings_local_model_rect = pygame.Rect(field_right_x, modal.y + 640, field_col_w, 30)
    local_model_active = settings_text_active == "local_model"
    pygame.draw.rect(
        screen,
        (58, 52, 45) if not local_model_active else (68, 60, 52),
        settings_local_model_rect,
        border_radius=10,
    )
    pygame.draw.rect(
        screen,
        (222, 212, 188) if not local_model_active else (255, 237, 172),
        settings_local_model_rect,
        width=2,
        border_radius=10,
    )
    local_model_text = field_font.render(path_preview(settings.bert_local_model_path), True, (239, 234, 222))
    screen.blit(local_model_text, (settings_local_model_rect.x + 10, settings_local_model_rect.y + 6))

    rvc_exe_label = body_font.render("RVC Executable:", True, (245, 236, 218))
    screen.blit(rvc_exe_label, (field_left_x, modal.y + 682))
    settings_rvc_exe_rect = pygame.Rect(field_left_x, modal.y + 708, field_col_w, 30)
    rvc_exe_active = settings_text_active == "rvc_exe"
    pygame.draw.rect(
        screen,
        (58, 52, 45) if not rvc_exe_active else (68, 60, 52),
        settings_rvc_exe_rect,
        border_radius=10,
    )
    pygame.draw.rect(
        screen,
        (222, 212, 188) if not rvc_exe_active else (255, 237, 172),
        settings_rvc_exe_rect,
        width=2,
        border_radius=10,
    )
    rvc_exe_text = field_font.render(path_preview(settings.bert_rvc_exe_path), True, (239, 234, 222))
    screen.blit(rvc_exe_text, (settings_rvc_exe_rect.x + 10, settings_rvc_exe_rect.y + 6))

    rvc_model_label = body_font.render("RVC Model Path:", True, (245, 236, 218))
    screen.blit(rvc_model_label, (field_right_x, modal.y + 682))
    settings_rvc_model_rect = pygame.Rect(field_right_x, modal.y + 708, field_col_w, 30)
    rvc_model_active = settings_text_active == "rvc_model"
    pygame.draw.rect(
        screen,
        (58, 52, 45) if not rvc_model_active else (68, 60, 52),
        settings_rvc_model_rect,
        border_radius=10,
    )
    pygame.draw.rect(
        screen,
        (222, 212, 188) if not rvc_model_active else (255, 237, 172),
        settings_rvc_model_rect,
        width=2,
        border_radius=10,
    )
    rvc_model_text = field_font.render(path_preview(settings.bert_rvc_model_path), True, (239, 234, 222))
    screen.blit(rvc_model_text, (settings_rvc_model_rect.x + 10, settings_rvc_model_rect.y + 6))

    rvc_index_label = body_font.render("RVC Index Path:", True, (245, 236, 218))
    screen.blit(rvc_index_label, (field_left_x, modal.y + 750))
    settings_rvc_index_rect = pygame.Rect(field_left_x, modal.y + 776, field_col_w, 30)
    rvc_index_active = settings_text_active == "rvc_index"
    pygame.draw.rect(
        screen,
        (58, 52, 45) if not rvc_index_active else (68, 60, 52),
        settings_rvc_index_rect,
        border_radius=10,
    )
    pygame.draw.rect(
        screen,
        (222, 212, 188) if not rvc_index_active else (255, 237, 172),
        settings_rvc_index_rect,
        width=2,
        border_radius=10,
    )
    rvc_index_text = field_font.render(path_preview(settings.bert_rvc_index_path), True, (239, 234, 222))
    screen.blit(rvc_index_text, (settings_rvc_index_rect.x + 10, settings_rvc_index_rect.y + 6))

    warn_text = voice_startup_warning_text(settings)
    if warn_text:
        warn = small_font.render(warn_text, True, (235, 193, 136))
        screen.blit(warn, (modal.x + 28, modal.y + 812))

    hint = small_font.render(
        "Click a path box to edit. Enter saves. Esc exits field.", True, (210, 198, 176)
    )
    screen.blit(hint, (modal.centerx - hint.get_width() // 2, modal.bottom - 22))

    return {
        "settings_volume_rect": settings_volume_rect,
        "settings_anim_rect": settings_anim_rect,
        "settings_ai_left_rect": settings_ai_left_rect,
        "settings_ai_right_rect": settings_ai_right_rect,
        "settings_style_left_rect": settings_style_left_rect,
        "settings_style_right_rect": settings_style_right_rect,
        "settings_voice_style_rect": settings_voice_style_rect,
        "settings_voice_backend_rect": settings_voice_backend_rect,
        "settings_rvc_toggle_rect": settings_rvc_toggle_rect,
        "settings_rvc_pitch_left_rect": settings_rvc_pitch_left_rect,
        "settings_rvc_pitch_right_rect": settings_rvc_pitch_right_rect,
        "settings_voice_test_rect": settings_voice_test_rect,
        "settings_local_exe_rect": settings_local_exe_rect,
        "settings_local_model_rect": settings_local_model_rect,
        "settings_rvc_exe_rect": settings_rvc_exe_rect,
        "settings_rvc_model_rect": settings_rvc_model_rect,
        "settings_rvc_index_rect": settings_rvc_index_rect,
        "settings_player_name_rect": settings_player_name_rect,
    }
