"""Legacy compatibility module.

The primary game client is now main.py + states/.
This module remains for compatibility with existing tests and migration tooling.
"""

import argparse
import math
import random
import shutil
import subprocess
import sys
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
from assets.woodland_colors import WOODLAND_COLORS
from audio_manager import AudioManager
from engine import CribbageEngine
from game_state import GameState
from phase_states import PhaseStateMachine
from settings_manager import GameSettings, load_settings, save_settings
from src.controllers import GameController
from src.input import EventHandler
from src.renderer import BoardRenderer, RenderingContext
from stats_manager import get_player_profile, record_game_result, record_hand_stats
from voice_manager import VoiceManager


# --- Constants ---
CARD_WIDTH = 120
CARD_HEIGHT = 180
FPS = 60

# Legacy global variables for compatibility
MAX_SCORE = 121
game_phase = "intro"
dealer = 0
crib = []
player1_hand = []
selected_cards = []

MAINE_COLORS = {
    "cream": WOODLAND_COLORS.get("widget_font", (222, 184, 135)),
    "gold": WOODLAND_COLORS.get("selection", (255, 215, 0)),
}

player2_hand: list[Any] = []
pegging_pile: list[Any] = []
player_scores: list[int] = [0, 0]
player_turn = 0
show_computer_hand = False
player_name = "Player"
message = "Select 2 cards to discard to the crib."

starter_card: Any | None = None
_deck_labels: list[str] = []
_stock_labels: list[str] = []

# These are the 4-card hands kept after discard (used for counting).
player1_kept: list[Any] = []
player2_kept: list[Any] = []

winner_index = None  # 0 = player, 1 = dealer, None = no winner yet
dad_ai_level = 2
pegging_passes = [False, False]
last_pegging_player = None

# Scoring breakdown tracking for end-of-round display
pegging_points = [0, 0]  # Points from pegging phase by player
round_breakdown: dict[str, tuple[int, list[tuple[str, list[Any], int]]]] = (
    {  # Details of hand scoring
        "player": (0, []),  # (total_points, breakdown_list)
        "ai": (0, []),
        "crib": (0, []),
    }
)
discard_analysis_message = ""

# Engine migration bridge (incremental refactor path)
_ENGINE = None
_ADAPTER = None
_PHASE_SM = None
_EFFECTS = None
_LAST_SCREEN_SIZE = (1280, 900)
_MAINE_BACK_SURFACE = None
_CARD_BACK_CACHE: dict[tuple[int, int], pygame.Surface] = {}
_AUDIO = None
_VOICE = None
_SETTINGS = GameSettings()
ctx = AppContext()
state: GameState = ctx.game_state
_CLASSIC_SESSION = state
_UI_STYLE = "classic"
_UI_STYLES = ["classic", "competitive_minimal", "broadcast_table", "premium_tabletop"]
_UI_STYLE_LABELS = {
    "classic": "Classic",
    "competitive_minimal": "Competitive Minimal",
    "broadcast_table": "Broadcast Table",
    "premium_tabletop": "Premium Tabletop",
}


def _check_for_winner():
    global winner_index
    scores = list(player_scores)
    _CLASSIC_SESSION.scores = list(player_scores)
    if scores[0] >= MAX_SCORE and scores[1] >= MAX_SCORE:
        winner_index = -1  # tie
        _CLASSIC_SESSION.winner = winner_index
        return winner_index
    if scores[0] >= MAX_SCORE:
        winner_index = 0
        _CLASSIC_SESSION.winner = winner_index
        return winner_index
    if scores[1] >= MAX_SCORE:
        winner_index = 1
        _CLASSIC_SESSION.winner = winner_index
        return winner_index
    winner_index = None
    _CLASSIC_SESSION.winner = winner_index
    return winner_index


# --- Helper Functions ---
_parse_label = cribbage_cards.parse_card_label
_rank_index = cribbage_cards.rank_index
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


def _speak_bert_event(event: str, *, force: bool = False) -> None:
    phrase = bert_persona.choose_line(
        event=event,
        style=_SETTINGS.bert_voice_style,
        dad_ai_level=dad_ai_level,
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


def _canonical_deck_labels():
    suits = ["clubs", "diamonds", "hearts", "spades"]
    ranks = ["ace", "2", "3", "4", "5", "6", "7", "8", "9", "10", "jack", "queen", "king"]
    return [f"{rank}_of_{suit}" for suit in suits for rank in ranks]


class CardSprite:
    def __init__(self, image, pos, label):
        self.image = pygame.transform.smoothscale(image, (CARD_WIDTH, CARD_HEIGHT))
        self.rect = self.image.get_rect(topleft=pos)
        self.label = label
        self.dragging = False

    def update(self, mouse_pos):
        if self.dragging:
            self.rect.center = mouse_pos

    def draw(self, screen):
        screen.blit(self.image, self.rect)


class _LabelCard:
    def __init__(self, label):
        self.label = label


_ROOT_DIR = Path(__file__).resolve().parent
_ASSETS_DIR = _ROOT_DIR / "assets"
_CARDS_DIR = _ASSETS_DIR / "cards"


def _ensure_card_pngs_from_svgs():
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
        import convert_all_svg_to_png as _converter
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


def load_card_images():
    loaded = {}
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
    card_images = {}
    for label in _canonical_deck_labels():
        if label in loaded:
            card_images[label] = loaded[label]
        else:
            surf = pygame.Surface((CARD_WIDTH, CARD_HEIGHT))
            surf.fill((255, 255, 255))
            pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 2)
            card_images[label] = surf
    return card_images


