"""Deprecated legacy compatibility module.

The primary game client path is main.py via src.compat.run_classic_client().
This module remains only for compatibility with existing tests and migration tooling.
New runtime wiring should be implemented in src/ modules, not here.
"""

# pyright: reportConstantRedefinition=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnknownLambdaType=false, reportUnusedFunction=false, reportUnusedVariable=false, reportAttributeAccessIssue=false

import argparse
import math
import random
import shutil
import subprocess
import sys
from importlib import import_module
from pathlib import Path
from typing import Any

import pygame

import ai_strategy
import bert_persona
import cards as cribbage_cards
from adapter import EngineAdapter
from animations import EffectsManager
from app_context import AppContext
from assets.maine_shape import maine_shape as MAINE_SHAPE
from audio_manager import AudioManager
from engine import CribbageEngine
from game_state import GameState
from phase_states import PhaseStateMachine
from settings_manager import GameSettings, load_settings, save_settings
from src.controllers import GameApplication, GameController
from src.input import EventHandler
from src.renderer import BoardRenderer, RenderingContext
from src.renderer.intro_controls_renderer import IntroControlsLayout, draw_intro_controls
from src.renderer.settings_modal_renderer import draw_settings_modal, voice_startup_warning_text
from stats_manager import get_player_profile, record_game_result, record_hand_stats
from voice_manager import VoiceManager

# --- Constants ---
CARD_WIDTH = 120
CARD_HEIGHT = 180
FPS = 60

# Legacy global variables for compatibility
MAX_SCORE = 121
game_phase: str = "intro"
dealer: int = 0
crib: list[Any] = []
player1_hand: list[Any] = []
selected_cards: list[int] = []

MAINE_COLORS: dict[str, tuple[int, int, int]] = {
    "cream": (222, 184, 135),
    "gold": (255, 215, 0),
}
THEME: dict[str, tuple[int, int, int]] = {
    "outer_bg": (36, 22, 14),
    "blue": (90, 172, 255),
    "red": (255, 125, 125),
}
PLAYFIELD_ALPHA = 238
PEGGING_Y = 402
AI_LEVELS: dict[int, str] = {
    1: "Easy",
    2: "Standard",
    3: "Hard",
    4: "Gumption",
    5: "Adaptive Bert",
}

player2_hand: list[Any] = []
pegging_pile: list[Any] = []
player_scores: list[int] = [0, 0]
player_turn: int = 0
player_name: str = "Player"
message: str = "Select 2 cards to discard to the crib."

starter_card: Any | None = None
_deck_labels: list[str] = []
_stock_labels: list[str] = []

# These are the 4-card hands kept after discard (used for counting).
player1_kept: list[Any] = []
player2_kept: list[Any] = []

dad_ai_level: int = 2
pegging_passes: list[bool] = [False, False]
last_pegging_player: int | None = None

# Scoring breakdown tracking for end-of-round display
pegging_points: list[int] = [0, 0]  # Points from pegging phase by player
round_breakdown: dict[str, tuple[int, list[tuple[str, list[Any], int]]]] = (
    {  # Details of hand scoring
        "player": (0, []),  # (total_points, breakdown_list)
        "ai": (0, []),
        "crib": (0, []),
    }
)
discard_analysis_message: str = ""

# Engine migration bridge (incremental refactor path)
_ENGINE: CribbageEngine | None = None
_ADAPTER: EngineAdapter | None = None
_PHASE_SM: PhaseStateMachine | None = None
_EFFECTS: EffectsManager | None = None
_LAST_SCREEN_SIZE: tuple[int, int] = (1280, 900)
_MAINE_BACK_SURFACE: pygame.Surface | None = None
_CARD_BACK_CACHE: dict[tuple[int, int], pygame.Surface] = {}
_AUDIO: AudioManager | None = None
_VOICE: VoiceManager | None = None
_SETTINGS = GameSettings()
_CLASSIC_SESSION = AppContext().game_state
_UI_STYLE = "classic"
_UI_STYLES = ["classic", "competitive_minimal", "broadcast_table", "premium_tabletop"]
_UI_STYLE_LABELS = {
    "classic": "Classic",
    "competitive_minimal": "Competitive Minimal",
    "broadcast_table": "Broadcast Table",
    "premium_tabletop": "Premium Tabletop",
}


def _check_for_winner(session: GameState | None = None):
    if session is None:
        scores = list(player_scores)
        _CLASSIC_SESSION.scores = list(scores)
    else:
        scores = list(session.scores)
        player_scores[:] = list(scores)
        _CLASSIC_SESSION.scores = list(scores)
    if scores[0] >= MAX_SCORE and scores[1] >= MAX_SCORE:
        _CLASSIC_SESSION.winner = -1
        return -1
    if scores[0] >= MAX_SCORE:
        _CLASSIC_SESSION.winner = 0
        return 0
    if scores[1] >= MAX_SCORE:
        _CLASSIC_SESSION.winner = 1
        return 1
    _CLASSIC_SESSION.winner = None
    return None


# --- Helper Functions ---
_parse_label = cribbage_cards.parse_card_label
_value_for_15 = cribbage_cards.value_for_fifteen
_label_to_model_card = cribbage_cards.label_to_card


def _dealer_display_name(ai_level: int) -> str:
    return "Bert" if ai_level in (4, 5) else "AI"


def _current_dealer_name() -> str:
    return _dealer_display_name(dad_ai_level)


def _speak_bert(line: str, *, force: bool = False) -> None:
    if _VOICE is None:
        return
    _VOICE.speak_bert(
        line,
        dad_ai_level=dad_ai_level,
        bypass_cooldown=force,
        voice_style=_SETTINGS.bert_voice_style,
    )


def _bert_voice_context() -> dict[str, Any]:
    session = _CLASSIC_SESSION
    player_score = int(session.scores[0]) if len(session.scores) > 0 else int(player_scores[0])
    bert_score = int(session.scores[1]) if len(session.scores) > 1 else int(player_scores[1])
    player_pts = int(round_breakdown.get("player", (0, []))[0])
    bert_pts = int(round_breakdown.get("ai", (0, []))[0])
    crib_pts = int(round_breakdown.get("crib", (0, []))[0])
    posture = bert_persona.level5_play_posture(
        {"player_score": player_score, "bert_score": bert_score}
    )
    return {
        "player_score": player_score,
        "bert_score": bert_score,
        "score_gap": bert_score - player_score,
        "posture": posture,
        "pegging_total": int(get_pegging_total()) if pegging_pile else 0,
        "player_pegging_points": int(pegging_points[0]),
        "bert_pegging_points": int(pegging_points[1]),
        "bert_is_dealer": bool(session.dealer == 1),
        "player_hand_points": player_pts,
        "bert_hand_points": bert_pts,
        "crib_points": crib_pts,
    }


def _speak_bert_event(event: str, *, force: bool = False) -> None:
    phrase = bert_persona.choose_line(
        event=event,
        style=_SETTINGS.bert_voice_style,
        dad_ai_level=dad_ai_level,
        context=_bert_voice_context(),
    )
    if not phrase:
        return
    _speak_bert(phrase, force=force)


def _record_single_player_hand_stats(
    player_points: int,
    ai_points: int,
    dealer_idx: int,
) -> None:
    try:
        record_hand_stats(
            player_name=player_name,
            hand_points=player_points,
            pegging_points=pegging_points[0],
            as_dealer=(dealer_idx == 0),
            mode="single_player",
        )
        record_hand_stats(
            player_name=_current_dealer_name(),
            hand_points=ai_points,
            pegging_points=pegging_points[1],
            as_dealer=(dealer_idx == 1),
            mode="single_player",
        )
    except OSError:
        pass


def _record_single_player_game_result(winner: int) -> None:
    if winner not in (0, 1):
        return

    player_final = int(_CLASSIC_SESSION.scores[0])
    ai_final = int(_CLASSIC_SESSION.scores[1])
    player_won = winner == 0
    player_skunk_for = player_won and ai_final <= 90
    player_skunk_against = (not player_won) and player_final <= 90

    try:
        record_game_result(
            player_name=player_name,
            won=player_won,
            skunk_for=player_skunk_for,
            skunk_against=player_skunk_against,
            final_score=player_final,
            mode="single_player",
        )
        record_game_result(
            player_name=_current_dealer_name(),
            won=not player_won,
            skunk_for=player_skunk_against,
            skunk_against=player_skunk_for,
            final_score=ai_final,
            mode="single_player",
        )
    except OSError:
        pass


def _transition_phase(target_phase: str, *, force: bool = False) -> None:
    global game_phase
    _CLASSIC_SESSION.phase = target_phase
    if _PHASE_SM is not None:
        if _ENGINE is not None:
            _ENGINE.state.phase = target_phase
        transitioned = _PHASE_SM.transition(target_phase, force=force)
        if not transitioned and not force:
            _PHASE_SM.transition(target_phase, force=True)
        if _ENGINE is not None:
            game_phase = _ENGINE.state.phase
            _CLASSIC_SESSION.phase = game_phase
            return
    game_phase = target_phase
    if _ENGINE is not None:
        _ENGINE.state.phase = target_phase


def _sync_classic_session_from_runtime() -> None:
    _CLASSIC_SESSION.phase = game_phase
    _CLASSIC_SESSION.dealer = dealer
    _CLASSIC_SESSION.scores = list(player_scores)
    _CLASSIC_SESSION.player_hand = list(player1_hand)
    _CLASSIC_SESSION.ai_hand = list(player2_hand)
    _CLASSIC_SESSION.crib = list(crib)
    _CLASSIC_SESSION.pegging_pile = list(pegging_pile)
    _CLASSIC_SESSION.message = message
    _CLASSIC_SESSION.selected_cards = list(selected_cards)
    _CLASSIC_SESSION.starter_card = starter_card
    _CLASSIC_SESSION.pegging_passes = list(pegging_passes)
    _CLASSIC_SESSION.last_pegging_player = last_pegging_player
    _CLASSIC_SESSION.player_kept = list(player1_kept)
    _CLASSIC_SESSION.ai_kept = list(player2_kept)
    _CLASSIC_SESSION.dad_ai_level = dad_ai_level


def _sync_runtime_from_classic_session() -> None:
    global game_phase, dealer, player_turn, message, starter_card, last_pegging_player, dad_ai_level
    game_phase = _CLASSIC_SESSION.phase
    dealer = _CLASSIC_SESSION.dealer
    dad_ai_level = _CLASSIC_SESSION.dad_ai_level
    player_scores[:] = list(_CLASSIC_SESSION.scores)
    player1_hand[:] = list(_CLASSIC_SESSION.player_hand)
    player2_hand[:] = list(_CLASSIC_SESSION.ai_hand)
    crib[:] = list(_CLASSIC_SESSION.crib)
    pegging_pile[:] = list(_CLASSIC_SESSION.pegging_pile)
    selected_cards[:] = list(_CLASSIC_SESSION.selected_cards)
    player1_kept[:] = list(_CLASSIC_SESSION.player_kept)
    player2_kept[:] = list(_CLASSIC_SESSION.ai_kept)
    starter_card = _CLASSIC_SESSION.starter_card
    player_turn = _CLASSIC_SESSION.player_turn
    pegging_passes[:] = list(_CLASSIC_SESSION.pegging_passes)
    last_pegging_player = _CLASSIC_SESSION.last_pegging_player
    message = _CLASSIC_SESSION.message