def fixed_hand_positions(player, n, screen_width, screen_height):
    margin = 60
    available_width = screen_width - 2 * margin
    spacing = min((available_width - CARD_WIDTH) // (n - 1), CARD_WIDTH + 20) if n > 1 else 0
    y = max(500, screen_height - CARD_HEIGHT - 84) if player == 1 else 160
    row_w = CARD_WIDTH if n <= 1 else CARD_WIDTH + spacing * (n - 1)
    start_x = max(margin, (screen_width - row_w) // 2)
    return [(start_x + i * spacing, y) for i in range(n)]


def _row_positions(n, screen_width, y, card_width, margin=60):
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


def _draw_score_panel(screen, dealer, player_scores, dad_ai_level, player_name):
    dealer_name = _dealer_display_name(dad_ai_level)
    playfield = _playfield_rect(screen)
    panel_w, panel_h = 252, 172
    panel_margin = 20
    dealer_row_bottom = 170 + 159
    # Keep the score box below dealer cards and fully inside the felt area.
    panel_x = playfield.right - panel_w - panel_margin
    panel_y = max(playfield.top + panel_margin, dealer_row_bottom + 16)
    panel_y = min(panel_y, playfield.bottom - panel_h - panel_margin)
    panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
    if _UI_STYLE == "competitive_minimal":
        _draw_shadowed_panel(screen, panel_rect, (18, 22, 30), (104, 120, 150), radius=20)
    elif _UI_STYLE == "broadcast_table":
        _draw_shadowed_panel(screen, panel_rect, (14, 33, 25), (189, 167, 112), radius=22)
    elif _UI_STYLE == "premium_tabletop":
        _draw_shadowed_panel(screen, panel_rect, (24, 54, 40), (230, 200, 144), radius=24)
    else:
        _draw_shadowed_panel(screen, panel_rect, (26, 38, 31), (201, 174, 108), radius=26)

    title_font = pygame.font.SysFont("cambria", 24, bold=True)
    body_font = pygame.font.SysFont("segoe ui", 16, bold=True)
    small_font = pygame.font.SysFont("segoe ui", 13)

    _draw_label(
        screen,
        "Cribbage",
        (panel_rect.x + 18, panel_rect.y + 12),
        title_font,
        (220, 230, 250) if _UI_STYLE == "competitive_minimal" else (240, 227, 188),
    )
    _draw_label(
        screen,
        f"Dealer: {'You' if dealer == 0 else dealer_name}",
        (panel_rect.x + 18, panel_rect.y + 46),
        body_font,
        (173, 186, 212) if _UI_STYLE == "competitive_minimal" else (213, 202, 174),
    )

    player_chip = pygame.Rect(panel_rect.x + 14, panel_rect.y + 74, panel_rect.width - 28, 32)
    dad_chip = pygame.Rect(panel_rect.x + 14, panel_rect.y + 112, panel_rect.width - 28, 32)
    if _UI_STYLE == "competitive_minimal":
        pygame.draw.rect(screen, (26, 38, 56), player_chip, border_radius=16)
        pygame.draw.rect(screen, (45, 32, 44), dad_chip, border_radius=16)
        pygame.draw.rect(screen, (120, 150, 196), player_chip, width=1, border_radius=16)
        pygame.draw.rect(screen, (176, 130, 168), dad_chip, width=1, border_radius=16)
    else:
        pygame.draw.rect(screen, (20, 53, 76), player_chip, border_radius=16)
        pygame.draw.rect(screen, (37, 22, 20), dad_chip, border_radius=16)
        pygame.draw.rect(screen, (153, 205, 255), player_chip, width=1, border_radius=16)
        pygame.draw.rect(screen, (255, 159, 141), dad_chip, width=1, border_radius=16)

    player_surf = body_font.render(f"{player_name}: {player_scores[0]}", True, (185, 222, 255))
    dad_surf = body_font.render(f"{dealer_name} Score: {player_scores[1]}", True, (255, 176, 160))
    screen.blit(
        player_surf,
        (
            player_chip.centerx - player_surf.get_width() // 2,
            player_chip.centery - player_surf.get_height() // 2,
        ),
    )
    screen.blit(
        dad_surf,
        (
            dad_chip.centerx - dad_surf.get_width() // 2,
            dad_chip.centery - dad_surf.get_height() // 2,
        ),
    )

    _draw_label(
        screen,
        f"AI Difficulty: {AI_LEVELS[dad_ai_level]}",
        (panel_rect.x + 18, panel_rect.y + 150),
        small_font,
        (164, 177, 208) if _UI_STYLE == "competitive_minimal" else (214, 203, 174),
    )


def _draw_scoring_breakdown(screen, player_idx, breakdown_list, total_points, player_name):
    """Draw a breakdown of scoring items for a player."""
    sh = screen.get_height()
    playfield = _playfield_rect(screen)
    panel_w = 220
    panel_h = 280
    if player_idx == 0:
        panel_x = playfield.left + 14
    else:
        panel_x = playfield.right - panel_w - 14
    panel_y = sh // 2 - panel_h // 2
    panel_y = max(playfield.top + 14, min(panel_y, playfield.bottom - panel_h - 14))
    panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

    _draw_shadowed_panel(screen, panel_rect, (29, 42, 33), (193, 167, 109), radius=18)

    header_font = pygame.font.SysFont("segoe ui", 16, bold=True)
    item_font = pygame.font.SysFont("segoe ui", 13)
    total_font = pygame.font.SysFont("segoe ui", 14, bold=True)

    player_label = player_name if player_idx == 0 else _current_dealer_name()
    _draw_label(
        screen,
        f"{player_label}'s Score",
        (panel_rect.x + 12, panel_rect.y + 10),
        header_font,
        (236, 222, 186),
    )

    y_offset = panel_rect.y + 38
    if breakdown_list:
        for desc, _cards, points in breakdown_list:
            score_str = f"{desc}: +{points}"
            item_surf = item_font.render(score_str, True, (213, 202, 175))
            screen.blit(item_surf, (panel_rect.x + 12, y_offset))
            y_offset += 22

    pygame.draw.line(
        screen,
        (153, 132, 90),
        (panel_rect.x + 12, y_offset),
        (panel_rect.right - 12, y_offset),
        1,
    )
    y_offset += 8

    total_str = f"Hand: +{total_points}"
    total_surf = total_font.render(
        total_str, True, (120, 189, 255) if player_idx == 0 else (255, 148, 130)
    )
    screen.blit(total_surf, (panel_rect.x + 12, y_offset))


def _draw_round_summary_popup(
    screen,
    player_points,
    dealer_points,
    crib_points,
    dealer_idx,
    player_name,
    analysis_text="",
):
    """Draw a centered popup with this round's scoring totals."""

    def _wrap_line(font, text, max_width, max_lines=3):
        words = text.split()
        if not words:
            return []
        lines = []
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if font.size(trial)[0] <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
                if len(lines) >= max_lines:
                    return lines
        lines.append(current)
        return lines[:max_lines]

    playfield = _playfield_rect(screen)
    panel_w = min(560, playfield.width - 80)
    panel_h = 260
    panel_rect = pygame.Rect(
        playfield.centerx - panel_w // 2,
        playfield.centery - panel_h // 2,
        panel_w,
        panel_h,
    )

    dim = pygame.Surface((playfield.width, playfield.height), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 76))
    screen.blit(dim, playfield.topleft)

    _draw_shadowed_panel(screen, panel_rect, (23, 36, 31), (210, 182, 113), radius=22, shadow=(4, 6))

    title_font = pygame.font.SysFont("cambria", 30, bold=True)
    row_font = pygame.font.SysFont("segoe ui", 19, bold=True)
    meta_font = pygame.font.SysFont("segoe ui", 15)

    _draw_label(
        screen,
        "Round Summary",
        (panel_rect.x + 22, panel_rect.y + 16),
        title_font,
        (242, 227, 188),
    )

    dealer_name = _current_dealer_name()
    crib_owner = "Your Crib" if dealer_idx == 0 else f"{dealer_name} Crib"
    rows = [
        (f"{player_name}: +{player_points}", (174, 214, 255)),
        (f"{dealer_name}: +{dealer_points}", (255, 176, 160)),
        (f"{crib_owner}: +{crib_points}", (241, 206, 132)),
        (f"Round Total: +{player_points + dealer_points + crib_points}", (229, 236, 204)),
    ]

    y = panel_rect.y + 66
    for text, color in rows:
        surf = row_font.render(text, True, color)
        screen.blit(surf, (panel_rect.x + 24, y))
        y += 34

    analysis = analysis_text.strip()
    if analysis:
        wrapped = _wrap_line(meta_font, analysis, panel_rect.width - 48, max_lines=2)
        for line in wrapped:
            line_surf = meta_font.render(line, True, (211, 201, 175))
            screen.blit(line_surf, (panel_rect.x + 24, y))
            y += 22

    prompt = meta_font.render("Press R for next round", True, (211, 201, 175))
    screen.blit(prompt, (panel_rect.right - prompt.get_width() - 22, panel_rect.bottom - 28))


def _draw_game_header(screen, message):
    sw = screen.get_width()
    body_font = pygame.font.SysFont("segoe ui", 22, bold=True)
    header_text = message.strip() or "Play the hand. Mind the crib. Beat the table."

    box_w = min(860, sw - 140)
    msg_box = pygame.Rect(sw // 2 - box_w // 2, 22, box_w, 58)
    if _UI_STYLE == "competitive_minimal":
        pygame.draw.rect(screen, (16, 20, 28), msg_box, border_radius=20)
        pygame.draw.rect(screen, (108, 126, 156), msg_box, width=1, border_radius=20)
        msg_surf = body_font.render(header_text, True, (222, 232, 248))
    elif _UI_STYLE == "broadcast_table":
        pygame.draw.rect(screen, (10, 32, 24), msg_box, border_radius=24)
        pygame.draw.rect(screen, (209, 184, 122), msg_box, width=2, border_radius=24)
        msg_surf = body_font.render(header_text, True, (240, 231, 198))
    elif _UI_STYLE == "premium_tabletop":
        pygame.draw.rect(screen, (19, 56, 40), msg_box, border_radius=30)
        pygame.draw.rect(screen, (236, 206, 147), msg_box, width=2, border_radius=30)
        msg_surf = body_font.render(header_text, True, (248, 236, 209))
    else:
        pygame.draw.rect(screen, (0, 0, 0, 78), msg_box.move(3, 5), border_radius=29)
        pygame.draw.rect(screen, (24, 36, 29, 240), msg_box, border_radius=29)
        pygame.draw.rect(screen, (212, 183, 114), msg_box, width=2, border_radius=29)
        pygame.draw.line(
            screen,
            (255, 234, 183),
            (msg_box.left + 24, msg_box.top + 11),
            (msg_box.right - 24, msg_box.top + 11),
            1,
        )
        msg_surf = body_font.render(header_text, True, (238, 225, 191))
    screen.blit(
        msg_surf,
        (msg_box.centerx - msg_surf.get_width() // 2, msg_box.centery - msg_surf.get_height() // 2),
    )


def _draw_crib_area(screen, crib_count, starter_card, card_images, dealer, phase):
    sw, sh = screen.get_width(), screen.get_height()
    label_font = pygame.font.SysFont("segoe ui", 18, bold=True)
    small_font = pygame.font.SysFont("segoe ui", 15)

    crib_panel = _crib_panel_rect(sw, sh)
    if _UI_STYLE == "competitive_minimal":
        _draw_shadowed_panel(screen, crib_panel, (18, 24, 34), (104, 120, 150), radius=20)
    elif _UI_STYLE == "broadcast_table":
        _draw_shadowed_panel(screen, crib_panel, (14, 54, 38), (194, 171, 113), radius=22)
    elif _UI_STYLE == "premium_tabletop":
        _draw_shadowed_panel(screen, crib_panel, (21, 74, 49), (232, 202, 147), radius=24)
    else:
        _draw_shadowed_panel(screen, crib_panel, (20, 66, 45), (206, 176, 108), radius=24)
    crib_owner_label = "Your Crib" if dealer == 0 else "Opponent's Crib"
    _draw_label(
        screen,
        crib_owner_label,
        (crib_panel.x + 22, crib_panel.y + 14),
        label_font,
        (208, 222, 248) if _UI_STYLE == "competitive_minimal" else (240, 227, 188),
    )
    if phase == "discard" and crib_count < 4:
        _draw_label(
            screen,
            "Drop 2 cards here",
            (crib_panel.x + 22, crib_panel.y + 38),
            small_font,
            (164, 177, 208) if _UI_STYLE == "competitive_minimal" else (221, 192, 129),
        )

    card_w, card_h = 66, 98
    card_group_left = crib_panel.centerx - 90
    for i in range(2):
        card_rect = pygame.Rect(card_group_left + i * 84, crib_panel.y + 20, card_w, card_h)
        if i < crib_count:
            _draw_card_back(screen, card_rect)
        else:
            pygame.draw.rect(screen, (250, 241, 221, 38), card_rect, width=2, border_radius=12)
            pygame.draw.rect(
                screen, (166, 144, 98, 46), card_rect.inflate(-8, -8), width=1, border_radius=9
            )

    starter_box = pygame.Rect(crib_panel.right - 118, crib_panel.y + 17, 100, 106)
    pygame.draw.rect(screen, (31, 43, 35), starter_box, border_radius=18)
    pygame.draw.rect(screen, (214, 184, 114), starter_box, width=2, border_radius=18)
    _draw_label(
        screen, "Starter", (starter_box.x + 21, starter_box.y + 8), small_font, (238, 223, 186)
    )
    if starter_card is not None:
        starter_surf = pygame.transform.smoothscale(card_images[starter_card], (62, 88))
        screen.blit(starter_surf, (starter_box.x + 19, starter_box.y + 16))


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
    _sync_classic_session_from_runtime()
    s = _CLASSIC_SESSION
    if s.player_hand or s.ai_hand:
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
    _sync_runtime_from_classic_session()
    return True


def _handle_go(player_idx):
    _sync_classic_session_from_runtime()
    s = _CLASSIC_SESSION
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

    _sync_runtime_from_classic_session()


def _play_pegging_card(player_idx, idx):
    _sync_classic_session_from_runtime()
    s = _CLASSIC_SESSION
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

    if _finalize_pegging_if_complete():
        return

    current_total = get_pegging_total()

    if s.player_turn == 0:  # Player Turn
        player_can_move = any(
            current_total + _value_for_15(_parse_label(c.label)[0]) <= 31 for c in s.player_hand
        )
        if not player_can_move:
            _handle_go(0)
            return
        if auto_player and event is None:
            chosen = _choose_auto_player_pegging_index(current_total)
            if chosen is not None:
                _play_pegging_card(0, chosen)
                _check_for_winner()
            _finalize_pegging_if_complete()
            return
        if event and event.type == pygame.MOUSEBUTTONDOWN:
            for idx, card in enumerate(s.player_hand):
                val = _value_for_15(_parse_label(card.label)[0])
                if card.rect.collidepoint(event.pos) and current_total + val <= 31:
                    _play_pegging_card(0, idx)
                    _check_for_winner()
                    break
    else:  # Dealer Turn (AI)
        dad_can_move = any(
            current_total + _value_for_15(_parse_label(c.label)[0]) <= 31 for c in s.ai_hand
        )
        if not dad_can_move:
            _handle_go(1)
            return
        chosen = _choose_dad_pegging_index(current_total)
        if chosen is not None:
            _play_pegging_card(1, chosen)
            _check_for_winner()

    _finalize_pegging_if_complete()


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
    global message, dealer, player1_hand, player2_hand, game_phase, player_name, pegging_pile, starter_card, _deck_labels, _stock_labels, player_scores, winner_index, dad_ai_level, last_pegging_player, discard_analysis_message, _UI_STYLE
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

    capture_video_path = Path(args.capture_video).resolve() if capture_video_pending else None
    capture_video_frames_dir = None
    capture_video_frame_index = 0
    capture_intro_frames = 0
    capture_end_frames = 0
    capture_intro_target = max(1, int(args.capture_video_intro_seconds * FPS))
    capture_end_target = max(1, int(args.capture_video_end_seconds * FPS))
    capture_max_frames = max(60, int(args.capture_video_max_seconds * FPS))

    if capture_video_pending:
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
        global winner_index
        nonlocal card_images
        global pegging_points, round_breakdown, discard_analysis_message
        # Fresh game from intro
        pegging_points[:] = [0, 0]
        round_breakdown = {"player": (0, []), "ai": (0, []), "crib": (0, [])}
        discard_analysis_message = ""
        player_scores[:] = [0, 0]
        winner_index = None
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
    difficulty_buttons = {}
    online_btn_rect = None
    settings_btn_rect = None
    settings_open = False
    settings_volume_rect = None
    settings_anim_rect = None
    settings_ai_left_rect = None
    settings_ai_right_rect = None
    settings_style_left_rect = None
    settings_style_right_rect = None
    settings_voice_style_rect = None
    settings_voice_backend_rect = None
    settings_rvc_toggle_rect = None
    settings_rvc_pitch_left_rect = None
    settings_rvc_pitch_right_rect = None
    settings_voice_test_rect = None
    settings_local_exe_rect = None
    settings_local_model_rect = None
    settings_rvc_exe_rect = None
    settings_rvc_model_rect = None
    settings_rvc_index_rect = None
    settings_player_name_rect = None
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

    def _voice_startup_warning_text() -> str:
        if _SETTINGS.bert_voice_backend != "local_ai":
            return ""

        model_path = _SETTINGS.bert_local_model_path.strip()
        exe_path = _SETTINGS.bert_local_exe_path.strip() or "piper"
        model_ok = bool(model_path) and Path(model_path).exists()
        exe_ok = shutil.which(exe_path) is not None or Path(exe_path).exists()

        if not model_ok:
            return "Local AI voice is selected but Piper model path is missing/invalid. SAPI fallback active."
        if not exe_ok:
            return "Local AI voice is selected but Piper executable was not found. SAPI fallback active."
        if _SETTINGS.bert_rvc_enabled:
            rvc_model_ok = bool(_SETTINGS.bert_rvc_model_path.strip()) and Path(
                _SETTINGS.bert_rvc_model_path.strip()
            ).exists()
            rvc_exe_path = _SETTINGS.bert_rvc_exe_path.strip() or "rvc_infer"
            rvc_exe_ok = shutil.which(rvc_exe_path) is not None or Path(rvc_exe_path).exists()
            if not rvc_model_ok or not rvc_exe_ok:
                return "RVC is enabled but not fully configured. Voice runs without RVC until paths are fixed."
        return ""

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

    def _path_preview(value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return "<not set>"
        if len(cleaned) <= 62:
            return cleaned
        return "..." + cleaned[-59:]

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

    def _begin_classic_round(*, announce: bool) -> tuple[int, Card, str]:
        d, sc, msg = _start_fresh_game()
        _transition_phase("discard")
        if announce:
            _speak_bert_event("game_start", force=True)
        return d, sc, msg

    def _handle_settings_modal_click(pos: tuple[int, int]) -> None:
        nonlocal settings_open, settings_text_active

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

    def _draw_settings_modal(sw: int, sh: int) -> None:
        nonlocal settings_volume_rect, settings_anim_rect, settings_ai_left_rect, settings_ai_right_rect
        nonlocal settings_style_left_rect, settings_style_right_rect
        nonlocal settings_voice_style_rect
        nonlocal settings_voice_backend_rect
        nonlocal settings_rvc_toggle_rect, settings_rvc_pitch_left_rect
        nonlocal settings_rvc_pitch_right_rect, settings_voice_test_rect
        nonlocal settings_local_exe_rect, settings_local_model_rect
        nonlocal settings_rvc_exe_rect, settings_rvc_model_rect, settings_rvc_index_rect
        nonlocal settings_player_name_rect
        nonlocal settings_text_active
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
        _name_active = settings_text_active == "player_name"
        pygame.draw.rect(
            screen,
            (68, 60, 52) if _name_active else (48, 42, 36),
            settings_player_name_rect,
            border_radius=10,
        )
        pygame.draw.rect(
            screen,
            (255, 237, 172) if _name_active else (180, 162, 130),
            settings_player_name_rect,
            width=2,
            border_radius=10,
        )
        _name_disp = small_font.render(
            (_SETTINGS.player_name or "Player") + ("|" if _name_active else ""),
            True,
            (239, 234, 222),
        )
        screen.blit(
            _name_disp,
            (settings_player_name_rect.x + 8, settings_player_name_rect.centery - _name_disp.get_height() // 2),
        )

        vol_label = body_font.render(
            f"Volume: {int(_SETTINGS.volume * 100)}%", True, (245, 236, 218)
        )
        screen.blit(vol_label, (modal.x + 28, modal.y + 92))
        settings_volume_rect = pygame.Rect(modal.x + 28, modal.y + 128, 420, 18)
        pygame.draw.rect(screen, (69, 56, 43), settings_volume_rect, border_radius=9)
        fill = settings_volume_rect.copy()
        fill.width = max(8, int(settings_volume_rect.width * _SETTINGS.volume))
        pygame.draw.rect(screen, (214, 176, 91), fill, border_radius=9)
        knob_x = settings_volume_rect.x + int(settings_volume_rect.width * _SETTINGS.volume)
        knob_x = max(settings_volume_rect.left + 10, min(settings_volume_rect.right - 10, knob_x))
        pygame.draw.circle(screen, (255, 244, 220), (knob_x, settings_volume_rect.centery), 11)
        pygame.draw.circle(screen, (139, 96, 48), (knob_x, settings_volume_rect.centery), 11, 2)

        anim_text = "On" if _SETTINGS.animations_enabled else "Off"
        settings_anim_rect = pygame.Rect(modal.x + 28, modal.y + 184, 174, 44)
        anim_label = body_font.render(f"Animations: {anim_text}", True, (245, 236, 218))
        screen.blit(anim_label, (modal.x + 28, modal.y + 156))
        pygame.draw.rect(
            screen,
            (62, 101, 74) if _SETTINGS.animations_enabled else (121, 72, 66),
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
            f"Online AI Pref: {AI_LEVELS[_SETTINGS.online_ai_level]}", True, (245, 236, 218)
        )
        screen.blit(ai_label, (modal.x + 244, modal.y + 156))
        settings_ai_left_rect = pygame.Rect(modal.x + 244, modal.y + 184, 46, 44)
        settings_ai_right_rect = pygame.Rect(modal.x + 366, modal.y + 184, 46, 44)
        mid_rect = pygame.Rect(modal.x + 300, modal.y + 184, 56, 44)
        for rect, label in ((settings_ai_left_rect, "<"), (settings_ai_right_rect, ">")):
            pygame.draw.rect(screen, (64, 106, 154), rect, border_radius=18)
            pygame.draw.rect(screen, (208, 228, 245), rect, width=2, border_radius=18)
            txt = body_font.render(label, True, (255, 255, 255))
            screen.blit(
                txt, (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2)
            )
        ai_mid = body_font.render(str(_SETTINGS.online_ai_level), True, (255, 255, 255))
        pygame.draw.rect(screen, (55, 48, 42), mid_rect, border_radius=18)
        pygame.draw.rect(screen, (233, 205, 153), mid_rect, width=2, border_radius=18)
        screen.blit(
            ai_mid,
            (
                mid_rect.centerx - ai_mid.get_width() // 2,
                mid_rect.centery - ai_mid.get_height() // 2,
            ),
        )

        style_label = body_font.render("Playfield Style:", True, (245, 236, 218))
        screen.blit(style_label, (modal.x + 28, modal.y + 244))
        settings_style_left_rect = pygame.Rect(modal.x + 28, modal.y + 272, 46, 44)
        settings_style_right_rect = pygame.Rect(modal.x + 402, modal.y + 272, 46, 44)
        style_mid_rect = pygame.Rect(modal.x + 84, modal.y + 272, 312, 44)
        for rect, label in ((settings_style_left_rect, "<"), (settings_style_right_rect, ">")):
            pygame.draw.rect(screen, (64, 106, 154), rect, border_radius=18)
            pygame.draw.rect(screen, (208, 228, 245), rect, width=2, border_radius=18)
            txt = body_font.render(label, True, (255, 255, 255))
            screen.blit(
                txt, (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2)
            )
        pygame.draw.rect(screen, (55, 48, 42), style_mid_rect, border_radius=18)
        pygame.draw.rect(screen, (233, 205, 153), style_mid_rect, width=2, border_radius=18)
        style_text = small_font.render(_UI_STYLE_LABELS[_SETTINGS.ui_style], True, (255, 255, 255))
        screen.blit(
            style_text,
            (
                style_mid_rect.centerx - style_text.get_width() // 2,
                style_mid_rect.centery - style_text.get_height() // 2,
            ),
        )

        voice_style_label = body_font.render("Bert Voice Style:", True, (245, 236, 218))
        screen.blit(voice_style_label, (modal.x + 28, modal.y + 324))
        settings_voice_style_rect = pygame.Rect(modal.x + 216, modal.y + 324, 196, 44)
        pygame.draw.rect(screen, (66, 94, 132), settings_voice_style_rect, border_radius=18)
        pygame.draw.rect(screen, (224, 234, 244), settings_voice_style_rect, width=2, border_radius=18)
        voice_text = small_font.render(
            f"{_SETTINGS.bert_voice_style.title()} (click)", True, (255, 255, 255)
        )
        screen.blit(
            voice_text,
            (
                settings_voice_style_rect.centerx - voice_text.get_width() // 2,
                settings_voice_style_rect.centery - voice_text.get_height() // 2,
            ),
        )

        backend_label = body_font.render("Bert Voice Backend:", True, (245, 236, 218))
        screen.blit(backend_label, (modal.x + 28, modal.y + 378))
        settings_voice_backend_rect = pygame.Rect(modal.x + 216, modal.y + 378, 196, 44)
        pygame.draw.rect(screen, (88, 94, 66), settings_voice_backend_rect, border_radius=18)
        pygame.draw.rect(screen, (244, 239, 188), settings_voice_backend_rect, width=2, border_radius=18)
        backend_text = "Local AI" if _SETTINGS.bert_voice_backend == "local_ai" else "Windows SAPI"
        backend_note = small_font.render(f"{backend_text} (click)", True, (255, 255, 255))
        screen.blit(
            backend_note,
            (
                settings_voice_backend_rect.centerx - backend_note.get_width() // 2,
                settings_voice_backend_rect.centery - backend_note.get_height() // 2,
            ),
        )

        rvc_label = body_font.render("RVC Accent Pass:", True, (245, 236, 218))
        screen.blit(rvc_label, (modal.x + 28, modal.y + 432))
        settings_rvc_toggle_rect = pygame.Rect(modal.x + 216, modal.y + 432, 196, 44)
        rvc_fill = (62, 101, 74) if _SETTINGS.bert_rvc_enabled else (121, 72, 66)
        pygame.draw.rect(screen, rvc_fill, settings_rvc_toggle_rect, border_radius=18)
        pygame.draw.rect(screen, (244, 239, 188), settings_rvc_toggle_rect, width=2, border_radius=18)
        rvc_text = "Enabled (click)" if _SETTINGS.bert_rvc_enabled else "Disabled (click)"
        rvc_note = small_font.render(rvc_text, True, (255, 255, 255))
        screen.blit(
            rvc_note,
            (
                settings_rvc_toggle_rect.centerx - rvc_note.get_width() // 2,
                settings_rvc_toggle_rect.centery - rvc_note.get_height() // 2,
            ),
        )

        pitch_label = body_font.render("RVC Pitch Shift:", True, (245, 236, 218))
        screen.blit(pitch_label, (modal.x + 28, modal.y + 486))
        settings_rvc_pitch_left_rect = pygame.Rect(modal.x + 216, modal.y + 486, 46, 44)
        settings_rvc_pitch_right_rect = pygame.Rect(modal.x + 366, modal.y + 486, 46, 44)
        pitch_mid_rect = pygame.Rect(modal.x + 272, modal.y + 486, 84, 44)
        for rect, label in (
            (settings_rvc_pitch_left_rect, "<"),
            (settings_rvc_pitch_right_rect, ">"),
        ):
            pygame.draw.rect(screen, (64, 106, 154), rect, border_radius=18)
            pygame.draw.rect(screen, (208, 228, 245), rect, width=2, border_radius=18)
            txt = body_font.render(label, True, (255, 255, 255))
            screen.blit(
                txt,
                (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2),
            )
        pygame.draw.rect(screen, (55, 48, 42), pitch_mid_rect, border_radius=18)
        pygame.draw.rect(screen, (233, 205, 153), pitch_mid_rect, width=2, border_radius=18)
        pitch_text = body_font.render(str(_SETTINGS.bert_rvc_pitch_shift), True, (255, 255, 255))
        screen.blit(
            pitch_text,
            (
                pitch_mid_rect.centerx - pitch_text.get_width() // 2,
                pitch_mid_rect.centery - pitch_text.get_height() // 2,
            ),
        )

        settings_voice_test_rect = pygame.Rect(modal.x + 116, modal.y + 542, 248, 44)
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

        local_exe_label = body_font.render("Piper Executable:", True, (245, 236, 218))
        screen.blit(local_exe_label, (modal.x + 28, modal.y + 488))
        settings_local_exe_rect = pygame.Rect(modal.x + 28, modal.y + 518, modal.width - 56, 30)
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
        local_exe_text = field_font.render(_path_preview(_SETTINGS.bert_local_exe_path), True, (239, 234, 222))
        screen.blit(local_exe_text, (settings_local_exe_rect.x + 10, settings_local_exe_rect.y + 6))

        local_model_label = body_font.render("Piper Model Path:", True, (245, 236, 218))
        screen.blit(local_model_label, (modal.x + 28, modal.y + 560))
        settings_local_model_rect = pygame.Rect(modal.x + 28, modal.y + 590, modal.width - 56, 30)
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
        local_model_text = field_font.render(
            _path_preview(_SETTINGS.bert_local_model_path), True, (239, 234, 222)
        )
        screen.blit(local_model_text, (settings_local_model_rect.x + 10, settings_local_model_rect.y + 6))

        rvc_exe_label = body_font.render("RVC Executable:", True, (245, 236, 218))
        screen.blit(rvc_exe_label, (modal.x + 28, modal.y + 632))
        settings_rvc_exe_rect = pygame.Rect(modal.x + 28, modal.y + 662, modal.width - 56, 30)
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
        rvc_exe_text = field_font.render(_path_preview(_SETTINGS.bert_rvc_exe_path), True, (239, 234, 222))
        screen.blit(rvc_exe_text, (settings_rvc_exe_rect.x + 10, settings_rvc_exe_rect.y + 6))

        rvc_model_label = body_font.render("RVC Model Path:", True, (245, 236, 218))
        screen.blit(rvc_model_label, (modal.x + 28, modal.y + 704))
        settings_rvc_model_rect = pygame.Rect(modal.x + 28, modal.y + 734, modal.width - 56, 30)
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
        rvc_model_text = field_font.render(
            _path_preview(_SETTINGS.bert_rvc_model_path), True, (239, 234, 222)
        )
        screen.blit(rvc_model_text, (settings_rvc_model_rect.x + 10, settings_rvc_model_rect.y + 6))

        rvc_index_label = body_font.render("RVC Index Path:", True, (245, 236, 218))
        screen.blit(rvc_index_label, (modal.x + 28, modal.y + 776))
        settings_rvc_index_rect = pygame.Rect(modal.x + 28, modal.y + 806, modal.width - 56, 30)
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
        rvc_index_text = field_font.render(
            _path_preview(_SETTINGS.bert_rvc_index_path), True, (239, 234, 222)
        )
        screen.blit(rvc_index_text, (settings_rvc_index_rect.x + 10, settings_rvc_index_rect.y + 6))

        warn_text = _voice_startup_warning_text()
        if warn_text:
            warn = small_font.render(warn_text, True, (235, 193, 136))
            screen.blit(warn, (modal.x + 28, modal.y + 842))

        hint = small_font.render(
            "Click a path box to edit. Enter saves. Esc exits field.", True, (210, 198, 176)
        )
        screen.blit(hint, (modal.centerx - hint.get_width() // 2, modal.bottom - 22))

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

    game_controller = GameController(_ENGINE, legacy_module=sys.modules[__name__])
    event_handler = EventHandler()

    running = True
    while running:
        if _EFFECTS is not None and _SETTINGS.animations_enabled:
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
            start_font = pygame.font.SysFont("bahnschrift", 24, bold=True)
            glyph_font = pygame.font.SysFont("segoe ui symbol", 20, bold=True)
            # Card typography — modern, 2026
            card_name_font = pygame.font.SysFont("segoe ui variable", 29, bold=True)
            card_badge_font = pygame.font.SysFont("segoe ui variable", 11)
            card_desc_font = pygame.font.SysFont("segoe ui variable", 13)

            title = title_font.render("Upta", True, MAINE_COLORS["cream"])
            title_outline = title_shadow_font.render("Upta", True, (40, 31, 18))
            title_warm_shadow = title_shadow_font.render("Upta", True, (97, 59, 24))
            subtitle = subtitle_font.render(
                "Play the Hand. Mind the Crib. Beat the Table.", True, (235, 216, 182)
            )
            subtitle_small = subtitle_small_font.render(
                "Maine camp cards, dressed like opening night.", True, (214, 194, 162)
            )
            voice_warning = _voice_startup_warning_text()

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

            panel_w = min(980, max(640, sw - 120))
            panel_h = min(430, max(330, sh - 250))
            panel_rect = pygame.Rect(
                sw // 2 - panel_w // 2, sh // 2 - panel_h // 2 + 54, panel_w, panel_h
            )

            panel_surface = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
            panel_surface.fill((10, 28, 14, 160))
            screen.blit(panel_surface, panel_rect.topleft)
            pygame.draw.rect(screen, (84, 152, 92), panel_rect, width=2, border_radius=18)
            # inner highlight rim
            _rim = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(_rim, (140, 200, 148, 40), _rim.get_rect().inflate(-4, -4), width=1, border_radius=16)
            screen.blit(_rim, panel_rect.topleft)

            panel_pad = 28
            difficulty_options = [
                (1, "Easy"),
                (2, "Medium"),
                (3, "Hard"),
                (4, "Bert"),
                (5, "Bert+"),
            ]
            button_count = len(difficulty_options)
            available_w = panel_rect.width - panel_pad * 2
            button_spacing = 14
            button_width = max(
                96,
                min(
                    152,
                    (available_w - button_spacing * (button_count - 1)) // max(1, button_count),
                ),
            )
            button_height = 132
            total_width = button_count * button_width + (button_count - 1) * button_spacing
            if total_width > available_w:
                button_spacing = max(
                    8,
                    (available_w - button_count * button_width) // max(1, button_count - 1),
                )
                total_width = button_count * button_width + (button_count - 1) * button_spacing
            if total_width > available_w:
                button_width = max(
                    84,
                    (available_w - button_spacing * (button_count - 1)) // max(1, button_count),
                )
                total_width = button_count * button_width + (button_count - 1) * button_spacing

            start_x = panel_rect.x + panel_pad + max(0, (available_w - total_width) // 2)
            cta_row_y = panel_rect.bottom - 88
            button_y = cta_row_y - button_height - 26

            yankee_font = pygame.font.SysFont("constantia", 22, bold=True, italic=True)
            yankee_line = yankee_font.render("\"Hurry up 'n' pick one there, bub.\"", True, (58, 40, 25))

            speech_w = min(panel_rect.width - 120, yankee_line.get_width() + 42)
            speech_h = 46
            speech_rect = pygame.Rect(sw // 2 - speech_w // 2, panel_rect.y + 12, speech_w, speech_h)

            # Traditional comic speech balloon: clean non-oval contour and crisp pointed tail.
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

            s = bubble_scale
            cx = speech_local.centerx
            cy = speech_local.centery
            a = speech_local.width // 2 + 20 * s
            b = speech_local.height // 2 + 10 * s
            n = 4.6  # superellipse exponent for a classic comic balloon contour

            body_points = []
            for i in range(72):
                t = (2 * math.pi * i) / 72
                ct = math.cos(t)
                st = math.sin(t)
                x = cx + a * (1 if ct >= 0 else -1) * (abs(ct) ** (2 / n))
                y = cy + b * (1 if st >= 0 else -1) * (abs(st) ** (2 / n))
                body_points.append((int(x), int(y)))

            shadow_points = [(x, y + 5 * s) for x, y in body_points]
            pygame.draw.polygon(bubble_surface, (0, 0, 0, 58), shadow_points)
            pygame.draw.polygon(bubble_surface, (245, 239, 225), body_points)
            pygame.draw.polygon(bubble_surface, (124, 96, 64), body_points, width=3 * s)
            pygame.draw.aalines(bubble_surface, (124, 96, 64), True, body_points)

            inner_points = []
            ia = max(8, a - 14 * s)
            ib = max(8, b - 12 * s)
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

            screen.blit(yankee_line, (speech_rect.centerx - yankee_line.get_width() // 2, speech_rect.centery - yankee_line.get_height() // 2))

            difficulty_buttons = {}

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

                # Maine-shaped level cards (scaled from MAINE_SHAPE asset, aspect-ratio preserved)
                shape_pad = 4
                min_x = min(p[0] for p in MAINE_SHAPE)
                max_x = max(p[0] for p in MAINE_SHAPE)
                min_y = min(p[1] for p in MAINE_SHAPE)
                max_y = max(p[1] for p in MAINE_SHAPE)
                raw_sw = max(1, max_x - min_x)
                raw_sh = max(1, max_y - min_y)
                avail_w = draw_rect.width - shape_pad * 2
                avail_h = draw_rect.height - shape_pad * 2
                _ms = min(avail_w / raw_sw, avail_h / raw_sh)
                _ox = draw_rect.x + shape_pad + (avail_w - raw_sw * _ms) / 2
                _oy = draw_rect.y + shape_pad + (avail_h - raw_sh * _ms) / 2
                maine_points = []
                for px, py in MAINE_SHAPE:
                    sx = int(_ox + (px - min_x) * _ms)
                    sy = int(_oy + (py - min_y) * _ms)
                    maine_points.append((sx, sy))

                # Drop shadow (proper SRCALPHA surface so alpha blends)
                _shad = pygame.Surface((draw_rect.width + 24, draw_rect.height + 24), pygame.SRCALPHA)
                _shad_pts = [(x - draw_rect.x + 8, y - draw_rect.y + 10) for x, y in maine_points]
                pygame.draw.polygon(_shad, (0, 0, 0, 110), _shad_pts)
                screen.blit(_shad, (draw_rect.x - 4, draw_rect.y - 4))
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

                # Glowing border: outer soft halo → solid 2px → bright aaline highlight
                _glow = pygame.Surface((draw_rect.width + 20, draw_rect.height + 20), pygame.SRCALPHA)
                _g_pts = [(x - draw_rect.x + 10, y - draw_rect.y + 10) for x, y in maine_points]
                pygame.draw.polygon(_glow, (*border_color, 55), _g_pts, width=7)
                pygame.draw.polygon(_glow, (*border_color, 90), _g_pts, width=4)
                screen.blit(_glow, (draw_rect.x - 10, draw_rect.y - 10))
                pygame.draw.polygon(screen, border_color, maine_points, width=2)
                _hi_border = tuple(min(255, c + 60) for c in border_color)
                pygame.draw.aalines(screen, _hi_border, True, maine_points)

                if level == dad_ai_level:
                    pass  # selected state handled by color/border only

                def _outlined(surf, font, text, color, ox, oy, outline=2):
                    """8-direction outlined text for legibility on textured/photo bg."""
                    _s = font.render(text, True, (0, 0, 0))
                    for _dx in range(-outline, outline + 1):
                        for _dy in range(-outline, outline + 1):
                            if _dx == 0 and _dy == 0:
                                continue
                            surf.blit(_s, (ox + _dx, oy + _dy))
                    surf.blit(font.render(text, True, color), (ox, oy))

                def _tracked_w(font, text, spacing=4):
                    return sum(font.size(c)[0] for c in text.upper()) + spacing * max(0, len(text) - 1)

                def _tracked(surf, font, text, color, cx, y, spacing=4):
                    """ALL-CAPS tracked text on a solid bg — no outline needed."""
                    x = cx - _tracked_w(font, text, spacing) // 2
                    for c in text.upper():
                        surf.blit(font.render(c, True, color), (x, y))
                        x += font.size(c)[0] + spacing

                # ── Badge pill (solid, tracked all-caps) ─────────────────────
                _badge_labels = {
                    1: "Introductory",
                    2: "From Away",
                    3: "Native Mainer",
                    4: "The Wharf",
                    5: "Learning",
                }
                _badge_str = _badge_labels[level]
                _bw = _tracked_w(card_badge_font, _badge_str, 4)
                _bh = card_badge_font.get_height()
                _pill_w, _pill_h = _bw + 24, _bh + 10
                _pill = pygame.Surface((_pill_w, _pill_h), pygame.SRCALPHA)
                pygame.draw.rect(_pill, (*badge_color, 255), _pill.get_rect(), border_radius=10)
                _label_cx = draw_rect.centerx
                _label_y = draw_rect.y - _pill_h - 8
                screen.blit(_pill, (_label_cx - _pill_w // 2, _label_y))
                _tracked(screen, card_badge_font, _badge_str, badge_text_color,
                         _label_cx, _label_y + (_pill_h - _bh) // 2, spacing=4)

                # ── Level name (hero text, top-lit shimmer) ───────────────────
                _lname_color = (255, 252, 235) if level == dad_ai_level else (255, 245, 215)
                _name_up = name.upper()
                _ltx = draw_rect.x + button_width // 2 - card_name_font.size(_name_up)[0] // 2
                _lty = draw_rect.y + 36
                _outlined(screen, card_name_font, _name_up, _lname_color, _ltx, _lty, outline=2)

                # ── Desc text ─────────────────────────────────────────────────
                desc_color = (255, 245, 210) if level == dad_ai_level else (210, 238, 210)
                desc_lines = difficulty_descriptions[level].split("\n")
                _desc_y0 = _lty + card_name_font.get_height() + 5
                for j, line in enumerate(desc_lines):
                    _dcx = draw_rect.centerx - card_desc_font.size(line)[0] // 2
                    _dcy = _desc_y0 + j * 15
                    _outlined(screen, card_desc_font, line, desc_color, _dcx, _dcy, outline=1)

            start_button_width, start_button_height = min(320, max(240, panel_rect.width // 3)), 60
            start_btn_rect = pygame.Rect(
                panel_rect.centerx - start_button_width // 2,
                panel_rect.bottom - start_button_height - 24,
                start_button_width,
                start_button_height,
            )
            start_hover = start_btn_rect.collidepoint(mouse_pos)
            start_draw = start_btn_rect.move(0, -2 if start_hover else 0)
            pygame.draw.rect(screen, (0, 0, 0, 80), start_draw.move(0, 5), border_radius=10)
            pygame.draw.rect(
                screen,
                (32, 70, 36) if not start_hover else (42, 88, 48),
                start_draw,
                border_radius=10,
            )
            pygame.draw.rect(screen, (96, 152, 102), start_draw, width=1, border_radius=10)

            start_text = start_font.render("START GAME", True, (238, 232, 214))
            start_icon = glyph_font.render("\u25b6", True, (206, 188, 152))
            icon_gap = 10
            screen.blit(
                start_text,
                (
                    start_btn_rect.centerx - (start_text.get_width() + icon_gap + start_icon.get_width()) // 2 + start_icon.get_width() + icon_gap,
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

            online_button_width, online_button_height = min(230, max(180, panel_rect.width // 4)), 46
            online_btn_rect = pygame.Rect(
                panel_rect.right - online_button_width,
                panel_rect.bottom + 14,
                online_button_width,
                online_button_height,
            )
            online_hover = online_btn_rect.collidepoint(mouse_pos)
            online_draw = online_btn_rect.move(0, -2 if online_hover else 0)
            pygame.draw.rect(screen, (0, 0, 0, 80), online_draw.move(0, 5), border_radius=10)
            pygame.draw.rect(
                screen,
                (44, 72, 108) if not online_hover else (56, 88, 128),
                online_draw,
                border_radius=10,
            )
            pygame.draw.rect(screen, (92, 142, 192), online_draw, width=1, border_radius=10)

            online_text = start_font.render("ONLINE MODE", True, (218, 230, 244))
            online_icon = glyph_font.render("\u2606", True, (180, 206, 234))
            screen.blit(
                online_text,
                (
                    online_btn_rect.centerx - (online_text.get_width() + icon_gap + online_icon.get_width()) // 2 + online_icon.get_width() + icon_gap,
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
                    settings_btn_rect.centerx - (settings_text.get_width() + 8 + gear.get_width()) // 2 + gear.get_width() + 8,
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

            if settings_open:
                _draw_settings_modal(sw, sh)

            if capture_title_pending:
                capture_path = Path(args.capture_title)
                capture_path.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(screen, str(capture_path))
                print(f"Saved title screenshot to: {capture_path}")
                capture_title_pending = False
                if args.exit_after_capture:
                    pygame.quit()
                    return

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

            pygame.display.flip()
            clock.tick(FPS)

            mouse_pos = pygame.mouse.get_pos()

            actions = event_handler.get_actions()
            for action in actions:
                action_type = str(action.get("type", ""))
                raw_event = action.get("raw_event")

                if action_type == "QUIT":
                    running = False
                    continue

                if (
                    action_type == "SETTINGS_TOGGLE"
                    and not (settings_open and settings_text_active is not None)
                ):
                    settings_open = not settings_open
                    if not settings_open:
                        settings_text_active = None
                    continue

                if (
                    action_type == "KEYDOWN"
                    and settings_open
                    and raw_event is not None
                    and _handle_settings_text_key(raw_event)
                ):
                    continue

                if action_type == "AI_LEVEL_SELECT" and not settings_open:
                    level = action.get("level")
                    if isinstance(level, int) and 1 <= level <= 5:
                        dad_ai_level = level
                        if dad_ai_level in (4, 5):
                            _speak_bert_event("level_selected", force=True)
                    continue

                if action_type == "ONLINE_MODE" and not settings_open:
                    _launch_online_client()
                    return

                if action_type == "KEYDOWN" and action.get("key") in (pygame.K_RETURN, pygame.K_SPACE):
                    if not settings_open:
                        d, sc, msg = _begin_classic_round(announce=True)
                        dealer = d
                        starter_card = sc
                        message = msg
                    continue

                if action_type == "MOUSEBUTTONDOWN":
                    pos = action.get("pos")
                    if not pos:
                        continue

                    if settings_open:
                        _handle_settings_modal_click(pos)
                        continue

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
                        return
                    elif settings_btn_rect is not None and settings_btn_rect.collidepoint(mouse_pos):
                        settings_open = True
                        settings_text_active = None
            continue

        sw, sh = screen.get_width(), screen.get_height()
        _LAST_SCREEN_SIZE = (sw, sh)
        if _UI_STYLE != "classic":
            _draw_board_frame(screen)
        elif gameplay_background is not None:
            bg = pygame.transform.smoothscale(gameplay_background, (sw, sh))
            screen.blit(bg, (0, 0))

            atmosphere = pygame.Surface((sw, sh), pygame.SRCALPHA)
            atmosphere.fill((10, 22, 18, 44))
            pygame.draw.ellipse(
                atmosphere,
                (220, 188, 118, 16),
                pygame.Rect(sw // 2 - 420, sh // 2 - 220, 840, 500),
            )
            pygame.draw.ellipse(
                atmosphere,
                (0, 0, 0, 52),
                pygame.Rect(14, 14, sw - 28, sh - 28),
                width=34,
            )
            screen.blit(atmosphere, (0, 0))

            table_zone = pygame.Rect(42, 88, sw - 84, sh - 136)
            zone_overlay = pygame.Surface((table_zone.width, table_zone.height), pygame.SRCALPHA)
            pygame.draw.rect(
                zone_overlay,
                (15, 45, 33, PLAYFIELD_ALPHA),
                zone_overlay.get_rect(),
                border_radius=26,
            )
            pygame.draw.rect(
                zone_overlay,
                (214, 184, 113, 95),
                zone_overlay.get_rect(),
                width=2,
                border_radius=26,
            )
            screen.blit(zone_overlay, table_zone.topleft)
        else:
            _draw_board_frame(screen)

        actions = event_handler.get_actions()
        for action in actions:
            action_type = str(action.get("type", ""))
            if action_type == "QUIT":
                running = False
                break

            if action_type == "AI_LEVEL_CHANGE":
                dad_ai_level = 1 if dad_ai_level == 5 else dad_ai_level + 1
                if dad_ai_level in (4, 5):
                    message = f"AI level set to {dad_ai_level}. Opponent is now Bert."
                    _speak_bert_event("level_selected", force=True)
                else:
                    message = f"AI level set to {dad_ai_level}."

            if _CLASSIC_SESSION.phase == "end":
                if action_type == "KEYDOWN" and action.get("key") == pygame.K_r:
                    d, sc, msg = _start_next_round()
                    dealer = d
                    starter_card = sc
                    message = msg
                    game_controller.transition_phase("discard")
                elif action_type == "MOUSEBUTTONDOWN" and action.get("button") == 1:
                    sw, sh = screen.get_width(), screen.get_height()
                    pos = action.get("pos")
                    if pos and _primary_button_rect(sw, sh).collidepoint(pos):
                        d, sc, msg = _start_next_round()
                        dealer = d
                        starter_card = sc
                        message = msg
                        game_controller.transition_phase("discard")

            if _CLASSIC_SESSION.phase == "game_over":
                if action_type == "KEYDOWN" and action.get("key") == pygame.K_r:
                    # Return to intro; starting a new game resets scores.
                    game_controller.transition_phase("intro")
                elif action_type == "MOUSEBUTTONDOWN" and action.get("button") == 1:
                    sw, sh = screen.get_width(), screen.get_height()
                    pos = action.get("pos")
                    if pos and _primary_button_rect(sw, sh).collidepoint(pos):
                        game_controller.transition_phase("intro")

        game_controller.process(actions)

        # Let the game logic advance even when there are no input events.
        if not capture_gameplay_pending:
            if capture_video_pending and _CLASSIC_SESSION.phase == "discard":
                _auto_discard_player_hand()
            game_controller.update(auto_player=capture_video_pending)

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

        # Update Card Positions for rendering
        p1_pos = fixed_hand_positions(1, len(_CLASSIC_SESSION.player_hand), sw, sh)
        mouse_pos = pygame.mouse.get_pos()
        for i, card in enumerate(_CLASSIC_SESSION.player_hand):
            card.rect.topleft = p1_pos[i]
            hovered = (
                card.rect.collidepoint(mouse_pos)
                and _CLASSIC_SESSION.phase in ("discard", "pegging")
                and _CLASSIC_SESSION.player_turn == 0
            )
            draw_rect = card.rect.copy()
            if hovered:
                draw_rect.y -= 14

            shadow = pygame.Rect(
                draw_rect.x + 6, draw_rect.y + 8, draw_rect.width, draw_rect.height
            )
            pygame.draw.rect(screen, (0, 0, 0, 80), shadow, border_radius=12)
            if hovered:
                lifted = pygame.transform.rotozoom(card.image, -3, 1.03)
                lifted_rect = lifted.get_rect(center=draw_rect.center)
                screen.blit(lifted, lifted_rect)
            else:
                card.draw(screen)

        p2_size = (106, 159)
        p2_pos = _row_positions(len(_CLASSIC_SESSION.ai_hand), sw, 170, p2_size[0], margin=60)
        if _CLASSIC_SESSION.ai_hand:
            opp_font = pygame.font.SysFont("segoe ui", 18, bold=True)
            opp_label = opp_font.render("Opponent Hand", True, (218, 206, 174))
            row_center_x = p2_pos[0][0] + ((p2_pos[-1][0] + p2_size[0]) - p2_pos[0][0]) // 2
            label_y = max(124, p2_pos[0][1] - 34)
            screen.blit(opp_label, opp_label.get_rect(center=(row_center_x, label_y)))
        for i, card in enumerate(_CLASSIC_SESSION.ai_hand):
            card.rect = pygame.Rect(p2_pos[i][0], p2_pos[i][1], p2_size[0], p2_size[1])
            shadow = pygame.Rect(
                card.rect.x + 5, card.rect.y + 6, card.rect.width, card.rect.height
            )
            pygame.draw.rect(screen, (0, 0, 0, 80), shadow, border_radius=12)
            _draw_card_back(screen, card.rect)

        pegging_card_size = (92, 138)
        _player_row_top = max(510, sh - CARD_HEIGHT - 70)
        pegging_y = min(PEGGING_Y, _player_row_top - pegging_card_size[1] - 62)
        lane_width = min(620, max(220, 128 + len(_CLASSIC_SESSION.pegging_pile) * 30))
        pegging_lane = pygame.Rect(
            sw // 2 - lane_width // 2,
            pegging_y - 14,
            lane_width,
            pegging_card_size[1] + 20,
        )
        if _CLASSIC_SESSION.pegging_pile:
            _draw_shadowed_panel(
                screen,
                pegging_lane,
                (21, 57, 42),
                (182, 155, 100),
                radius=28,
                shadow=(3, 4),
            )
        for i, card in enumerate(_CLASSIC_SESSION.pegging_pile):
            card.rect = pygame.Rect(
                sw // 2 - 220 + i * 26, pegging_y, pegging_card_size[0], pegging_card_size[1]
            )
            shadow = pygame.Rect(
                card.rect.x + 4, card.rect.y + 6, card.rect.width, card.rect.height
            )
            pygame.draw.rect(screen, (0, 0, 0, 75), shadow, border_radius=12)
            _draw_scaled_card(screen, card.image, card.rect, pegging_card_size)

        if _EFFECTS is not None and _SETTINGS.animations_enabled:
            _EFFECTS.draw(screen)
            shake_x, shake_y = _EFFECTS.shake_offset()
            if shake_x or shake_y:
                shaken = screen.copy()
                screen.fill((0, 0, 0))
                screen.blit(shaken, (shake_x, shake_y))

        if _CLASSIC_SESSION.phase == "pegging":
            total_font = pygame.font.SysFont("segoe ui", 20, bold=True)
            total_chip = pygame.Rect(sw // 2 - 154, pegging_y + pegging_card_size[1] - 4, 308, 46)
            _draw_shadowed_panel(
                screen, total_chip, (24, 36, 29), (197, 170, 108), radius=23, shadow=(4, 5)
            )
            total_surf = total_font.render(
                f"Pegging Total: {get_pegging_total()}", True, (238, 224, 188)
            )
            screen.blit(
                total_surf,
                (
                    total_chip.centerx - total_surf.get_width() // 2,
                    total_chip.centery - total_surf.get_height() // 2,
                ),
            )

        # Display scoring breakdown during end-of-hand phase
        if _CLASSIC_SESSION.phase == "end":
            p1_pts, p1_breakdown = round_breakdown["player"]
            p2_pts, p2_breakdown = round_breakdown["ai"]
            crib_pts, crib_breakdown = round_breakdown["crib"]

            # Show player and ai hand scoring
            _draw_scoring_breakdown(screen, 0, p1_breakdown, p1_pts, player_name)
            _draw_scoring_breakdown(screen, 1, p2_breakdown, p2_pts, player_name)

            # Show crib scoring in the center if dealer
            if crib_pts > 0 or crib_breakdown:
                playfield = _playfield_rect(screen)
                crib_panel = _crib_panel_rect(sw, sh)
                crib_w = 240
                crib_h = 140
                crib_x = crib_panel.centerx - crib_w // 2
                if _CLASSIC_SESSION.dealer == 0:
                    # Opponent crib: place summary above the crib/starter box.
                    crib_y = crib_panel.top - crib_h - 12
                else:
                    crib_y = crib_panel.bottom + 12

                crib_x = max(playfield.left + 12, min(crib_x, playfield.right - crib_w - 12))
                crib_y = max(playfield.top + 12, min(crib_y, playfield.bottom - crib_h - 12))
                crib_rect = pygame.Rect(crib_x, crib_y, crib_w, crib_h)
                _draw_shadowed_panel(screen, crib_rect, (21, 71, 48), (199, 169, 102), radius=18)

                crib_font = pygame.font.SysFont("segoe ui", 16, bold=True)
                item_font = pygame.font.SysFont("segoe ui", 13)
                crib_label = "Crib" if _CLASSIC_SESSION.dealer == 1 else "Opponent's Crib"
                _draw_label(
                    screen,
                    crib_label,
                    (crib_rect.x + 12, crib_rect.y + 10),
                    crib_font,
                    (240, 227, 188),
                )

                y = crib_rect.y + 38
                for desc, _cards, points in crib_breakdown:
                    score_str = f"{desc}: +{points}"
                    item_surf = item_font.render(score_str, True, (223, 211, 181))
                    screen.blit(item_surf, (crib_rect.x + 12, y))
                    y += 22

                total_font = pygame.font.SysFont("segoe ui", 14, bold=True)
                total_str = f"Total: +{crib_pts}"
                total_surf = total_font.render(total_str, True, (240, 205, 124))
                screen.blit(total_surf, (crib_rect.x + 12, y + 8))

            _draw_round_summary_popup(
                screen,
                p1_pts,
                p2_pts,
                crib_pts,
                _CLASSIC_SESSION.dealer,
                player_name,
                discard_analysis_message,
            )

        # End-of-hand / game-over clickable button (in addition to the R key).
        if _CLASSIC_SESSION.phase in ("end", "game_over"):
            sw, sh = screen.get_width(), screen.get_height()
            btn = _primary_button_rect(sw, sh)
            is_hover = btn.collidepoint(pygame.mouse.get_pos())
            if is_hover:
                btn = btn.move(0, -2)
            _draw_shadowed_panel(
                screen,
                btn,
                (34, 50, 40) if is_hover else (28, 40, 33),
                (223, 190, 115),
                radius=18,
                shadow=(5, 7),
            )

            btn_text = "Next Round" if _CLASSIC_SESSION.phase == "end" else "Back to Intro"
            btn_font = pygame.font.SysFont("cambria", 28, bold=True)
            btn_shadow = btn_font.render(btn_text, True, (0, 0, 0))
            btn_label = btn_font.render(btn_text, True, (243, 227, 183))
            tx = btn.centerx - btn_label.get_width() // 2
            ty = btn.centery - btn_label.get_height() // 2
            screen.blit(btn_shadow, (tx + 2, ty + 2))
            screen.blit(btn_label, (tx, ty))

        if capture_gameplay_pending:
            capture_path = Path(args.capture_gameplay)
            capture_path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(screen, str(capture_path))
            print(f"Saved gameplay screenshot to: {capture_path}")
            capture_gameplay_pending = False
            if args.exit_after_capture:
                pygame.quit()
                return

        if capture_discard_pending and _CLASSIC_SESSION.phase == "discard":
            capture_path = Path(args.capture_discard)
            capture_path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(screen, str(capture_path))
            print(f"Saved discard screenshot to: {capture_path}")
            capture_discard_pending = False
            if args.exit_after_capture:
                pygame.quit()
                return

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
                return

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