def _canonical_deck_labels() -> list[str]:
    suits = ["clubs", "diamonds", "hearts", "spades"]
    ranks = ["ace", "2", "3", "4", "5", "6", "7", "8", "9", "10", "jack", "queen", "king"]
    return [f"{rank}_of_{suit}" for suit in suits for rank in ranks]


class CardSprite:
    def __init__(self, image: pygame.Surface, pos: tuple[int, int], label: str):
        self.image = pygame.transform.smoothscale(image, (CARD_WIDTH, CARD_HEIGHT))
        self.rect = self.image.get_rect(topleft=pos)
        self.label = label
        self.dragging = False

    def update(self, mouse_pos: tuple[int, int]) -> None:
        if self.dragging:
            self.rect.center = mouse_pos

    def draw(self, screen: pygame.Surface) -> None:
        screen.blit(self.image, self.rect)


class _LabelCard:
    def __init__(self, label: str):
        self.label = label


_ROOT_DIR = Path(__file__).resolve().parent
_ASSETS_DIR = _ROOT_DIR / "assets"
_CARDS_DIR = _ASSETS_DIR / "cards"


def _ensure_card_pngs_from_svgs() -> None:
    """Best-effort: if card SVGs exist but PNGs are missing, attempt conversion.

    This connects the game to the repo's converter scripts without making them a hard dependency.
    """
    try:
        svg_paths = list(_CARDS_DIR.glob("*.svg"))
    except OSError:
        return

    if not svg_paths:
        return

    # Only attempt conversion if any canonical deck PNG is missing.
    missing_any = False
    for label in _canonical_deck_labels():
        if not (_CARDS_DIR / f"{label}.png").exists():
            missing_any = True
            break
    if not missing_any:
        return

    try:
        _converter = import_module("convert_all_svg_to_png")
    except Exception as e:
        print(f"[assets] SVGs found but converter unavailable: {e}")
        return

    try:
        rc = _converter.convert_all_svg_to_png(str(_CARDS_DIR), str(_CARDS_DIR), scale=1.0, bg=None)
        if rc == 0:
            print("[assets] Converted SVG card assets to PNG.")
        else:
            print(f"[assets] SVGΓåÆPNG conversion completed with code {rc}.")
    except Exception as e:
        print(f"[assets] SVGΓåÆPNG conversion failed: {e}")


def _load_image(path: Path) -> pygame.Surface:
    surf = pygame.image.load(str(path))
    # JPGs typically don't have alpha; convert_alpha can behave oddly across drivers.
    if path.suffix.lower() in (".jpg", ".jpeg"):
        return surf.convert()
    return surf.convert_alpha()


def load_card_images() -> dict[str, pygame.Surface]:
    loaded: dict[str, pygame.Surface] = {}
    if _CARDS_DIR.exists():
        for path in _CARDS_DIR.glob("*.png"):
            stem = path.stem.lower()
            if stem in ("black_joker", "red_joker"):
                continue
            # Ignore duplicates like "jack_of_spades2"; we want a clean 52-card deck.
            if stem.endswith("2"):
                continue
            try:
                loaded[stem] = _load_image(path)
            except pygame.error:
                continue

    # Always return a full 52-card dictionary.
    card_images: dict[str, pygame.Surface] = {}
    for label in _canonical_deck_labels():
        if label in loaded:
            card_images[label] = loaded[label]
        else:
            surf = pygame.Surface((CARD_WIDTH, CARD_HEIGHT))
            surf.fill((255, 255, 255))
            pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 2)
            card_images[label] = surf
    return card_images


def fixed_hand_positions(
    player: int,
    n: int,
    screen_width: int,
    screen_height: int,
) -> list[tuple[int, int]]:
    margin = 60
    available_width = screen_width - 2 * margin
    spacing = min((available_width - CARD_WIDTH) // (n - 1), CARD_WIDTH + 20) if n > 1 else 0
    y = max(500, screen_height - CARD_HEIGHT - 84) if player == 1 else 160
    row_w = CARD_WIDTH if n <= 1 else CARD_WIDTH + spacing * (n - 1)
    start_x = max(margin, (screen_width - row_w) // 2)
    return [(start_x + i * spacing, y) for i in range(n)]


def _row_positions(
    n: int,
    screen_width: int,
    y: int,
    card_width: int,
    margin: int = 60,
) -> list[tuple[int, int]]:
    available_width = screen_width - 2 * margin
    spacing = min((available_width - card_width) // (n - 1), card_width + 18) if n > 1 else 0
    row_w = card_width if n <= 1 else card_width + spacing * (n - 1)
    start_x = max(margin, (screen_width - row_w) // 2)
    return [(start_x + i * spacing, y) for i in range(n)]


def _draw_shadowed_panel(screen, rect, fill, border, radius=18, shadow=(6, 7)):
    if _UI_STYLE == "competitive_minimal":
        pygame.draw.rect(screen, fill, rect, border_radius=radius)
        pygame.draw.rect(screen, border, rect, width=1, border_radius=radius)
        return

    shadow_rect = rect.move(shadow)
    pygame.draw.rect(screen, (0, 0, 0, 35), shadow_rect.inflate(10, 10), border_radius=radius + 8)
    pygame.draw.rect(screen, (0, 0, 0, 70), shadow_rect.inflate(4, 4), border_radius=radius + 4)
    pygame.draw.rect(screen, (0, 0, 0, 95), shadow_rect, border_radius=radius)
    pygame.draw.rect(screen, fill, rect, border_radius=radius)
    pygame.draw.rect(screen, border, rect, width=2, border_radius=radius)
    pygame.draw.rect(
        screen, (255, 255, 255, 40), rect.inflate(-6, -6), width=1, border_radius=max(4, radius - 4)
    )


def _draw_board_frame(screen):
    sw, sh = screen.get_width(), screen.get_height()

    if _UI_STYLE == "competitive_minimal":
        screen.fill((12, 14, 20))
        playfield = _playfield_rect(screen)
        for x in range(playfield.left + 20, playfield.right, 140):
            pygame.draw.line(screen, (24, 30, 40), (x, playfield.top), (x, playfield.bottom), 1)
        for y in range(playfield.top + 20, playfield.bottom, 110):
            pygame.draw.line(screen, (24, 30, 40), (playfield.left, y), (playfield.right, y), 1)
        return

    if _UI_STYLE == "broadcast_table":
        screen.fill((11, 38, 28))
        playfield = _playfield_rect(screen)
        pygame.draw.rect(screen, (8, 29, 22), playfield, border_radius=24)
        pygame.draw.rect(screen, (203, 180, 118), playfield, width=2, border_radius=24)
        for y in range(playfield.top + 30, playfield.bottom, 86):
            pygame.draw.line(
                screen,
                (18, 58, 43),
                (playfield.left + 18, y),
                (playfield.right - 18, y),
                1,
            )
        return

    if _UI_STYLE == "premium_tabletop":
        screen.fill((66, 40, 21))
        board_rect = pygame.Rect(20, 20, sw - 40, sh - 40)
        pygame.draw.rect(screen, (92, 58, 31), board_rect, border_radius=36)
        pygame.draw.rect(screen, (186, 134, 74), board_rect, width=3, border_radius=36)
        felt = board_rect.inflate(-40, -40)
        pygame.draw.rect(screen, (26, 86, 56), felt, border_radius=30)
        pygame.draw.rect(screen, (226, 196, 138), felt, width=2, border_radius=30)
        return

    screen.fill(THEME["outer_bg"])

    board_rect = pygame.Rect(24, 24, sw - 48, sh - 48)
    pygame.draw.rect(screen, (158, 106, 64), board_rect, border_radius=34)

    inner_rect = board_rect.inflate(-26, -26)
    pygame.draw.rect(screen, (92, 60, 34), inner_rect, border_radius=28)

    felt_rect = inner_rect.inflate(-28, -28)
    felt_surface = pygame.Surface((felt_rect.width, felt_rect.height), pygame.SRCALPHA)
    pygame.draw.rect(felt_surface, (18, 82, 54), felt_surface.get_rect(), border_radius=22)

    band_w = max(18, felt_rect.width // 18)
    for x in range(felt_rect.left, felt_rect.right, band_w):
        shade = (14, 68, 45) if ((x - felt_rect.left) // band_w) % 2 == 0 else (20, 90, 58)
        local_band = pygame.Rect(x - felt_rect.left, 0, band_w, felt_rect.height)
        pygame.draw.rect(felt_surface, shade, local_band.clip(felt_surface.get_rect()))

    glow = pygame.Surface((felt_rect.width, felt_rect.height), pygame.SRCALPHA)
    for i in range(5):
        alpha = 22 - i * 4
        pygame.draw.rect(
            glow,
            (226, 198, 122, alpha),
            pygame.Rect(
                12 + i * 2, 12 + i * 2, felt_rect.width - 24 - i * 4, felt_rect.height - 24 - i * 4
            ),
            width=2,
            border_radius=18,
        )
    felt_surface.blit(glow, (0, 0))

    vignette = pygame.Surface((felt_rect.width, felt_rect.height), pygame.SRCALPHA)
    pygame.draw.rect(vignette, (0, 0, 0, 0), vignette.get_rect(), border_radius=22)
    pygame.draw.rect(vignette, (0, 0, 0, 58), vignette.get_rect(), width=26, border_radius=22)
    felt_surface.blit(vignette, (0, 0))
    felt_surface.set_alpha(PLAYFIELD_ALPHA)
    screen.blit(felt_surface, felt_rect.topleft)


def _playfield_rect(screen):
    """Return the felt playfield bounds used by gameplay overlays."""
    sw, sh = screen.get_width(), screen.get_height()
    board_rect = pygame.Rect(24, 24, sw - 48, sh - 48)
    inner_rect = board_rect.inflate(-26, -26)
    return inner_rect.inflate(-28, -28)


def _crib_panel_rect(sw, sh):
    ai_row_bottom = 170 + 159
    player_row_top = max(510, sh - CARD_HEIGHT - 70)
    gap_top = ai_row_bottom + 22
    gap_bottom = player_row_top - 22
    crib_h = 136
    crib_y = max(gap_top, min((gap_top + gap_bottom - crib_h) // 2, gap_bottom - crib_h))

    # Keep a dedicated lane on the right for the score panel so it does not
    # overlap the crib/starter panel.
    board_rect = pygame.Rect(24, 24, sw - 48, sh - 48)
    inner_rect = board_rect.inflate(-26, -26)
    playfield = inner_rect.inflate(-28, -28)
    reserve_right = 296  # score panel width + margins + breathing room
    usable_left = playfield.left + 18
    usable_right = playfield.right - reserve_right

    # Fall back gracefully on small windows.
    if usable_right - usable_left < 420:
        usable_right = playfield.right - 18

    usable_width = max(320, usable_right - usable_left)
    crib_w = min(620, usable_width)
    crib_x = usable_left + max(0, (usable_width - crib_w) // 2)
    return pygame.Rect(crib_x, crib_y, crib_w, crib_h)


def _scale_polygon_points(points, target_rect, padding=0.12):
    min_x = min(p[0] for p in points)
    max_x = max(p[0] for p in points)
    min_y = min(p[1] for p in points)
    max_y = max(p[1] for p in points)
    width = max_x - min_x
    height = max_y - min_y
    usable_w = target_rect.width * (1.0 - padding * 2)
    usable_h = target_rect.height * (1.0 - padding * 2)
    scale = min(usable_w / width, usable_h / height)
    offset_x = target_rect.x + (target_rect.width - width * scale) / 2
    offset_y = target_rect.y + (target_rect.height - height * scale) / 2
    return [
        (int(offset_x + (x - min_x) * scale), int(offset_y + (y - min_y) * scale))
        for x, y in points
    ]


def _build_card_back_surface(size):
    w, h = size
    scale = 2
    W, H = w * scale, h * scale
    surf_hi = pygame.Surface((W, H), pygame.SRCALPHA)

    outer = pygame.Rect(0, 0, W, H)
    pygame.draw.rect(surf_hi, (247, 242, 231), outer, border_radius=26)
    pygame.draw.rect(surf_hi, (118, 95, 64), outer, width=4, border_radius=26)

    inset = outer.inflate(-20, -20)
    back = pygame.Surface((inset.width, inset.height), pygame.SRCALPHA)
    pygame.draw.rect(back, (20, 66, 54), back.get_rect(), border_radius=20)

    # Ink depth gradient.
    for y in range(back.get_height()):
        t = y / max(1, back.get_height() - 1)
        r = int(15 + 8 * t)
        g = int(58 + 16 * t)
        b = int(48 + 10 * t)
        pygame.draw.line(back, (r, g, b, 52), (0, y), (back.get_width(), y), 1)

    # Guilloche-style security curves for a realistic deck-back look.
    cx, cy = back.get_width() // 2, back.get_height() // 2
    min_dim = min(back.get_width(), back.get_height())
    rings = max(6, min_dim // 32)
    for i in range(1, rings + 1):
        base_r = int(min_dim * (0.11 + i * 0.045))
        amp = max(3, int(base_r * 0.06))
        pts = []
        for deg in range(0, 361, 3):
            t = math.radians(deg)
            rr = base_r + amp * math.sin(8 * t)
            x = cx + rr * math.cos(t)
            y = cy + rr * math.sin(t)
            pts.append((int(x), int(y)))
        tone = 176 + (i % 2) * 14
        pygame.draw.aalines(back, (tone, tone - 18, tone - 66, 72), True, pts)

    step = max(12, w // 6)
    for d in range(-back.get_height(), back.get_width(), step):
        pygame.draw.line(back, (230, 218, 187, 22), (d, 0), (d + back.get_height(), back.get_height()), 1)
        pygame.draw.line(back, (22, 50, 44, 20), (d, back.get_height()), (d + back.get_height(), 0), 1)

    if _MAINE_BACK_SURFACE is not None:
        tex = pygame.transform.smoothscale(_MAINE_BACK_SURFACE, (back.get_width(), back.get_height())).convert_alpha()
        tex.set_alpha(44)
        back.blit(tex, (0, 0))

    # Multi-ring border lines common in premium decks.
    frame = back.get_rect().inflate(-14, -14)
    pygame.draw.rect(back, (216, 194, 136, 185), frame, width=2, border_radius=16)
    pygame.draw.rect(back, (242, 231, 205, 124), frame.inflate(-10, -10), width=2, border_radius=14)
    pygame.draw.rect(back, (16, 50, 41, 95), frame.inflate(-20, -20), width=2, border_radius=12)

    medallion = pygame.Rect(0, 0, int(back.get_width() * 0.44), int(back.get_height() * 0.32))
    medallion.center = (cx, cy)
    pygame.draw.ellipse(back, (0, 0, 0, 72), medallion.move(2, 3))
    pygame.draw.ellipse(back, (24, 80, 66), medallion)
    pygame.draw.ellipse(back, (226, 202, 146, 192), medallion, width=2)
    pygame.draw.ellipse(back, (249, 238, 211, 132), medallion.inflate(-12, -12), width=1)

    state_poly = _scale_polygon_points(MAINE_SHAPE, medallion.inflate(-34, -24), padding=0.08)
    pygame.draw.polygon(back, (0, 0, 0, 96), [(x + 2, y + 2) for x, y in state_poly])
    pygame.draw.polygon(back, (240, 218, 161), state_poly)
    pygame.draw.lines(back, (92, 70, 39), True, state_poly, 2)

    # Small engraved-style label.
    plaque = pygame.Rect(0, 0, int(back.get_width() * 0.34), int(back.get_height() * 0.08))
    plaque.centerx = cx
    plaque.top = medallion.bottom + 10
    pygame.draw.rect(back, (17, 58, 47), plaque, border_radius=8)
    pygame.draw.rect(back, (218, 194, 136, 165), plaque, width=1, border_radius=8)
    label_font = pygame.font.SysFont("cambria", max(14, int(h * 0.11)), bold=True)
    lbl = label_font.render("MAINE", True, (239, 225, 186))
    lbl_shadow = label_font.render("MAINE", True, (34, 24, 14))
    lx = plaque.centerx - lbl.get_width() // 2
    ly = plaque.centery - lbl.get_height() // 2
    back.blit(lbl_shadow, (lx + 1, ly + 1))
    back.blit(lbl, (lx, ly))

    # Fine corner ornaments.
    r = max(8, int(min_dim * 0.035))
    corners = (
        (22, 22),
        (back.get_width() - 22, 22),
        (22, back.get_height() - 22),
        (back.get_width() - 22, back.get_height() - 22),
    )
    for cx0, cy0 in corners:
        pygame.draw.circle(back, (218, 194, 136, 180), (cx0, cy0), r, width=2)
        pygame.draw.circle(back, (246, 234, 205, 132), (cx0, cy0), max(2, r - 5), width=1)

    sheen = pygame.Surface((back.get_width(), max(1, int(back.get_height() * 0.18))), pygame.SRCALPHA)
    for y in range(sheen.get_height()):
        a = max(0, 26 - y * 2)
        pygame.draw.line(sheen, (255, 255, 255, a), (0, y), (sheen.get_width(), y), 1)
    back.blit(sheen, (0, 4))

    surf_hi.blit(back, inset.topleft)

    # Downsample from high-res canvas to reduce digital pixelation.
    return pygame.transform.smoothscale(surf_hi, (w, h))


def _draw_label(screen, text, pos, font, color, shadow=(0, 0), align_left=True):
    shadow_surf = font.render(text, True, (0, 0, 0))
    text_surf = font.render(text, True, color)
    x, y = pos
    if not align_left:
        x -= text_surf.get_width() // 2
    if shadow != (0, 0):
        screen.blit(shadow_surf, (x + shadow[0], y + shadow[1]))
    screen.blit(text_surf, (x, y))


def _draw_card_back(screen, rect):
    key = (rect.width, rect.height)
    if key not in _CARD_BACK_CACHE:
        _CARD_BACK_CACHE[key] = _build_card_back_surface(key)
    screen.blit(_CARD_BACK_CACHE[key], rect.topleft)


def _draw_scaled_card(screen, surface, rect, size):
    scaled = pygame.transform.smoothscale(surface, size)
    screen.blit(scaled, rect.topleft)


def _pegging_target_center(slot_index):
    sw, sh = _LAST_SCREEN_SIZE
    x = sw // 2 - 220 + slot_index * 26 + 46
    _player_row_top = max(510, sh - CARD_HEIGHT - 70)
    _peg_y = min(PEGGING_Y, _player_row_top - 138 - 62)
    y = _peg_y + 69
    return (x, y)


def _queue_score_popup(player_idx, points):
    if _EFFECTS is None or points <= 0:
        return
    sw, sh = _LAST_SCREEN_SIZE
    x = sw // 2 - 150 if player_idx == 0 else sw // 2 + 150
    y = sh - 220 if player_idx == 0 else 180
    color = THEME["blue"] if player_idx == 0 else THEME["red"]
    _EFFECTS.add_score_popup(f"+{points}", (x, y), color=color)


def get_pegging_total():
    return cribbage_cards.pegging_total(_CLASSIC_SESSION.pegging_pile)


def _score_pegging_play(pile):
    return cribbage_cards.score_pegging_play(pile)


def _score_labels_hand(hand_labels, starter_label, is_crib=False):
    hand_model = [_label_to_model_card(lbl) for lbl in hand_labels]
    starter_model = _label_to_model_card(starter_label)
    total, _ = cribbage_cards.score_hand(hand_model, starter_model, is_crib=is_crib)
    return total


def _choose_dad_discards():
    dad_labels = [c.label for c in _CLASSIC_SESSION.ai_hand]
    return ai_strategy.choose_discard_indices(
        dad_labels=dad_labels,
        dad_ai_level=_CLASSIC_SESSION.dad_ai_level,
        dealer_is_dad=(_CLASSIC_SESSION.dealer == 1),
        canonical_deck_labels=_canonical_deck_labels(),
        score_labels_hand=_score_labels_hand,
        game_state=_CLASSIC_SESSION,
    )


def _choose_dad_pegging_index(current_total):
    hand_labels = [c.label for c in _CLASSIC_SESSION.ai_hand]
    pegging_labels = [c.label for c in _CLASSIC_SESSION.pegging_pile]
    return ai_strategy.choose_pegging_index(
        hand_labels=hand_labels,
        current_total=current_total,
        dad_ai_level=_CLASSIC_SESSION.dad_ai_level,
        value_for_15=_value_for_15,
        parse_label=_parse_label,
        score_pegging_play=_score_pegging_play,
        label_card_factory=_LabelCard,
        current_pegging_labels=pegging_labels,
        estimate_opponent_reply_risk=_estimate_opponent_reply_risk,
        own_score=_CLASSIC_SESSION.scores[1],
        opp_score=_CLASSIC_SESSION.scores[0],
        own_cards_remaining=len(_CLASSIC_SESSION.ai_hand),
        game_state=_CLASSIC_SESSION,
    )


def _choose_auto_player_discard_indices():
    player_labels = [c.label for c in _CLASSIC_SESSION.player_hand]
    return ai_strategy.choose_discard_indices(
        dad_labels=player_labels,
        dad_ai_level=_CLASSIC_SESSION.dad_ai_level,
        dealer_is_dad=(_CLASSIC_SESSION.dealer == 0),
        canonical_deck_labels=_canonical_deck_labels(),
        score_labels_hand=_score_labels_hand,
        game_state=_CLASSIC_SESSION,
    )


def _grade_from_percentile(percentile: float) -> str:
    if percentile >= 97:
        return "A+"
    if percentile >= 90:
        return "A"
    if percentile >= 80:
        return "B"
    if percentile >= 65:
        return "C"
    return "D"


def _build_discard_feedback(pre_discard_labels: list[str], chosen_indices: list[int]) -> str:
    analysis = ai_strategy.analyze_discard_options(
        hand_labels=pre_discard_labels,
        dealer_is_player=(_CLASSIC_SESSION.dealer == 0),
        canonical_deck_labels=_canonical_deck_labels(),
        score_labels_hand=_score_labels_hand,
    )
    if not analysis:
        return ""

    chosen_key = tuple(sorted(chosen_indices))
    chosen = next((opt for opt in analysis if opt.discard_indices == chosen_key), None)
    best = analysis[0]
    if chosen is None:
        return ""

    grade = _grade_from_percentile(chosen.percentile)
    delta = best.expected_points - chosen.expected_points
    best_cards = f"{best.discard_labels[0]}, {best.discard_labels[1]}"
    chosen_cards = f"{chosen.discard_labels[0]}, {chosen.discard_labels[1]}"
    if delta <= 0.05:
        return (
            f"Hand Analyzer: {grade} ({chosen.percentile:.0f}th pct). "
            f"Your discard {chosen_cards} is near-optimal ({chosen.expected_points:.2f} EV)."
        )
    return (
        f"Hand Analyzer: {grade} ({chosen.percentile:.0f}th pct). "
        f"Better discard was {best_cards} for +{delta:.2f} EV "
        f"({best.expected_points:.2f} vs {chosen.expected_points:.2f})."
    )


def _choose_auto_player_pegging_index(current_total):
    best_idx = None
    best_score = -1
    best_value = 99
    for idx, card in enumerate(_CLASSIC_SESSION.player_hand):
        value = _value_for_15(_parse_label(card.label)[0])
        if current_total + value > 31:
            continue
        trial = _CLASSIC_SESSION.pegging_pile + [_LabelCard(card.label)]
        immediate = _score_pegging_play(trial)
        if immediate > best_score or (immediate == best_score and value < best_value):
            best_idx = idx
            best_score = immediate
            best_value = value
    return best_idx


def _estimate_opponent_reply_risk(trial_pile):
    trial_total = sum(_value_for_15(_parse_label(c.label)[0]) for c in trial_pile)
    opponent_hand_size = len(_CLASSIC_SESSION.player_hand)
    if opponent_hand_size <= 0:
        return 0.0

    known_labels = {c.label for c in _CLASSIC_SESSION.ai_hand}
    known_labels.update(c.label for c in trial_pile)
    if _CLASSIC_SESSION.starter_card is not None:
        known_labels.add(_CLASSIC_SESSION.starter_card)

    unseen_pool = [lbl for lbl in _canonical_deck_labels() if lbl not in known_labels]
    if not unseen_pool:
        return 0.0

    sample_size = min(opponent_hand_size, len(unseen_pool))
    sims = min(140, 40 + 20 * opponent_hand_size)
    total_best = 0.0

    for _ in range(sims):
        hypothetical_hand = random.sample(unseen_pool, sample_size)
        best_reply = 0
        for label in hypothetical_hand:
            value = _value_for_15(_parse_label(label)[0])
            if trial_total + value > 31:
                continue
            opp_trial = trial_pile + [_LabelCard(label)]
            best_reply = max(best_reply, _score_pegging_play(opp_trial))
        total_best += best_reply

    return total_best / max(1, sims)


def _finalize_pegging_if_complete():
    return _finalize_pegging_if_complete_for_session(None)


def _finalize_pegging_if_complete_for_session(session):
    should_sync_runtime = False
    if session is None:
        _sync_classic_session_from_runtime()
        s = _CLASSIC_SESSION
        should_sync_runtime = True
    else:
        s = session

    if s.player_hand or s.ai_hand:
        if should_sync_runtime:
            _sync_runtime_from_classic_session()
        return False

    # Last card point if sequence did not already end at 31.
    if s.pegging_pile and get_pegging_total() != 31 and s.last_pegging_player is not None:
        s.scores[s.last_pegging_player] += 1
        pegging_points[s.last_pegging_player] += 1
        if s.last_pegging_player == 0:
            s.message = "Last card for 1 point. Counting hands."
        else:
            s.message = f"{_current_dealer_name()} gets last card for 1 point. Counting hands."
            _speak_bert_event("last_card")
    else:
        s.message = "Counting hands."

    _transition_phase("counting")
    if should_sync_runtime:
        _sync_runtime_from_classic_session()
    return True


def _handle_go(player_idx):
    return _handle_go_for_session(player_idx, None)


def _handle_go_for_session(player_idx, session):
    should_sync_runtime = False
    if session is None:
        _sync_classic_session_from_runtime()
        s = _CLASSIC_SESSION
        should_sync_runtime = True
    else:
        s = session

    s.pegging_passes[player_idx] = True
    other = 1 - player_idx

    if s.pegging_passes[other]:
        if s.pegging_pile and get_pegging_total() < 31 and s.last_pegging_player is not None:
            s.scores[s.last_pegging_player] += 1
            pegging_points[s.last_pegging_player] += 1
            _queue_score_popup(s.last_pegging_player, 1)
            if s.last_pegging_player == 0:
                s.message = "Go for you (+1). New count."
            else:
                s.message = f"Go for {_current_dealer_name()} (+1). New count."
                _speak_bert_event("go_point")
        else:
            s.message = "No plays. New count."
        s.pegging_pile.clear()
        s.pegging_passes[0] = False
        s.pegging_passes[1] = False
        if s.last_pegging_player is not None:
            s.player_turn = 1 - s.last_pegging_player
    else:
        s.player_turn = other
        s.message = "Go. " + (
            f"{_current_dealer_name()}'s turn." if other == 1 else "Your turn."
        )
        if other == 1:
            _speak_bert_event("go_called")

    if should_sync_runtime:
        _sync_runtime_from_classic_session()


def _play_pegging_card(player_idx, idx):
    return _play_pegging_card_for_session(player_idx, idx, None)


def _play_pegging_card_for_session(player_idx, idx, session):
    should_sync_runtime = False
    if session is None:
        _sync_classic_session_from_runtime()
        s = _CLASSIC_SESSION
        should_sync_runtime = True
    else:
        s = session

    if player_idx == 0:
        card = s.player_hand.pop(idx)
    else:
        card = s.ai_hand.pop(idx)

    if _AUDIO is not None:
        _AUDIO.play("card")

    if _EFFECTS is not None and _SETTINGS.animations_enabled:
        start = card.rect.center
        end = _pegging_target_center(len(s.pegging_pile))
        _EFFECTS.add_card_flight(card.image, start, end)

    s.pegging_pile.append(card)
    s.pegging_passes[0] = False
    s.pegging_passes[1] = False

    points = _score_pegging_play(s.pegging_pile)
    s.scores[player_idx] += points
    pegging_points[player_idx] += points
    _queue_score_popup(player_idx, points)
    if points > 0 and _AUDIO is not None:
        _AUDIO.play("score")

    name = (s.player_name or player_name) if player_idx == 0 else _current_dealer_name()
    point_note = f" (+{points})" if points else ""

    if get_pegging_total() == 31:
        s.message = f"{name} played 31{point_note}. New count."
        if _EFFECTS is not None and _SETTINGS.animations_enabled:
            _EFFECTS.trigger_shake(intensity=7, duration_ms=220)
        if player_idx == 1:
            _speak_bert_event("pegging_31")
        s.pegging_pile.clear()
        s.player_turn = 1 - player_idx
    else:
        s.message = f"{name} pegs{point_note}. " + (
            f"{_current_dealer_name()}'s turn." if player_idx == 0 else "Your turn."
        )
        if player_idx == 1 and points > 0:
            _speak_bert_event("pegging_score")
        s.player_turn = 1 - player_idx

    s.last_pegging_player = player_idx
    if should_sync_runtime:
        _sync_runtime_from_classic_session()


# --- Event Handlers ---
def handle_discard(event):
    global discard_analysis_message
    _sync_classic_session_from_runtime()
    s = _CLASSIC_SESSION
    if event.type == pygame.MOUSEBUTTONDOWN:
        for idx, card in enumerate(s.player_hand):
            if card.rect.collidepoint(event.pos) and idx not in s.selected_cards:
                s.selected_cards.append(idx)
                _sync_runtime_from_classic_session()
                if _AUDIO is not None:
                    _AUDIO.play("card")
                if len(s.selected_cards) == 2:
                    pre_discard_labels = [c.label for c in s.player_hand]
                    chosen = sorted(s.selected_cards)
                    discard_analysis_message = _build_discard_feedback(pre_discard_labels, chosen)
                    s.history.append(discard_analysis_message)
                    if _ADAPTER is not None and _ENGINE is not None:
                        # Route discard transition through engine adapter.
                        _sync_runtime_from_classic_session()
                        _ADAPTER.update_engine_from_globals()
                        _ENGINE.handle_discard(s.selected_cards)
                        _ADAPTER.update_globals_from_engine()
                        _sync_classic_session_from_runtime()
                        _speak_bert_event("cards_dealt")
                    else:
                        # Fallback legacy path
                        for i in sorted(s.selected_cards, reverse=True):
                            s.crib.append(s.player_hand.pop(i))
                        dad_discards = _choose_dad_discards()
                        for i in sorted(dad_discards, reverse=True):
                            s.crib.append(s.ai_hand.pop(i))
                        s.player_kept = s.player_hand.copy()
                        s.ai_kept = s.ai_hand.copy()
                        s.starter_card = None
                        if _stock_labels:
                            s.starter_card = _stock_labels.pop(0)
                        _transition_phase("pegging")
                        s.player_turn = 1 - s.dealer
                        s.pegging_passes[0] = False
                        s.pegging_passes[1] = False
                        s.last_pegging_player = None
                        s.message = "Pegging phase begins!"
                        _speak_bert_event("cards_dealt")

                    s.selected_cards = []
                    _sync_runtime_from_classic_session()
                break


def handle_pegging(event, auto_player=False):
    _sync_classic_session_from_runtime()
    s = _CLASSIC_SESSION

    if _finalize_pegging_if_complete_for_session(s):
        _sync_runtime_from_classic_session()
        return

    current_total = get_pegging_total()

    if s.player_turn == 0:  # Player Turn
        player_can_move = any(
            current_total + _value_for_15(_parse_label(c.label)[0]) <= 31 for c in s.player_hand
        )
        if not player_can_move:
            _handle_go_for_session(0, s)
            _sync_runtime_from_classic_session()
            return
        if auto_player and event is None:
            chosen = _choose_auto_player_pegging_index(current_total)
            if chosen is not None:
                _play_pegging_card_for_session(0, chosen, s)
                _check_for_winner(s)
            _finalize_pegging_if_complete_for_session(s)
            _sync_runtime_from_classic_session()
            return
        if event and event.type == pygame.MOUSEBUTTONDOWN:
            for idx, card in enumerate(s.player_hand):
                val = _value_for_15(_parse_label(card.label)[0])
                if card.rect.collidepoint(event.pos) and current_total + val <= 31:
                    _play_pegging_card_for_session(0, idx, s)
                    _check_for_winner(s)
                    break
    else:  # Dealer Turn (AI)
        dad_can_move = any(
            current_total + _value_for_15(_parse_label(c.label)[0]) <= 31 for c in s.ai_hand
        )
        if not dad_can_move:
            _handle_go_for_session(1, s)
            _sync_runtime_from_classic_session()
            return
        chosen = _choose_dad_pegging_index(current_total)
        if chosen is not None:
            _play_pegging_card_for_session(1, chosen, s)
            _check_for_winner(s)

    _finalize_pegging_if_complete_for_session(s)
    _sync_runtime_from_classic_session()


def handle_counting():
    global round_breakdown
    _sync_classic_session_from_runtime()
    s = _CLASSIC_SESSION

    if _ADAPTER is not None and _ENGINE is not None:
        _sync_runtime_from_classic_session()
        _ADAPTER.update_engine_from_globals()
        results = _ENGINE.count_hands(_label_to_model_card)
        _ADAPTER.update_globals_from_engine()
        _sync_classic_session_from_runtime()
        p1_points = results["player"]
        p2_points = results["ai"]
        crib_points = results["crib"]
        # For engine path, breakdown would come from engine; for now use empty
        round_breakdown = {
            "player": (p1_points, []),
            "ai": (p2_points, []),
            "crib": (crib_points, []),
        }
    else:
        if s.starter_card is None:
            s.message = "No starter card available. Press R to reset."
            _transition_phase("end")
            _sync_runtime_from_classic_session()
            return

        starter = _label_to_model_card(s.starter_card)
        p1_hand_model = [_label_to_model_card(c.label) for c in s.player_kept]
        p2_hand_model = [_label_to_model_card(c.label) for c in s.ai_kept]
        crib_model = [_label_to_model_card(c.label) for c in s.crib]

        p1_total, p1_breakdown = cribbage_cards.score_hand(p1_hand_model, starter, is_crib=False)
        p2_total, p2_breakdown = cribbage_cards.score_hand(p2_hand_model, starter, is_crib=False)
        crib_total, crib_breakdown = (
            cribbage_cards.score_hand(crib_model, starter, is_crib=True)
            if len(crib_model) == 4
            else (0, [])
        )
        p1_points = p1_total
        p2_points = p2_total
        crib_points = crib_total

        round_breakdown = {
            "player": (p1_points, p1_breakdown),
            "ai": (p2_points, p2_breakdown),
            "crib": (crib_points, crib_breakdown),
        }

        s.scores[0] += p1_points
        s.scores[1] += p2_points
        s.scores[s.dealer] += crib_points

    if (p1_points + p2_points + crib_points) > 0 and _AUDIO is not None:
        _AUDIO.play("score")

    _record_single_player_hand_stats(p1_points, p2_points, s.dealer)

    w = _check_for_winner()

    # Auto-save game checkpoint after each hand
    s.save_checkpoint()

    if w is None:
        s.message = "Round counted. Review the scoring popup and press R for next round."
        _speak_bert_event("hand_scored")
        _transition_phase("end")
    else:
        _record_single_player_game_result(w)
        if _AUDIO is not None:
            _AUDIO.play("win")
        if w == -1:
            s.message = f"Game Over at {MAX_SCORE}! It's a tie. Press R to return to the intro."
        elif w == 0:
            s.message = (
                f"Game Over! {player_name} wins with {s.scores[0]} points. "
                "Press R to return to the intro."
            )
            _speak_bert_event("player_won", force=True)
        else:
            s.message = (
                f"Game Over! {_current_dealer_name()} wins with {s.scores[1]} points. "
                "Press R to return to the intro."
            )
            _speak_bert_event("bert_won", force=True)
        _transition_phase("game_over")

    _sync_runtime_from_classic_session()


# --- Main Entry ---
def main():
    global message, dealer, player1_hand, player2_hand, game_phase, player_name, pegging_pile, starter_card, _deck_labels, _stock_labels, player_scores, dad_ai_level, last_pegging_player, discard_analysis_message, _UI_STYLE
    global _ENGINE, _ADAPTER, _PHASE_SM, _EFFECTS, _LAST_SCREEN_SIZE, _MAINE_BACK_SURFACE, _CARD_BACK_CACHE, _AUDIO, _VOICE, _SETTINGS
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--online-url", dest="online_url", default="http://127.0.0.1:8787")
    parser.add_argument("--online-ws-url", dest="online_ws_url", default="ws://127.0.0.1:8790")
    parser.add_argument("--volume", dest="volume", type=float, default=None)
    parser.add_argument("--animations", dest="animations", choices=["on", "off"], default=None)
    parser.add_argument("--online-ai-level", dest="online_ai_level", type=int, default=None)
    parser.add_argument("--capture-title", dest="capture_title", default=None)
    parser.add_argument("--capture-discard", dest="capture_discard", default=None)
    parser.add_argument("--capture-gameplay", dest="capture_gameplay", default=None)
    parser.add_argument("--capture-video", dest="capture_video", default=None)
    parser.add_argument(
        "--ui-style",
        dest="ui_style",
        choices=_UI_STYLES,
        default=None,
        help="Optional gameplay style override. If omitted, saved settings style is used.",
    )
    parser.add_argument("--capture-video-fps", dest="capture_video_fps", type=int, default=30)
    parser.add_argument(
        "--capture-video-intro-seconds", dest="capture_video_intro_seconds", type=float, default=1.4
    )
    parser.add_argument(
        "--capture-video-end-seconds", dest="capture_video_end_seconds", type=float, default=1.2
    )
    parser.add_argument(
        "--capture-video-max-seconds", dest="capture_video_max_seconds", type=float, default=90.0
    )
    parser.add_argument("--exit-after-capture", dest="exit_after_capture", action="store_true")
    args, _ = parser.parse_known_args()
    capture_title_pending = bool(args.capture_title)
    capture_discard_pending = bool(args.capture_discard)
    capture_gameplay_pending = bool(args.capture_gameplay)
    capture_video_pending = bool(args.capture_video)

    _SETTINGS = load_settings()
    _UI_STYLE = _SETTINGS.ui_style
    if args.volume is not None:
        _SETTINGS.volume = args.volume
    if args.animations is not None:
        _SETTINGS.animations_enabled = args.animations == "on"
    if args.online_ai_level is not None:
        _SETTINGS.online_ai_level = args.online_ai_level
    if args.ui_style is not None:
        _SETTINGS.ui_style = args.ui_style
    _UI_STYLE = _SETTINGS.ui_style
    _SETTINGS.clamp()
    _UI_STYLE = _SETTINGS.ui_style
    save_settings(_SETTINGS)
    player_name = _SETTINGS.player_name or "Player"

    app = GameApplication()
    app.settings = _SETTINGS
    app.player_name = player_name
    app.ui_style = _UI_STYLE
    app.game_state = _CLASSIC_SESSION

    capture_video_path = Path(args.capture_video).resolve() if capture_video_pending else None
    capture_video_frames_dir = None
    capture_video_frame_index = 0
    capture_intro_frames = 0
    capture_end_frames = 0
    capture_intro_target = max(1, int(args.capture_video_intro_seconds * FPS))
    capture_end_target = max(1, int(args.capture_video_end_seconds * FPS))
    capture_max_frames = max(60, int(args.capture_video_max_seconds * FPS))

    if capture_video_pending:
        assert capture_video_path is not None
        capture_video_frames_dir = capture_video_path.parent / f"{capture_video_path.stem}_frames"
        capture_video_frames_dir.mkdir(parents=True, exist_ok=True)
        for stale in capture_video_frames_dir.glob("frame_*.png"):
            try:
                stale.unlink()
            except OSError:
                pass
        print(f"Starting automated capture to frames: {capture_video_frames_dir}")

    def _save_video_frame():
        nonlocal capture_video_frame_index
        if not capture_video_pending or capture_video_frames_dir is None:
            return
        frame_path = capture_video_frames_dir / f"frame_{capture_video_frame_index:06d}.png"
        pygame.image.save(screen, str(frame_path))
        capture_video_frame_index += 1

    def _finalize_video_capture():
        if (
            not capture_video_pending
            or capture_video_frames_dir is None
            or capture_video_path is None
        ):
            return

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            print("Capture complete, but ffmpeg was not found on PATH.")
            print(f"Frames are available in: {capture_video_frames_dir}")
            return

        capture_video_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            ffmpeg,
            "-y",
            "-framerate",
            str(max(1, args.capture_video_fps)),
            "-i",
            str(capture_video_frames_dir / "frame_%06d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(capture_video_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"Saved gameplay video to: {capture_video_path}")
        except subprocess.CalledProcessError as exc:
            print("ffmpeg encoding failed.")
            if exc.stderr:
                print(exc.stderr)
            print(f"Frames are still available in: {capture_video_frames_dir}")

    pygame.init()
    screen = pygame.display.set_mode((1280, 900), pygame.RESIZABLE)
    pygame.display.set_caption("Upta - The Camp Cribbage Game")
    clock = pygame.time.Clock()
    app.screen = screen
    app.clock = clock
    app.initialize(width=1280, height=900)
    _AUDIO = AudioManager(volume=_SETTINGS.volume)
    _VOICE = VoiceManager(
        enabled=_SETTINGS.bert_voice_enabled,
        backend=_SETTINGS.bert_voice_backend,
        local_ai_model_path=_SETTINGS.bert_local_model_path,
        local_ai_exe_path=_SETTINGS.bert_local_exe_path,
        rvc_enabled=_SETTINGS.bert_rvc_enabled,
        rvc_exe_path=_SETTINGS.bert_rvc_exe_path,
        rvc_model_path=_SETTINGS.bert_rvc_model_path,
        rvc_index_path=_SETTINGS.bert_rvc_index_path,
        rvc_pitch_shift=_SETTINGS.bert_rvc_pitch_shift,
    )

    _ENGINE = CribbageEngine()
    _ADAPTER = EngineAdapter(_ENGINE, sys.modules[__name__])
    _PHASE_SM = PhaseStateMachine(_ENGINE)
    _EFFECTS = EffectsManager()
    hud_renderer = BoardRenderer(RenderingContext(screen=screen, assets=None, ui_style=_UI_STYLE))

    intro_background = None
    for intro_candidate in (
        "table.jpg",
        "table.png",
        "board.jpg",
        "welcome_bg.png",
        "Tony.jpg",
        "name_entry_bg.jpg",
    ):
        intro_path = _ASSETS_DIR / intro_candidate
        if intro_path.exists():
            try:
                intro_background = _load_image(intro_path)
                break
            except pygame.error:
                intro_background = None

    gameplay_background = None
    for candidate in ("name_entry_bg.jpg", "table.jpg", "table.png", "board.jpg"):
        path = _ASSETS_DIR / candidate
        if not path.exists():
            continue
        try:
            gameplay_background = _load_image(path)
            break
        except pygame.error:
            gameplay_background = None
            continue

    maine_back = _ASSETS_DIR / "maine.jpg"
    if maine_back.exists():
        try:
            _MAINE_BACK_SURFACE = _load_image(maine_back)
            _CARD_BACK_CACHE = {}
        except pygame.error:
            _MAINE_BACK_SURFACE = None
            _CARD_BACK_CACHE = {}

    _ensure_card_pngs_from_svgs()
    card_images = load_card_images()

    def _start_fresh_game():
        nonlocal card_images
        global pegging_points, round_breakdown, discard_analysis_message
        # Fresh game from intro
        pegging_points[:] = [0, 0]
        round_breakdown = {"player": (0, []), "ai": (0, []), "crib": (0, [])}
        discard_analysis_message = ""
        player_scores[:] = [0, 0]
        _CLASSIC_SESSION.winner = None
        pegging_pile.clear()
        crib.clear()
        selected_cards.clear()
        player1_kept.clear()
        player2_kept.clear()
        dealer = 0

        _deck_labels[:] = _canonical_deck_labels()
        random.shuffle(_deck_labels)
        starter_card = None
        _stock_labels[:] = _deck_labels[12:].copy()

        player1_hand[:] = [
            CardSprite(card_images[_deck_labels[i]], (0, 0), _deck_labels[i]) for i in range(6)
        ]
        player2_hand[:] = [
            CardSprite(card_images[_deck_labels[i + 6]], (0, 0), _deck_labels[i + 6])
            for i in range(6)
        ]

        if _ENGINE is not None:
            _ENGINE.state.dad_ai_level = dad_ai_level
            _ENGINE.start_new_game(player1_hand, player2_hand, _stock_labels, dealer=dealer)
            if _ADAPTER is not None:
                _ADAPTER.update_globals_from_engine()

        if dad_ai_level in (4, 5):
            _speak_bert_event("cards_dealt", force=True)

        # Start at discard phase
        message = "Select 2 cards to discard to the crib."
        return dealer, starter_card, message

    def _start_next_round():
        """Start the next hand while keeping the running score."""
        global last_pegging_player
        nonlocal card_images
        global pegging_points, round_breakdown, discard_analysis_message
        pegging_points[:] = [0, 0]
        round_breakdown = {"player": (0, []), "ai": (0, []), "crib": (0, [])}
        discard_analysis_message = ""
        pegging_pile.clear()
        crib.clear()
        selected_cards.clear()
        player1_kept.clear()
        player2_kept.clear()
        pegging_passes[0] = False
        pegging_passes[1] = False
        last_pegging_player = None

        # Alternate dealer each hand
        nonlocal_dealer = 1 - dealer

        _deck_labels[:] = _canonical_deck_labels()
        random.shuffle(_deck_labels)
        nonlocal_starter = None
        _stock_labels[:] = _deck_labels[12:].copy()

        player1_hand[:] = [
            CardSprite(card_images[_deck_labels[i]], (0, 0), _deck_labels[i]) for i in range(6)
        ]
        player2_hand[:] = [
            CardSprite(card_images[_deck_labels[i + 6]], (0, 0), _deck_labels[i + 6])
            for i in range(6)
        ]

        if _ENGINE is not None:
            _ENGINE.state.dad_ai_level = dad_ai_level
            _ENGINE.start_next_round(player1_hand, player2_hand, _stock_labels)
            if _ADAPTER is not None:
                _ADAPTER.update_globals_from_engine()

        if dad_ai_level in (4, 5):
            _speak_bert_event("round_start", force=True)

        return nonlocal_dealer, nonlocal_starter, "New Round. Select 2 cards to discard."

    def _prepare_gameplay_preview_state():
        """Build a deterministic pegging-phase board for screenshot capture."""
        global game_phase, message, player_turn, starter_card, last_pegging_player, dealer

        d, sc, msg = _start_fresh_game()
        dealer = d
        starter_card = sc
        message = msg

        # Simulate discards quickly so we can render a real pegging phase.
        if len(player1_hand) >= 2:
            for idx in sorted([0, 1], reverse=True):
                crib.append(player1_hand.pop(idx))

        dad_discards = _choose_dad_discards()
        for idx in sorted(dad_discards, reverse=True):
            crib.append(player2_hand.pop(idx))

        player1_kept[:] = player1_hand.copy()
        player2_kept[:] = player2_hand.copy()

        starter_card = None
        if _stock_labels:
            starter_card = _stock_labels.pop(0)

        pegging_pile.clear()
        pegging_passes[0] = False
        pegging_passes[1] = False
        last_pegging_player = None
        player_turn = 1 - dealer
        _transition_phase("pegging")
        message = "Pegging phase preview."
        _sync_classic_session_from_runtime()

    def _primary_button_rect(sw: int, sh: int) -> pygame.Rect:
        w, h = 260, 60
        return pygame.Rect(sw // 2 - w // 2, sh - 180, w, h)

    # Initialize deck containers used across rounds.
    _deck_labels = _canonical_deck_labels()
    _stock_labels = []

    # Intro screen difficulty buttons and state
    difficulty_buttons: dict[int, pygame.Rect] = {}
    online_btn_rect = None
    settings_btn_rect = None
    settings_open = False
    settings_rects: dict[str, pygame.Rect] = {}
    settings_text_active = None
    difficulty_descriptions = {
        1: "Random play\nEasy wins",
        2: "Monte Carlo\nMixed strategy",
        3: "Risk simulation\nHard opponent",
        4: "Gumption\nMode",
        5: "Learns from play\nAdaptive style",
    }

    def _launch_online_client() -> None:
        pygame.quit()
        cmd = [
            sys.executable,
            str((_ROOT_DIR / "main.py").resolve()),
            "--new-client",
            "--online-url",
            args.online_url,
            "--online-ws-url",
            args.online_ws_url,
            "--volume",
            str(_SETTINGS.volume),
            "--animations",
            "on" if _SETTINGS.animations_enabled else "off",
            "--online-ai-level",
            str(_SETTINGS.online_ai_level),
        ]
        subprocess.Popen(cmd, cwd=str(_ROOT_DIR))

    def _persist_settings() -> None:
        global player_name
        _SETTINGS.player_name = _SETTINGS.player_name or "Player"
        save_settings(_SETTINGS)
        player_name = _SETTINGS.player_name
        app.settings = _SETTINGS
        app.player_name = player_name
        app.ui_style = _UI_STYLE
        if _AUDIO is not None:
            _AUDIO.set_volume(_SETTINGS.volume)
        if _VOICE is not None:
            _VOICE.set_enabled(_SETTINGS.bert_voice_enabled)
            _VOICE.configure_backend(
                _SETTINGS.bert_voice_backend,
                _SETTINGS.bert_local_model_path,
                _SETTINGS.bert_local_exe_path,
                _SETTINGS.bert_rvc_enabled,
                _SETTINGS.bert_rvc_exe_path,
                _SETTINGS.bert_rvc_model_path,
                _SETTINGS.bert_rvc_index_path,
                _SETTINGS.bert_rvc_pitch_shift,
            )

    def _preview_bert_voice() -> None:
        if _VOICE is None:
            return
        preview_level = dad_ai_level if dad_ai_level in (4, 5) else 4
        line = bert_persona.choose_line(
            event="level_selected",
            style=_SETTINGS.bert_voice_style,
            dad_ai_level=preview_level,
        )
        if not line:
            line = "Ayuh. Bert voice test." if _SETTINGS.bert_voice_style == "downeast" else "BERT VOICE TEST."
        _VOICE.speak_bert(
            line,
            dad_ai_level=preview_level,
            bypass_cooldown=True,
            voice_style=_SETTINGS.bert_voice_style,
        )

    def _get_text_field_value(field: str) -> str:
        if field == "player_name":
            return _SETTINGS.player_name
        if field == "local_exe":
            return _SETTINGS.bert_local_exe_path
        if field == "local_model":
            return _SETTINGS.bert_local_model_path
        if field == "rvc_exe":
            return _SETTINGS.bert_rvc_exe_path
        if field == "rvc_model":
            return _SETTINGS.bert_rvc_model_path
        if field == "rvc_index":
            return _SETTINGS.bert_rvc_index_path
        return ""

    def _set_text_field_value(field: str, value: str) -> None:
        if field == "player_name":
            _SETTINGS.player_name = value[:24]
        elif field == "local_exe":
            _SETTINGS.bert_local_exe_path = value
        elif field == "local_model":
            _SETTINGS.bert_local_model_path = value
        elif field == "rvc_exe":
            _SETTINGS.bert_rvc_exe_path = value
        elif field == "rvc_model":
            _SETTINGS.bert_rvc_model_path = value
        elif field == "rvc_index":
            _SETTINGS.bert_rvc_index_path = value

    def _handle_settings_text_key(event: pygame.event.Event) -> bool:
        nonlocal settings_text_active
        if settings_text_active is None:
            return False

        current = _get_text_field_value(settings_text_active)

        if event.key == pygame.K_ESCAPE:
            settings_text_active = None
            return True
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            settings_text_active = None
            _persist_settings()
            return True
        if event.key == pygame.K_BACKSPACE:
            _set_text_field_value(settings_text_active, current[:-1])
            _persist_settings()
            return True

        char = event.unicode
        if char and char.isprintable() and len(current) < 300:
            _set_text_field_value(settings_text_active, current + char)
            _persist_settings()
            return True

        return False

    def _cycle_online_ai(delta: int) -> None:
        levels = [1, 2, 3]
        current_idx = levels.index(_SETTINGS.online_ai_level)
        _SETTINGS.online_ai_level = levels[(current_idx + delta) % len(levels)]
        _persist_settings()

    def _cycle_ui_style(delta: int) -> None:
        global _UI_STYLE
        idx = _UI_STYLES.index(_SETTINGS.ui_style)
        _SETTINGS.ui_style = _UI_STYLES[(idx + delta) % len(_UI_STYLES)]
        _UI_STYLE = _SETTINGS.ui_style
        _persist_settings()

    def _begin_classic_round(*, announce: bool) -> tuple[int, object, str]:
        d, sc, msg = _start_fresh_game()
        _transition_phase("discard")
        if announce:
            _speak_bert_event("game_start", force=True)
        return d, sc, msg

    def _handle_settings_modal_click(pos: tuple[int, int]) -> None:
        nonlocal settings_open, settings_text_active

        settings_volume_rect = settings_rects.get("settings_volume_rect")
        settings_anim_rect = settings_rects.get("settings_anim_rect")
        settings_ai_left_rect = settings_rects.get("settings_ai_left_rect")
        settings_ai_right_rect = settings_rects.get("settings_ai_right_rect")
        settings_style_left_rect = settings_rects.get("settings_style_left_rect")
        settings_style_right_rect = settings_rects.get("settings_style_right_rect")
        settings_voice_style_rect = settings_rects.get("settings_voice_style_rect")
        settings_voice_backend_rect = settings_rects.get("settings_voice_backend_rect")
        settings_rvc_toggle_rect = settings_rects.get("settings_rvc_toggle_rect")
        settings_rvc_pitch_left_rect = settings_rects.get("settings_rvc_pitch_left_rect")
        settings_rvc_pitch_right_rect = settings_rects.get("settings_rvc_pitch_right_rect")
        settings_voice_test_rect = settings_rects.get("settings_voice_test_rect")
        settings_local_exe_rect = settings_rects.get("settings_local_exe_rect")
        settings_local_model_rect = settings_rects.get("settings_local_model_rect")
        settings_rvc_exe_rect = settings_rects.get("settings_rvc_exe_rect")
        settings_rvc_model_rect = settings_rects.get("settings_rvc_model_rect")
        settings_rvc_index_rect = settings_rects.get("settings_rvc_index_rect")
        settings_player_name_rect = settings_rects.get("settings_player_name_rect")

        if settings_volume_rect is not None and settings_volume_rect.collidepoint(pos):
            ratio = (pos[0] - settings_volume_rect.x) / max(1, settings_volume_rect.width)
            _SETTINGS.volume = max(0.0, min(1.0, ratio))
            _persist_settings()
            if _AUDIO is not None:
                _AUDIO.play("score")
            return
        if settings_anim_rect is not None and settings_anim_rect.collidepoint(pos):
            _SETTINGS.animations_enabled = not _SETTINGS.animations_enabled
            _persist_settings()
            return
        if settings_ai_left_rect is not None and settings_ai_left_rect.collidepoint(pos):
            _cycle_online_ai(-1)
            return
        if settings_ai_right_rect is not None and settings_ai_right_rect.collidepoint(pos):
            _cycle_online_ai(1)
            return
        if settings_style_left_rect is not None and settings_style_left_rect.collidepoint(pos):
            _cycle_ui_style(-1)
            return
        if settings_style_right_rect is not None and settings_style_right_rect.collidepoint(pos):
            _cycle_ui_style(1)
            return
        if settings_voice_style_rect is not None and settings_voice_style_rect.collidepoint(pos):
            _SETTINGS.bert_voice_style = "robot" if _SETTINGS.bert_voice_style == "downeast" else "downeast"
            _persist_settings()
            _speak_bert_event("level_selected", force=True)
            return
        if settings_voice_backend_rect is not None and settings_voice_backend_rect.collidepoint(pos):
            _SETTINGS.bert_voice_backend = "local_ai" if _SETTINGS.bert_voice_backend == "sapi" else "sapi"
            _persist_settings()
            _speak_bert_event("level_selected", force=True)
            return
        if settings_rvc_toggle_rect is not None and settings_rvc_toggle_rect.collidepoint(pos):
            _SETTINGS.bert_rvc_enabled = not _SETTINGS.bert_rvc_enabled
            _persist_settings()
            _preview_bert_voice()
            return
        if settings_rvc_pitch_left_rect is not None and settings_rvc_pitch_left_rect.collidepoint(pos):
            _SETTINGS.bert_rvc_pitch_shift = max(-24, _SETTINGS.bert_rvc_pitch_shift - 1)
            _persist_settings()
            _preview_bert_voice()
            return
        if settings_rvc_pitch_right_rect is not None and settings_rvc_pitch_right_rect.collidepoint(pos):
            _SETTINGS.bert_rvc_pitch_shift = min(24, _SETTINGS.bert_rvc_pitch_shift + 1)
            _persist_settings()
            _preview_bert_voice()
            return
        if settings_voice_test_rect is not None and settings_voice_test_rect.collidepoint(pos):
            _preview_bert_voice()
            return
        if settings_local_exe_rect is not None and settings_local_exe_rect.collidepoint(pos):
            settings_text_active = "local_exe"
            return
        if settings_local_model_rect is not None and settings_local_model_rect.collidepoint(pos):
            settings_text_active = "local_model"
            return
        if settings_rvc_exe_rect is not None and settings_rvc_exe_rect.collidepoint(pos):
            settings_text_active = "rvc_exe"
            return
        if settings_rvc_model_rect is not None and settings_rvc_model_rect.collidepoint(pos):
            settings_text_active = "rvc_model"
            return
        if settings_rvc_index_rect is not None and settings_rvc_index_rect.collidepoint(pos):
            settings_text_active = "rvc_index"
            return
        if settings_player_name_rect is not None and settings_player_name_rect.collidepoint(pos):
            settings_text_active = "player_name"
            return

        settings_text_active = None
        settings_open = False

    def _start_next_round_from_end() -> None:
        global dealer, starter_card, message
        d, sc, msg = _start_next_round()
        dealer = d
        starter_card = sc
        message = msg
        controller = app.game_controller
        if controller is not None:
            controller.transition_phase("discard")

    def _handle_end_phase_action(action: dict[str, object]) -> None:
        action_type = str(action.get("type", ""))
        if action_type == "KEYDOWN" and action.get("key") == pygame.K_r:
            _start_next_round_from_end()
            return
        if action_type == "MOUSEBUTTONDOWN" and action.get("button") == 1:
            sw, sh = screen.get_width(), screen.get_height()
            pos = action.get("pos")
            if isinstance(pos, tuple) and _primary_button_rect(sw, sh).collidepoint(pos):
                _start_next_round_from_end()

    def _handle_game_over_action(action: dict[str, object]) -> None:
        action_type = str(action.get("type", ""))
        if action_type == "KEYDOWN" and action.get("key") == pygame.K_r:
            controller = app.game_controller
            if controller is not None:
                controller.transition_phase("intro")
            return
        if action_type == "MOUSEBUTTONDOWN" and action.get("button") == 1:
            sw, sh = screen.get_width(), screen.get_height()
            pos = action.get("pos")
            if isinstance(pos, tuple) and _primary_button_rect(sw, sh).collidepoint(pos):
                controller = app.game_controller
                if controller is not None:
                    controller.transition_phase("intro")

    def _handle_gameplay_action(action: dict[str, object]) -> bool:
        global message, dad_ai_level

        action_type = str(action.get("type", ""))
        if action_type == "QUIT":
            return True

        if action_type == "AI_LEVEL_CHANGE":
            dad_ai_level = 1 if dad_ai_level == 5 else dad_ai_level + 1
            if dad_ai_level in (4, 5):
                message = f"AI level set to {dad_ai_level}. Opponent is now Bert."
                _speak_bert_event("level_selected", force=True)
            else:
                message = f"AI level set to {dad_ai_level}."

        if _CLASSIC_SESSION.phase == "end":
            _handle_end_phase_action(action)

        if _CLASSIC_SESSION.phase == "game_over":
            _handle_game_over_action(action)

        return False

    def _handle_gameplay_capture_outputs() -> bool:
        nonlocal capture_gameplay_pending, capture_discard_pending, capture_end_frames

        if capture_gameplay_pending:
            capture_path = Path(args.capture_gameplay)
            capture_path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(screen, str(capture_path))
            print(f"Saved gameplay screenshot to: {capture_path}")
            capture_gameplay_pending = False
            if args.exit_after_capture:
                pygame.quit()
                return True

        if capture_discard_pending and _CLASSIC_SESSION.phase == "discard":
            capture_path = Path(args.capture_discard)
            capture_path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(screen, str(capture_path))
            print(f"Saved discard screenshot to: {capture_path}")
            capture_discard_pending = False
            if args.exit_after_capture:
                pygame.quit()
                return True

        if capture_video_pending:
            _save_video_frame()

            if _CLASSIC_SESSION.phase in ("end", "game_over"):
                capture_end_frames += 1
            else:
                capture_end_frames = 0

            hit_end_target = capture_end_frames >= capture_end_target
            hit_max_frames = capture_video_frame_index >= capture_max_frames
            if hit_end_target or hit_max_frames:
                _finalize_video_capture()
                pygame.quit()
                return True

        return False

    def _handle_intro_capture_outputs() -> bool:
        nonlocal capture_title_pending, capture_intro_frames
        global dealer, starter_card, message

        if capture_title_pending:
            capture_path = Path(args.capture_title)
            capture_path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(screen, str(capture_path))
            print(f"Saved title screenshot to: {capture_path}")
            capture_title_pending = False
            if args.exit_after_capture:
                pygame.quit()
                return True

        if capture_discard_pending:
            d, sc, msg = _start_fresh_game()
            dealer = d
            starter_card = sc
            message = msg
            _transition_phase("discard")
            _sync_classic_session_from_runtime()

        if capture_video_pending:
            _save_video_frame()
            capture_intro_frames += 1
            if capture_intro_frames >= capture_intro_target:
                d, sc, msg = _start_fresh_game()
                dealer = d
                starter_card = sc
                message = msg
                _transition_phase("discard")
                _sync_classic_session_from_runtime()

        return False

    def _handle_intro_action(action: dict[str, object], mouse_pos: tuple[int, int]) -> bool:
        global dad_ai_level, dealer, starter_card, message
        nonlocal settings_open, settings_text_active

        action_type = str(action.get("type", ""))
        raw_event = action.get("raw_event")

        if action_type == "QUIT":
            app.running = False
            return False

        if (
            action_type == "SETTINGS_TOGGLE"
            and not (settings_open and settings_text_active is not None)
        ):
            settings_open = not settings_open
            if not settings_open:
                settings_text_active = None
            return False

        if (
            action_type == "KEYDOWN"
            and settings_open
            and isinstance(raw_event, pygame.event.Event)
            and _handle_settings_text_key(raw_event)
        ):
            return False

        if action_type == "AI_LEVEL_SELECT" and not settings_open:
            level = action.get("level")
            if isinstance(level, int) and 1 <= level <= 5:
                dad_ai_level = level
                if dad_ai_level in (4, 5):
                    _speak_bert_event("level_selected", force=True)
            return False

        if action_type == "ONLINE_MODE" and not settings_open:
            _launch_online_client()
            return True

        if action_type == "KEYDOWN" and action.get("key") in (pygame.K_RETURN, pygame.K_SPACE):
            if not settings_open:
                d, sc, msg = _begin_classic_round(announce=True)
                dealer = d
                starter_card = sc
                message = msg
            return False

        if action_type == "MOUSEBUTTONDOWN":
            pos = action.get("pos")
            if not isinstance(pos, tuple):
                return False

            if settings_open:
                _handle_settings_modal_click(pos)
                return False

            for level, btn_rect in difficulty_buttons.items():
                if btn_rect.collidepoint(mouse_pos):
                    dad_ai_level = level
                    if dad_ai_level in (4, 5):
                        _speak_bert_event("level_selected", force=True)

            if start_btn_rect.collidepoint(mouse_pos):
                d, sc, msg = _begin_classic_round(announce=True)
                dealer = d
                starter_card = sc
                message = msg
            elif online_btn_rect is not None and online_btn_rect.collidepoint(mouse_pos):
                _launch_online_client()
                return True
            elif settings_btn_rect is not None and settings_btn_rect.collidepoint(mouse_pos):
                settings_open = True
                settings_text_active = None

        return False

    if capture_gameplay_pending:
        _prepare_gameplay_preview_state()

    def _auto_discard_player_hand():
        global game_phase, player_turn, starter_card, message, selected_cards, last_pegging_player

        if len(player1_hand) < 2:
            return

        selected = _choose_auto_player_discard_indices()
        if len(selected) != 2:
            selected = [0, 1]

        if _ADAPTER is not None and _ENGINE is not None:
            _ADAPTER.update_engine_from_globals()
            _ENGINE.handle_discard(selected)
            _ADAPTER.update_globals_from_engine()
        else:
            for i in sorted(selected, reverse=True):
                crib.append(player1_hand.pop(i))
            dad_discards = _choose_dad_discards()
            for i in sorted(dad_discards, reverse=True):
                crib.append(player2_hand.pop(i))
            player1_kept[:] = player1_hand.copy()
            player2_kept[:] = player2_hand.copy()
            starter_card = None
            if _stock_labels:
                starter_card = _stock_labels.pop(0)
            _transition_phase("pegging")
            player_turn = 1 - dealer
            pegging_passes[0] = False
            pegging_passes[1] = False
            last_pegging_player = None
            message = "Pegging phase begins!"

        selected_cards = []

    app.game_controller = GameController(_ENGINE, legacy_module=sys.modules[__name__])
    if app.event_handler is None:
        app.event_handler = EventHandler()

    app.running = True
    while app.running:
        if _SETTINGS.animations_enabled:
            _EFFECTS.update(clock.get_time())

        if _CLASSIC_SESSION.phase == "intro":
            sw, sh = screen.get_width(), screen.get_height()
            mouse_pos = pygame.mouse.get_pos()
            if intro_background is not None:
                scale = 1.06
                bg_w, bg_h = int(sw * scale), int(sh * scale)
                bg = pygame.transform.smoothscale(intro_background, (bg_w, bg_h))
                drift_x = int((mouse_pos[0] / max(1, sw) - 0.5) * 24)
                drift_y = int((mouse_pos[1] / max(1, sh) - 0.5) * 16)
                bg_x = (sw - bg_w) // 2 - drift_x
                bg_y = (sh - bg_h) // 2 - drift_y
                screen.blit(bg, (bg_x, bg_y))
            else:
                screen.fill(THEME["outer_bg"])

            overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
            overlay.fill((11, 9, 12, 126))
            screen.blit(overlay, (0, 0))

            vignette = pygame.Surface((sw, sh), pygame.SRCALPHA)
            pygame.draw.rect(vignette, (0, 0, 0, 90), pygame.Rect(0, 0, sw, sh), width=80)
            screen.blit(vignette, (0, 0))

            title_font = pygame.font.SysFont("constantia", 106, bold=True)
            title_shadow_font = pygame.font.SysFont("constantia", 108, bold=True)
            subtitle_font = pygame.font.SysFont("palatino linotype", 26, bold=True)
            subtitle_small_font = pygame.font.SysFont("candara", 18, bold=True)

            title = title_font.render("Upta", True, MAINE_COLORS["cream"])
            title_outline = title_shadow_font.render("Upta", True, (40, 31, 18))
            title_warm_shadow = title_shadow_font.render("Upta", True, (97, 59, 24))
            subtitle = subtitle_font.render(
                "Play the Hand. Mind the Crib. Beat the Table.", True, (235, 216, 182)
            )
            subtitle_small = subtitle_small_font.render(
                "Maine camp cards, dressed like opening night.", True, (214, 194, 162)
            )
            voice_warning = voice_startup_warning_text(_SETTINGS)

            title_top = 88
            title_to_subtitle_gap = 8
            title_x = sw // 2 - title.get_width() // 2
            title_y = title_top
            subtitle_x = sw // 2 - subtitle.get_width() // 2
            subtitle_y = title_y + title.get_height() + title_to_subtitle_gap
            subtitle_small_x = sw // 2 - subtitle_small.get_width() // 2
            subtitle_small_y = subtitle_y + subtitle.get_height() + 10

            crest_rect = pygame.Rect(sw // 2 - 138, 72, 276, 182)
            crest_surface = pygame.Surface(crest_rect.size, pygame.SRCALPHA)
            pygame.draw.ellipse(crest_surface, (0, 0, 0, 78), crest_surface.get_rect().inflate(-14, -18))
            pygame.draw.ellipse(crest_surface, (25, 41, 33, 172), crest_surface.get_rect().inflate(-24, -30))
            pygame.draw.ellipse(crest_surface, (224, 193, 122, 70), crest_surface.get_rect().inflate(-42, -58), 2)
            screen.blit(crest_surface, crest_rect.topleft)

            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
                screen.blit(title_outline, (title_x + dx, title_y + dy))
            screen.blit(title_warm_shadow, (title_x + 4, title_y + 4))
            screen.blit(title, (title_x, title_y))

            title_glint = title_font.render("Upta", True, MAINE_COLORS["gold"])
            glint_clip = pygame.Rect(
                0, 0, title_glint.get_width(), max(1, title_glint.get_height() // 3)
            )
            screen.blit(title_glint, (title_x, title_y), area=glint_clip)
            screen.blit(subtitle, (subtitle_x, subtitle_y))
            screen.blit(subtitle_small, (subtitle_small_x, subtitle_small_y))
            if voice_warning:
                warn_font = pygame.font.SysFont("segoe ui", 16, bold=True)
                warn_surface = warn_font.render(voice_warning, True, (255, 216, 198))
                warn_rect = pygame.Rect(
                    sw // 2 - warn_surface.get_width() // 2 - 16,
                    subtitle_small_y + subtitle_small.get_height() + 10,
                    warn_surface.get_width() + 32,
                    34,
                )
                pygame.draw.rect(screen, (99, 36, 32), warn_rect, border_radius=12)
                pygame.draw.rect(screen, (214, 120, 100), warn_rect, width=2, border_radius=12)
                screen.blit(
                    warn_surface,
                    (
                        warn_rect.centerx - warn_surface.get_width() // 2,
                        warn_rect.centery - warn_surface.get_height() // 2,
                    ),
                )

            # Player W/L stats badge (always shown above the panel)
            _profile = get_player_profile(player_name)
            _badge_font = pygame.font.SysFont("segoe ui", 15)
            _stats_y = subtitle_small_y + subtitle_small.get_height() + (54 if voice_warning else 14)
            _name_surf = _badge_font.render(player_name, True, (239, 229, 205))
            _wl_surf = _badge_font.render(
                f"  \u2014  {_profile['wins']}W / {_profile['losses']}L", True, (162, 202, 168)
            )
            _badge_total_w = _name_surf.get_width() + _wl_surf.get_width() + 24
            _badge_rect = pygame.Rect(sw // 2 - _badge_total_w // 2, _stats_y, _badge_total_w, 26)
            _badge_surf = pygame.Surface(_badge_rect.size, pygame.SRCALPHA)
            _badge_surf.fill((14, 34, 20, 180))
            screen.blit(_badge_surf, _badge_rect.topleft)
            pygame.draw.rect(screen, (84, 130, 92), _badge_rect, width=1, border_radius=8)
            _bx = _badge_rect.x + 12
            _by = _badge_rect.centery - _name_surf.get_height() // 2
            screen.blit(_name_surf, (_bx, _by))
            screen.blit(_wl_surf, (_bx + _name_surf.get_width(), _by))

            intro_controls: IntroControlsLayout = draw_intro_controls(
                screen=screen,
                sw=sw,
                sh=sh,
                mouse_pos=mouse_pos,
                dad_ai_level=dad_ai_level,
                difficulty_descriptions=difficulty_descriptions,
                maine_shape=MAINE_SHAPE,
            )
            difficulty_buttons = intro_controls["difficulty_buttons"]
            start_btn_rect = intro_controls["start_btn_rect"]
            online_btn_rect = intro_controls["online_btn_rect"]
            settings_btn_rect = intro_controls["settings_btn_rect"]

            if settings_open:
                settings_rects = draw_settings_modal(
                    screen=screen,
                    sw=sw,
                    sh=sh,
                    settings=_SETTINGS,
                    settings_text_active=settings_text_active,
                    ai_level_labels=AI_LEVELS,
                    ui_style_labels=_UI_STYLE_LABELS,
                )

            if _handle_intro_capture_outputs():
                return

            pygame.display.flip()
            clock.tick(FPS)

            mouse_pos = pygame.mouse.get_pos()

            actions = app.event_handler.get_actions()
            for action in actions:
                if _handle_intro_action(action, mouse_pos):
                    return
            continue

        sw, sh = screen.get_width(), screen.get_height()
        _LAST_SCREEN_SIZE = (sw, sh)
        hud_renderer.draw_gameplay_backdrop(
            gameplay_background=gameplay_background,
            playfield_alpha=PLAYFIELD_ALPHA,
        )

        actions = app.event_handler.get_actions()
        for action in actions:
            if _handle_gameplay_action(action):
                app.running = False
                break

        app.game_controller.process(actions)

        # Let the game logic advance even when there are no input events.
        if not capture_gameplay_pending:
            if capture_video_pending and _CLASSIC_SESSION.phase == "discard":
                _auto_discard_player_hand()
            app.game_controller.update(auto_player=capture_video_pending)

        hud_renderer.context.screen = screen
        hud_renderer.context.ui_style = _UI_STYLE
        hud_renderer.draw_classic_hud(
            message=_CLASSIC_SESSION.message,
            dealer=_CLASSIC_SESSION.dealer,
            scores=_CLASSIC_SESSION.scores,
            dad_ai_level=_CLASSIC_SESSION.dad_ai_level,
            player_name=player_name,
            crib_count=len(_CLASSIC_SESSION.crib),
            starter_card=_CLASSIC_SESSION.starter_card,
            card_images=card_images,
            phase=_CLASSIC_SESSION.phase,
        )

        hud_renderer.draw_player_hand_lane(session=_CLASSIC_SESSION, sw=sw, sh=sh)
        hud_renderer.draw_ai_hand_lane(session=_CLASSIC_SESSION, sw=sw)
        pegging_y, pegging_card_size = hud_renderer.draw_pegging_lane(
            session=_CLASSIC_SESSION,
            sw=sw,
            sh=sh,
            card_height=CARD_HEIGHT,
            pegging_y_base=PEGGING_Y,
        )

        if _SETTINGS.animations_enabled:
            _EFFECTS.draw(screen)
            shake_x, shake_y = _EFFECTS.shake_offset()
            if shake_x or shake_y:
                shaken = screen.copy()
                screen.fill((0, 0, 0))
                screen.blit(shaken, (shake_x, shake_y))

        if _CLASSIC_SESSION.phase == "pegging":
            hud_renderer.draw_pegging_total_chip(
                sw=sw,
                pegging_y=pegging_y,
                pegging_card_size=pegging_card_size,
                get_pegging_total=get_pegging_total,
            )

        if _CLASSIC_SESSION.phase == "end":
            hud_renderer.draw_end_phase_scoring(
                session=_CLASSIC_SESSION,
                round_breakdown=round_breakdown,
                player_name=player_name,
                discard_analysis_message=discard_analysis_message,
                sw=sw,
                sh=sh,
            )

        if _CLASSIC_SESSION.phase in ("end", "game_over"):
            hud_renderer.draw_end_or_game_over_button(phase=_CLASSIC_SESSION.phase, sw=sw, sh=sh)

        if _handle_gameplay_capture_outputs():
            return

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
