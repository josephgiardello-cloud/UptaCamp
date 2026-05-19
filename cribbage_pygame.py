import os
import sys
import random
from pathlib import Path
import argparse

import pygame
from itertools import combinations
from collections import Counter

import cards as cribbage_cards
import ai_strategy
from engine import CribbageEngine
from adapter import EngineAdapter
from phase_states import PhaseStateMachine
from animations import EffectsManager

# --- Constants ---
CARD_WIDTH = 120
CARD_HEIGHT = 180
FPS = 60
TABLE_COLOR = (34, 139, 34)
MAX_SCORE = 121
AI_LEVELS = {1: 'Easy', 2: 'Medium', 3: 'Hard'}

THEME = {
    "outer_bg": (50, 30, 14),
    "felt": (24, 92, 56),
    "felt_dark": (18, 72, 44),
    "wood": (102, 63, 34),
    "wood_light": (144, 93, 52),
    "panel": (246, 236, 214),
    "panel_edge": (90, 67, 39),
    "text": (245, 241, 230),
    "ink": (36, 28, 20),
    "gold": (214, 176, 91),
    "blue": (84, 145, 225),
    "red": (205, 83, 71),
    "muted": (194, 181, 157),
}

MAINE_COLORS = {
    "pine": (44, 56, 36),
    "bark": (80, 51, 20),
    "sand": (222, 184, 135),
    "gold": (212, 175, 55),
    "cream": (245, 234, 210),
}

# --- Global Game State ---
game_phase = 'intro'
dealer = 0  # 0 for Player, 1 for Dad
crib = []
selected_cards = []
player1_hand = []
player2_hand = []
pegging_pile = []
player_scores = [0, 0]
player_turn = 0
show_computer_hand = False
player_name = "Player"
message = "Select 2 cards to discard to the crib."

starter_card = None
_deck_labels = []
_stock_labels = []

# These are the 4-card hands kept after discard (used for counting).
player1_kept = []
player2_kept = []

winner_index = None  # 0 = player, 1 = dad, None = no winner yet
dad_ai_level = 2
pegging_passes = [False, False]
last_pegging_player = None

# Scoring breakdown tracking for end-of-round display
pegging_points = [0, 0]  # Points from pegging phase by player
round_breakdown = {  # Details of hand scoring
    'player': (0, []),  # (total_points, breakdown_list)
    'ai': (0, []),
    'crib': (0, [])
}

# Engine migration bridge (incremental refactor path)
_ENGINE = None
_ADAPTER = None
_PHASE_SM = None
_EFFECTS = None
_LAST_SCREEN_SIZE = (1280, 900)
_MAINE_BACK_SURFACE = None


def _check_for_winner():
    global winner_index
    if player_scores[0] >= MAX_SCORE and player_scores[1] >= MAX_SCORE:
        winner_index = -1  # tie
        return winner_index
    if player_scores[0] >= MAX_SCORE:
        winner_index = 0
        return winner_index
    if player_scores[1] >= MAX_SCORE:
        winner_index = 1
        return winner_index
    winner_index = None
    return winner_index

# --- Helper Functions ---
def _parse_label(label):
    parts = label.split(' of ')
    if len(parts) == 2:
        return parts[0].lower(), parts[1].lower()
    if '_of_' in label:
        r, s = label.split('_of_', 1)
        return r.lower(), s.lower()
    if '_' in label:
        r, s = label.split('_', 1)
        return r.lower(), s.lower()
    return label.lower(), ''

def _rank_index(rank):
    rank = rank.lower()
    mapping = {'ace': 1, 'a': 1, 'jack': 11, 'j': 11, 'queen': 12, 'q': 12, 'king': 13, 'k': 13}
    if rank in mapping: return mapping[rank]
    try: return int(rank)
    except: return 0

def _value_for_15(rank):
    rank = rank.lower()
    if rank in ('ace', 'a'): return 1
    if rank in ('jack', 'queen', 'king', 'j', 'q', 'k', '10'): return 10
    try: return int(rank)
    except: return 0


def _label_to_model_card(label: str) -> "cribbage_cards.Card":
    rank, suit = _parse_label(label)
    rank_map = {
        'ace': 'A',
        'jack': 'J',
        'queen': 'Q',
        'king': 'K',
    }
    suit_map = {
        'clubs': 'Clubs',
        'diamonds': 'Diamonds',
        'hearts': 'Hearts',
        'spades': 'Spades',
    }
    model_rank = rank_map.get(rank, rank.upper())
    model_suit = suit_map.get(suit, suit.title())
    return cribbage_cards.Card(model_rank, model_suit)


def _canonical_deck_labels():
    suits = ['clubs', 'diamonds', 'hearts', 'spades']
    ranks = ['ace', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king']
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
_ASSETS_DIR = _ROOT_DIR / 'assets'
_CARDS_DIR = _ASSETS_DIR / 'cards'


def _ensure_card_pngs_from_svgs():
    """Best-effort: if card SVGs exist but PNGs are missing, attempt conversion.

    This connects the game to the repo's converter scripts without making them a hard dependency.
    """
    try:
        svg_paths = list(_CARDS_DIR.glob('*.svg'))
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
    if path.suffix.lower() in ('.jpg', '.jpeg'):
        return surf.convert()
    return surf.convert_alpha()

def load_card_images():
    loaded = {}
    if _CARDS_DIR.exists():
        for path in _CARDS_DIR.glob('*.png'):
            stem = path.stem.lower()
            if stem in ('black_joker', 'red_joker'):
                continue
            # Ignore duplicates like "jack_of_spades2"; we want a clean 52-card deck.
            if stem.endswith('2'):
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
    y = max(510, screen_height - CARD_HEIGHT - 70) if player == 1 else 160
    return [(margin + i * spacing, y) for i in range(n)]


def _row_positions(n, screen_width, y, card_width, margin=60):
    available_width = screen_width - 2 * margin
    spacing = min((available_width - card_width) // (n - 1), card_width + 18) if n > 1 else 0
    return [(margin + i * spacing, y) for i in range(n)]


def _draw_shadowed_panel(screen, rect, fill, border, radius=18, shadow=(6, 7)):
    shadow_rect = rect.move(shadow)
    pygame.draw.rect(screen, (0, 0, 0, 85), shadow_rect, border_radius=radius)
    pygame.draw.rect(screen, fill, rect, border_radius=radius)
    pygame.draw.rect(screen, border, rect, width=2, border_radius=radius)


def _draw_board_frame(screen):
    sw, sh = screen.get_width(), screen.get_height()
    screen.fill(THEME["outer_bg"])

    board_rect = pygame.Rect(24, 24, sw - 48, sh - 48)
    pygame.draw.rect(screen, THEME["wood_light"], board_rect, border_radius=34)

    inner_rect = board_rect.inflate(-26, -26)
    pygame.draw.rect(screen, THEME["wood"], inner_rect, border_radius=28)

    felt_rect = inner_rect.inflate(-28, -28)
    pygame.draw.rect(screen, THEME["felt"], felt_rect, border_radius=22)

    band_w = max(18, felt_rect.width // 18)
    for x in range(felt_rect.left, felt_rect.right, band_w):
        shade = THEME["felt_dark"] if ((x - felt_rect.left) // band_w) % 2 == 0 else THEME["felt"]
        band = pygame.Rect(x, felt_rect.top, band_w, felt_rect.height)
        pygame.draw.rect(screen, shade, band.clip(felt_rect))

    pygame.draw.rect(screen, THEME["wood_light"], felt_rect, width=2, border_radius=18)


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
    if _MAINE_BACK_SURFACE is not None:
        textured = pygame.transform.smoothscale(_MAINE_BACK_SURFACE, (rect.width, rect.height))
        screen.blit(textured, rect.topleft)
        pygame.draw.rect(screen, (232, 208, 146), rect, width=3, border_radius=12)
        return

    pygame.draw.rect(screen, (235, 228, 214), rect, border_radius=12)
    inner = rect.inflate(-14, -14)
    pygame.draw.rect(screen, (56, 79, 115), inner, border_radius=10)
    pygame.draw.rect(screen, (232, 208, 146), inner.inflate(-12, -12), width=3, border_radius=8)


def _draw_score_panel(screen, dealer, player_scores, dad_ai_level, player_name):
    sw, sh = screen.get_width(), screen.get_height()
    panel_rect = pygame.Rect(sw - 250, sh - 176, 214, 138)
    _draw_shadowed_panel(screen, panel_rect, THEME["panel"], THEME["panel_edge"], radius=20)

    title_font = pygame.font.SysFont('georgia', 26, bold=True)
    body_font = pygame.font.SysFont('arial', 18, bold=True)
    small_font = pygame.font.SysFont('arial', 15)

    _draw_label(screen, "Cribbage", (panel_rect.x + 16, panel_rect.y + 12), title_font, THEME["ink"])
    _draw_label(screen, f"Dealer: {'You' if dealer == 0 else 'Dad'}", (panel_rect.x + 16, panel_rect.y + 48), body_font, THEME["ink"])
    _draw_label(screen, f"{player_name}: {player_scores[0]}", (panel_rect.x + 16, panel_rect.y + 78), body_font, THEME["blue"])
    _draw_label(screen, f"Dad: {player_scores[1]}", (panel_rect.x + 16, panel_rect.y + 104), body_font, THEME["red"])
    _draw_label(screen, f"AI: {AI_LEVELS[dad_ai_level]}", (panel_rect.x + 16, panel_rect.y + 120), small_font, THEME["muted"])


def _draw_scoring_breakdown(screen, player_idx, breakdown_list, total_points, player_name):
    """Draw a breakdown of scoring items for a player."""
    sw, sh = screen.get_width(), screen.get_height()
    if player_idx == 0:
        panel_x = 24
    else:
        panel_x = sw - 244
    panel_y = sh // 2 - 140
    panel_rect = pygame.Rect(panel_x, panel_y, 220, 280)

    _draw_shadowed_panel(screen, panel_rect, THEME["panel"], THEME["panel_edge"], radius=18)

    header_font = pygame.font.SysFont('arial', 16, bold=True)
    item_font = pygame.font.SysFont('arial', 13)
    total_font = pygame.font.SysFont('arial', 14, bold=True)

    player_label = player_name if player_idx == 0 else "Dad"
    _draw_label(screen, f"{player_label}'s Score", (panel_rect.x + 12, panel_rect.y + 10), header_font, THEME["ink"])

    y_offset = panel_rect.y + 38
    if breakdown_list:
        for desc, cards, points in breakdown_list:
            score_str = f"{desc}: +{points}"
            item_surf = item_font.render(score_str, True, THEME["ink"])
            screen.blit(item_surf, (panel_rect.x + 12, y_offset))
            y_offset += 22

    pygame.draw.line(screen, THEME["ink"], (panel_rect.x + 12, y_offset), (panel_rect.right - 12, y_offset), 1)
    y_offset += 8

    total_str = f"Hand: +{total_points}"
    total_surf = total_font.render(total_str, True, THEME["blue"] if player_idx == 0 else THEME["red"])
    screen.blit(total_surf, (panel_rect.x + 12, y_offset))


def _draw_game_header(screen, message):
    sw = screen.get_width()
    body_font = pygame.font.SysFont('arial', 23, bold=True)

    msg_box = pygame.Rect(sw // 2 - 360, 26, 720, 50)
    pygame.draw.rect(screen, (0, 0, 0, 95), msg_box.move(4, 5), border_radius=16)
    pygame.draw.rect(screen, THEME["panel"], msg_box, border_radius=16)
    pygame.draw.rect(screen, THEME["panel_edge"], msg_box, width=2, border_radius=16)
    msg_surf = body_font.render(message, True, THEME["ink"])
    screen.blit(msg_surf, (msg_box.centerx - msg_surf.get_width() // 2, msg_box.centery - msg_surf.get_height() // 2))


def _draw_crib_area(screen, crib_count, starter_card, card_images):
    sw = screen.get_width()
    label_font = pygame.font.SysFont('arial', 18, bold=True)
    small_font = pygame.font.SysFont('arial', 16)

    crib_panel = pygame.Rect(sw // 2 - 250, 316, 500, 118)
    _draw_shadowed_panel(screen, crib_panel, (32, 85, 52), THEME["wood_light"], radius=20)
    _draw_label(screen, "Opponent's Crib", (crib_panel.x + 18, crib_panel.y + 12), label_font, THEME["text"])
    _draw_label(screen, "Drop 2 cards here", (crib_panel.x + 18, crib_panel.y + 34), small_font, THEME["gold"])

    card_w, card_h = 64, 96
    for i in range(2):
        card_rect = pygame.Rect(crib_panel.x + 180 + i * 74, crib_panel.y + 12, card_w, card_h)
        if i < crib_count:
            _draw_card_back(screen, card_rect)
        else:
            pygame.draw.rect(screen, (255, 255, 255, 24), card_rect, width=2, border_radius=12)

    starter_box = pygame.Rect(crib_panel.right - 104, crib_panel.y + 9, 94, 100)
    pygame.draw.rect(screen, THEME["panel"], starter_box, border_radius=14)
    pygame.draw.rect(screen, THEME["panel_edge"], starter_box, width=2, border_radius=14)
    _draw_label(screen, "Starter", (starter_box.x + 16, starter_box.y + 6), small_font, THEME["ink"])
    if starter_card is not None:
        starter_surf = pygame.transform.smoothscale(card_images[starter_card], (56, 82))
        screen.blit(starter_surf, (starter_box.x + 19, starter_box.y + 16))


def _draw_scaled_card(screen, surface, rect, size):
    scaled = pygame.transform.smoothscale(surface, size)
    screen.blit(scaled, rect.topleft)


def _pegging_target_center(slot_index):
    sw, _ = _LAST_SCREEN_SIZE
    x = sw // 2 - 220 + slot_index * 26 + 46
    y = 458 + 69
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
    return sum(_value_for_15(_parse_label(c.label)[0]) for c in pegging_pile)


def _score_pegging_play(pile):
    if not pile:
        return 0

    total = sum(_value_for_15(_parse_label(c.label)[0]) for c in pile)
    points = 0

    if total == 15:
        points += 2
    if total == 31:
        points += 2

    # Pair / pair royal / double pair royal from the end of the pile.
    last_rank = _parse_label(pile[-1].label)[0]
    same_rank_count = 1
    for i in range(len(pile) - 2, -1, -1):
        if _parse_label(pile[i].label)[0] == last_rank:
            same_rank_count += 1
        else:
            break
    if same_rank_count == 2:
        points += 2
    elif same_rank_count == 3:
        points += 6
    elif same_rank_count >= 4:
        points += 12

    # Longest trailing run scores.
    for run_len in range(len(pile), 2, -1):
        ranks = [_rank_index(_parse_label(c.label)[0]) for c in pile[-run_len:]]
        if len(set(ranks)) != run_len:
            continue
        if max(ranks) - min(ranks) + 1 == run_len:
            points += run_len
            break

    return points


def _score_labels_hand(hand_labels, starter_label, is_crib=False):
    hand_model = [_label_to_model_card(lbl) for lbl in hand_labels]
    starter_model = _label_to_model_card(starter_label)
    total, _ = cribbage_cards.score_hand(hand_model, starter_model, is_crib=is_crib)
    return total


def _choose_dad_discards():
    dad_labels = [c.label for c in player2_hand]
    return ai_strategy.choose_discard_indices(
        dad_labels=dad_labels,
        dad_ai_level=dad_ai_level,
        dealer_is_dad=(dealer == 1),
        canonical_deck_labels=_canonical_deck_labels(),
        score_labels_hand=_score_labels_hand,
    )


def _choose_dad_pegging_index(current_total):
    hand_labels = [c.label for c in player2_hand]
    pegging_labels = [c.label for c in pegging_pile]
    return ai_strategy.choose_pegging_index(
        hand_labels=hand_labels,
        current_total=current_total,
        dad_ai_level=dad_ai_level,
        value_for_15=_value_for_15,
        parse_label=_parse_label,
        score_pegging_play=_score_pegging_play,
        label_card_factory=_LabelCard,
        current_pegging_labels=pegging_labels,
        estimate_opponent_reply_risk=_estimate_opponent_reply_risk,
    )


def _estimate_opponent_reply_risk(trial_pile):
    trial_total = sum(_value_for_15(_parse_label(c.label)[0]) for c in trial_pile)
    opponent_hand_size = len(player1_hand)
    if opponent_hand_size <= 0:
        return 0.0

    known_labels = {c.label for c in player2_hand}
    known_labels.update(c.label for c in trial_pile)
    if starter_card is not None:
        known_labels.add(starter_card)

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
    global game_phase, message, pegging_points
    if player1_hand or player2_hand:
        return False

    # Last card point if sequence did not already end at 31.
    if pegging_pile and get_pegging_total() != 31 and last_pegging_player is not None:
        player_scores[last_pegging_player] += 1
        pegging_points[last_pegging_player] += 1
        if last_pegging_player == 0:
            message = "Last card for 1 point. Counting hands."
        else:
            message = "Dad gets last card for 1 point. Counting hands."
    else:
        message = "Counting hands."

    game_phase = 'counting'
    return True


def _handle_go(player_idx):
    global player_turn, message, pegging_points
    pegging_passes[player_idx] = True
    other = 1 - player_idx

    if pegging_passes[other]:
        if pegging_pile and get_pegging_total() < 31 and last_pegging_player is not None:
            player_scores[last_pegging_player] += 1
            pegging_points[last_pegging_player] += 1
            _queue_score_popup(last_pegging_player, 1)
            if last_pegging_player == 0:
                message = "Go for you (+1). New count."
            else:
                message = "Go for Dad (+1). New count."
        else:
            message = "No plays. New count."
        pegging_pile.clear()
        pegging_passes[0] = False
        pegging_passes[1] = False
        if last_pegging_player is not None:
            player_turn = 1 - last_pegging_player
    else:
        player_turn = other
        message = "Go. " + ("Dad's turn." if other == 1 else "Your turn.")


def _play_pegging_card(player_idx, idx):
    global player_turn, message, pegging_points
    if player_idx == 0:
        card = player1_hand.pop(idx)
    else:
        card = player2_hand.pop(idx)

    if _EFFECTS is not None:
        start = card.rect.center
        end = _pegging_target_center(len(pegging_pile))
        _EFFECTS.add_card_flight(card.image, start, end)

    pegging_pile.append(card)
    pegging_passes[0] = False
    pegging_passes[1] = False

    points = _score_pegging_play(pegging_pile)
    player_scores[player_idx] += points
    pegging_points[player_idx] += points
    _queue_score_popup(player_idx, points)

    name = player_name if player_idx == 0 else 'Dad'
    point_note = f" (+{points})" if points else ""

    if get_pegging_total() == 31:
        message = f"{name} played 31{point_note}. New count."
        if _EFFECTS is not None:
            _EFFECTS.trigger_shake(intensity=7, duration_ms=220)
        pegging_pile.clear()
        player_turn = 1 - player_idx
    else:
        message = f"{name} pegs{point_note}. " + ("Dad's turn." if player_idx == 0 else "Your turn.")
        player_turn = 1 - player_idx

    global last_pegging_player
    last_pegging_player = player_idx

# --- Event Handlers ---
def handle_discard(event):
    global selected_cards, player1_hand, player2_hand, crib, game_phase, message, player_turn, starter_card, _stock_labels, player1_kept, player2_kept, last_pegging_player
    if event.type == pygame.MOUSEBUTTONDOWN:
        for idx, card in enumerate(player1_hand):
            if card.rect.collidepoint(event.pos) and idx not in selected_cards:
                selected_cards.append(idx)
                if len(selected_cards) == 2:
                    if _ADAPTER is not None and _ENGINE is not None:
                        # Route discard transition through engine adapter.
                        _ADAPTER.update_engine_from_globals()
                        _ENGINE.handle_discard(selected_cards)
                        _ADAPTER.update_globals_from_engine()
                    else:
                        # Fallback legacy path
                        for i in sorted(selected_cards, reverse=True):
                            crib.append(player1_hand.pop(i))
                        dad_discards = _choose_dad_discards()
                        for i in sorted(dad_discards, reverse=True):
                            crib.append(player2_hand.pop(i))
                        player1_kept = player1_hand.copy()
                        player2_kept = player2_hand.copy()
                        starter_card = None
                        if _stock_labels:
                            starter_card = _stock_labels.pop(0)
                        game_phase = 'pegging'
                        player_turn = 1 - dealer
                        pegging_passes[0] = False
                        pegging_passes[1] = False
                        last_pegging_player = None
                        message = "Pegging phase begins!"

                    selected_cards = []
                break

def handle_pegging(event):
    global player_turn

    if _finalize_pegging_if_complete():
        return

    current_total = get_pegging_total()

    if player_turn == 0: # Player Turn
        player_can_move = any(current_total + _value_for_15(_parse_label(c.label)[0]) <= 31 for c in player1_hand)
        if not player_can_move:
            _handle_go(0)
            return
        if event and event.type == pygame.MOUSEBUTTONDOWN:
            for idx, card in enumerate(player1_hand):
                val = _value_for_15(_parse_label(card.label)[0])
                if card.rect.collidepoint(event.pos) and current_total + val <= 31:
                    _play_pegging_card(0, idx)
                    _check_for_winner()
                    break
    else: # Dad Turn (AI)
        dad_can_move = any(current_total + _value_for_15(_parse_label(c.label)[0]) <= 31 for c in player2_hand)
        if not dad_can_move:
            _handle_go(1)
            return
        chosen = _choose_dad_pegging_index(current_total)
        if chosen is not None:
            _play_pegging_card(1, chosen)
            _check_for_winner()

    _finalize_pegging_if_complete()


def handle_counting():
    global game_phase, message, player_scores, player1_kept, player2_kept, round_breakdown

    if _ADAPTER is not None and _ENGINE is not None:
        _ADAPTER.update_engine_from_globals()
        results = _ENGINE.count_hands(_label_to_model_card)
        _ADAPTER.update_globals_from_engine()
        p1_points = results["player"]
        p2_points = results["ai"]
        crib_points = results["crib"]
        # For engine path, breakdown would come from engine; for now use empty
        round_breakdown = {'player': (p1_points, []), 'ai': (p2_points, []), 'crib': (crib_points, [])}
    else:
        if starter_card is None:
            message = "No starter card available. Press R to reset."
            game_phase = 'end'
            return

        starter = _label_to_model_card(starter_card)
        p1_hand_model = [_label_to_model_card(c.label) for c in player1_kept]
        p2_hand_model = [_label_to_model_card(c.label) for c in player2_kept]
        crib_model = [_label_to_model_card(c.label) for c in crib]

        p1_total, p1_breakdown = cribbage_cards.score_hand(p1_hand_model, starter, is_crib=False)
        p2_total, p2_breakdown = cribbage_cards.score_hand(p2_hand_model, starter, is_crib=False)
        crib_total, crib_breakdown = cribbage_cards.score_hand(crib_model, starter, is_crib=True) if len(crib_model) == 4 else (0, [])
        p1_points = p1_total
        p2_points = p2_total
        crib_points = crib_total

        round_breakdown = {
            'player': (p1_points, p1_breakdown),
            'ai': (p2_points, p2_breakdown),
            'crib': (crib_points, crib_breakdown)
        }

        player_scores[0] += p1_points
        player_scores[1] += p2_points
        player_scores[dealer] += crib_points

    w = _check_for_winner()
    if w is None:
        message = f"Counted: You +{p1_points}, Dad +{p2_points}, Crib +{crib_points} (dealer). Press R for next round."
        game_phase = 'end'
    else:
        if w == -1:
            message = f"Game Over at {MAX_SCORE}! It's a tie. Press R to return to the intro."
        elif w == 0:
            message = f"Game Over! {player_name} wins with {player_scores[0]} points. Press R to return to the intro."
        else:
            message = f"Game Over! Dad wins with {player_scores[1]} points. Press R to return to the intro."
        game_phase = 'game_over'

# --- Main Entry ---
def main():
    global message, dealer, player1_hand, player2_hand, game_phase, player_name, pegging_pile, starter_card, _deck_labels, _stock_labels, player_scores, winner_index, dad_ai_level, last_pegging_player
    global _ENGINE, _ADAPTER, _PHASE_SM, _EFFECTS, _LAST_SCREEN_SIZE, _MAINE_BACK_SURFACE
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--capture-title', dest='capture_title', default=None)
    parser.add_argument('--capture-gameplay', dest='capture_gameplay', default=None)
    parser.add_argument('--exit-after-capture', dest='exit_after_capture', action='store_true')
    args, _ = parser.parse_known_args()
    capture_title_pending = bool(args.capture_title)
    capture_gameplay_pending = bool(args.capture_gameplay)

    pygame.init()
    screen = pygame.display.set_mode((1280, 900), pygame.RESIZABLE)
    pygame.display.set_caption("Upta - The Camp Cribbage Game")
    clock = pygame.time.Clock()

    _ENGINE = CribbageEngine()
    _ADAPTER = EngineAdapter(_ENGINE, sys.modules[__name__])
    _PHASE_SM = PhaseStateMachine(_ENGINE)
    _EFFECTS = EffectsManager()

    intro_background = None
    for intro_candidate in ('table.jpg', 'table.png', 'board.jpg', 'welcome_bg.png', 'Tony.jpg', 'name_entry_bg.jpg'):
        intro_path = _ASSETS_DIR / intro_candidate
        if intro_path.exists():
            try:
                intro_background = _load_image(intro_path)
                break
            except pygame.error:
                intro_background = None

    gameplay_background = None
    gameplay_background_name = None
    for candidate in ('name_entry_bg.jpg', 'table.jpg', 'table.png', 'board.jpg'):
        path = _ASSETS_DIR / candidate
        if not path.exists():
            continue
        try:
            gameplay_background = _load_image(path)
            gameplay_background_name = candidate
            break
        except pygame.error:
            gameplay_background = None
            gameplay_background_name = None
            continue

    maine_back = _ASSETS_DIR / 'maine.jpg'
    if maine_back.exists():
        try:
            _MAINE_BACK_SURFACE = _load_image(maine_back)
        except pygame.error:
            _MAINE_BACK_SURFACE = None
    
    _ensure_card_pngs_from_svgs()
    card_images = load_card_images()

    def _start_fresh_game():
        global winner_index
        nonlocal card_images
        global pegging_points, round_breakdown
        # Fresh game from intro
        pegging_points[:] = [0, 0]
        round_breakdown = {'player': (0, []), 'ai': (0, []), 'crib': (0, [])}
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

        player1_hand[:] = [CardSprite(card_images[_deck_labels[i]], (0, 0), _deck_labels[i]) for i in range(6)]
        player2_hand[:] = [CardSprite(card_images[_deck_labels[i + 6]], (0, 0), _deck_labels[i + 6]) for i in range(6)]

        if _ENGINE is not None:
            _ENGINE.state.dad_ai_level = dad_ai_level
            _ENGINE.start_new_game(player1_hand, player2_hand, _stock_labels, dealer=dealer)
            if _ADAPTER is not None:
                _ADAPTER.update_globals_from_engine()

        # Start at discard phase
        message = "Select 2 cards to discard to the crib."
        return dealer, starter_card, message

    def _start_next_round():
        """Start the next hand while keeping the running score."""
        global last_pegging_player
        nonlocal card_images
        global pegging_points, round_breakdown
        pegging_points[:] = [0, 0]
        round_breakdown = {'player': (0, []), 'ai': (0, []), 'crib': (0, [])}
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

        player1_hand[:] = [CardSprite(card_images[_deck_labels[i]], (0, 0), _deck_labels[i]) for i in range(6)]
        player2_hand[:] = [CardSprite(card_images[_deck_labels[i + 6]], (0, 0), _deck_labels[i + 6]) for i in range(6)]

        if _ENGINE is not None:
            _ENGINE.state.dad_ai_level = dad_ai_level
            _ENGINE.start_next_round(player1_hand, player2_hand, _stock_labels)
            if _ADAPTER is not None:
                _ADAPTER.update_globals_from_engine()

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
        game_phase = 'pegging'
        message = 'Pegging phase preview.'

    def _primary_button_rect(sw: int, sh: int) -> pygame.Rect:
        w, h = 260, 60
        return pygame.Rect(sw // 2 - w // 2, sh - 180, w, h)

    # Initialize deck containers used across rounds.
    _deck_labels = _canonical_deck_labels()
    _stock_labels = []

    # Intro screen difficulty buttons and state
    difficulty_buttons = {}
    difficulty_descriptions = {
        1: "Random play\nEasy wins",
        2: "Monte Carlo\nMixed strategy",
        3: "Risk simulation\nHard opponent"
    }

    if capture_gameplay_pending:
        _prepare_gameplay_preview_state()

    running = True
    while running:
        if _EFFECTS is not None:
            _EFFECTS.update(clock.get_time())

        if game_phase == 'intro':
            sw, sh = screen.get_width(), screen.get_height()
            if intro_background is not None:
                bg = pygame.transform.smoothscale(intro_background, (sw, sh))
                screen.blit(bg, (0, 0))
            else:
                screen.fill(THEME["outer_bg"])

            overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 92))
            screen.blit(overlay, (0, 0))

            title_font = pygame.font.SysFont('georgia', 78, bold=True)
            subtitle_font = pygame.font.SysFont('arial', 20, bold=True)
            button_font = pygame.font.SysFont('arial', 24, bold=True)
            desc_font = pygame.font.SysFont('arial', 15)
            start_font = pygame.font.SysFont('arial', 26, bold=True)

            title = title_font.render('Upta', True, MAINE_COLORS["cream"])
            title_outline = title_font.render('Upta', True, MAINE_COLORS["pine"])
            title_warm_shadow = title_font.render('Upta', True, MAINE_COLORS["bark"])
            subtitle = subtitle_font.render('Play the hand. Mind the crib. Beat the table.', True, MAINE_COLORS["sand"])

            title_top = 44
            title_to_subtitle_gap = 12
            title_x = sw // 2 - title.get_width() // 2
            title_y = title_top
            subtitle_x = sw // 2 - subtitle.get_width() // 2
            subtitle_y = title_y + title.get_height() + title_to_subtitle_gap

            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
                screen.blit(title_outline, (title_x + dx, title_y + dy))
            screen.blit(title_warm_shadow, (title_x + 4, title_y + 4))
            screen.blit(title, (title_x, title_y))

            title_glint = title_font.render('Upta', True, MAINE_COLORS["gold"])
            glint_clip = pygame.Rect(0, 0, title_glint.get_width(), max(1, title_glint.get_height() // 3))
            screen.blit(title_glint, (title_x, title_y), area=glint_clip)
            screen.blit(subtitle, (subtitle_x, subtitle_y))

            panel_rect = pygame.Rect(sw // 2 - 290, sh // 2 - 150, 580, 300)
            panel_surface = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
            panel_surface.fill((15, 15, 15, 110))
            screen.blit(panel_surface, panel_rect.topleft)
            pygame.draw.rect(screen, (236, 219, 184), panel_rect, width=2, border_radius=24)

            diff_label = subtitle_font.render('Choose difficulty', True, (245, 238, 220))
            screen.blit(diff_label, (sw // 2 - diff_label.get_width() // 2, panel_rect.y + 18))

            button_width, button_height = 128, 86
            button_spacing = 18
            total_width = 3 * button_width + 2 * button_spacing
            start_x = (sw - total_width) // 2
            button_y = panel_rect.y + 58
            difficulty_buttons = {}

            for i, (level, name) in enumerate([(1, 'Easy'), (2, 'Medium'), (3, 'Hard')]):
                btn_x = start_x + i * (button_width + button_spacing)
                btn_rect = pygame.Rect(btn_x, button_y, button_width, button_height)
                difficulty_buttons[level] = btn_rect

                if level == dad_ai_level:
                    btn_color = (164, 110, 58)
                    border_color = (240, 204, 114)
                    text_color = (255, 255, 255)
                else:
                    btn_color = (236, 228, 214)
                    border_color = (180, 160, 130)
                    text_color = (34, 26, 19)

                pygame.draw.rect(screen, btn_color, btn_rect, width=0, border_radius=16)
                pygame.draw.rect(screen, border_color, btn_rect, width=2, border_radius=16)

                level_text = button_font.render(name, True, text_color)
                screen.blit(level_text, (btn_x + button_width // 2 - level_text.get_width() // 2, button_y + 12))

                desc_lines = difficulty_descriptions[level].split('\n')
                for j, line in enumerate(desc_lines):
                    desc = desc_font.render(line, True, (221, 206, 176))
                    screen.blit(desc, (btn_x + button_width // 2 - desc.get_width() // 2, button_y + 44 + j * 16))

            start_button_width, start_button_height = 214, 58
            start_btn_rect = pygame.Rect(sw // 2 - start_button_width // 2, panel_rect.bottom - 74, start_button_width, start_button_height)
            pygame.draw.rect(screen, (120, 77, 39), start_btn_rect, width=0, border_radius=18)
            pygame.draw.rect(screen, (240, 204, 114), start_btn_rect, width=2, border_radius=18)

            start_text = start_font.render('START GAME', True, (255, 255, 255))
            screen.blit(start_text, (
                start_btn_rect.centerx - start_text.get_width() // 2,
                start_btn_rect.centery - start_text.get_height() // 2
            ))

            instructions_font = pygame.font.SysFont('arial', 16)
            inst1 = instructions_font.render('Press 1/2/3 or click a button', True, (210, 198, 176))
            inst2 = instructions_font.render('Press Enter or click START GAME', True, (210, 198, 176))
            screen.blit(inst1, (sw // 2 - inst1.get_width() // 2, panel_rect.bottom + 12))
            screen.blit(inst2, (sw // 2 - inst2.get_width() // 2, panel_rect.bottom + 32))

            if capture_title_pending:
                capture_path = Path(args.capture_title)
                capture_path.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(screen, str(capture_path))
                print(f"Saved title screenshot to: {capture_path}")
                capture_title_pending = False
                if args.exit_after_capture:
                    pygame.quit()
                    return

            pygame.display.flip()
            clock.tick(FPS)

            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    dad_ai_level = int(event.unicode)
                elif event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    # Start a brand-new game
                    d, sc, msg = _start_fresh_game()
                    dealer = d
                    starter_card = sc
                    message = msg
                    game_phase = 'discard'
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    # Check if difficulty button clicked
                    for level, btn_rect in difficulty_buttons.items():
                        if btn_rect.collidepoint(mouse_pos):
                            dad_ai_level = level
                    
                    # Check if start button clicked
                    if start_btn_rect.collidepoint(mouse_pos):
                        d, sc, msg = _start_fresh_game()
                        dealer = d
                        starter_card = sc
                        message = msg
                        game_phase = 'discard'
            continue

        sw, sh = screen.get_width(), screen.get_height()
        _LAST_SCREEN_SIZE = (sw, sh)
        if gameplay_background is not None:
            bg = pygame.transform.smoothscale(gameplay_background, (sw, sh))
            screen.blit(bg, (0, 0))
        else:
            _draw_board_frame(screen)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F2:
                dad_ai_level = 1 if dad_ai_level == 3 else dad_ai_level + 1
                message = f"Dad AI level set to {AI_LEVELS[dad_ai_level]}."
            
            if game_phase == 'discard':
                handle_discard(event)
            elif game_phase == 'pegging' and event.type == pygame.MOUSEBUTTONDOWN:
                handle_pegging(event)
            elif game_phase == 'end':
                if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    d, sc, msg = _start_next_round()
                    dealer = d
                    starter_card = sc
                    message = msg
                    game_phase = 'discard'
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    sw, sh = screen.get_width(), screen.get_height()
                    if _primary_button_rect(sw, sh).collidepoint(event.pos):
                        d, sc, msg = _start_next_round()
                        dealer = d
                        starter_card = sc
                        message = msg
                        game_phase = 'discard'
            elif game_phase == 'game_over':
                if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    # Return to intro; starting a new game resets scores.
                    game_phase = 'intro'
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    sw, sh = screen.get_width(), screen.get_height()
                    if _primary_button_rect(sw, sh).collidepoint(event.pos):
                        game_phase = 'intro'

        # Let the game logic advance even when there are no input events.
        if not capture_gameplay_pending:
            if game_phase == 'pegging':
                handle_pegging(None)
            elif game_phase == 'counting':
                handle_counting()

        # Keep phase machine synchronized during transition period.
        if _ADAPTER is not None and _PHASE_SM is not None:
            _ADAPTER.update_engine_from_globals()
            _PHASE_SM.update()
            _ADAPTER.update_globals_from_engine()

        _draw_game_header(screen, message)
        _draw_score_panel(screen, dealer, player_scores, dad_ai_level, player_name)
        _draw_crib_area(screen, len(crib), starter_card, card_images)

        # Update Card Positions for rendering
        p1_pos = fixed_hand_positions(1, len(player1_hand), sw, sh)
        mouse_pos = pygame.mouse.get_pos()
        for i, card in enumerate(player1_hand):
            card.rect.topleft = p1_pos[i]
            hovered = card.rect.collidepoint(mouse_pos) and game_phase in ('discard', 'pegging') and player_turn == 0
            draw_rect = card.rect.copy()
            if hovered:
                draw_rect.y -= 14

            shadow = pygame.Rect(draw_rect.x + 6, draw_rect.y + 8, draw_rect.width, draw_rect.height)
            pygame.draw.rect(screen, (0, 0, 0, 80), shadow, border_radius=12)
            if hovered:
                lifted = pygame.transform.rotozoom(card.image, -3, 1.03)
                lifted_rect = lifted.get_rect(center=draw_rect.center)
                screen.blit(lifted, lifted_rect)
            else:
                card.draw(screen)

        p2_pos = _row_positions(len(player2_hand), sw, 170, 86)
        p2_size = (90, 135)
        for i, card in enumerate(player2_hand):
            card.rect = pygame.Rect(p2_pos[i][0], p2_pos[i][1], p2_size[0], p2_size[1])
            shadow = pygame.Rect(card.rect.x + 5, card.rect.y + 6, card.rect.width, card.rect.height)
            pygame.draw.rect(screen, (0, 0, 0, 80), shadow, border_radius=12)
            _draw_card_back(screen, card.rect)

        pegging_card_size = (92, 138)
        pegging_y = 458
        for i, card in enumerate(pegging_pile):
            card.rect = pygame.Rect(sw // 2 - 220 + i * 26, pegging_y, pegging_card_size[0], pegging_card_size[1])
            shadow = pygame.Rect(card.rect.x + 4, card.rect.y + 6, card.rect.width, card.rect.height)
            pygame.draw.rect(screen, (0, 0, 0, 75), shadow, border_radius=12)
            _draw_scaled_card(screen, card.image, card.rect, pegging_card_size)

        if _EFFECTS is not None:
            _EFFECTS.draw(screen)
            shake_x, shake_y = _EFFECTS.shake_offset()
            if shake_x or shake_y:
                shaken = screen.copy()
                screen.fill((0, 0, 0))
                screen.blit(shaken, (shake_x, shake_y))

        font = pygame.font.SysFont('arial', 22, bold=True)

        total_surf = font.render(f"Pegging Total: {get_pegging_total()}", True, THEME["text"])
        screen.blit(total_surf, (sw // 2 - total_surf.get_width() // 2, pegging_y + pegging_card_size[1] + 10))

        # Display scoring breakdown during end-of-hand phase
        if game_phase == 'end':
            p1_pts, p1_breakdown = round_breakdown['player']
            p2_pts, p2_breakdown = round_breakdown['ai']
            crib_pts, crib_breakdown = round_breakdown['crib']
            
            # Show player and ai hand scoring
            _draw_scoring_breakdown(screen, 0, p1_breakdown, p1_pts, player_name)
            _draw_scoring_breakdown(screen, 1, p2_breakdown, p2_pts, player_name)
            
            # Show crib scoring in the center if dealer
            if crib_pts > 0 or crib_breakdown:
                crib_panel_x = sw // 2 - 110
                crib_panel_y = sh // 2 + 60
                crib_rect = pygame.Rect(crib_panel_x, crib_panel_y, 220, 140)
                _draw_shadowed_panel(screen, crib_rect, (32, 85, 52), THEME["wood_light"], radius=18)
                
                crib_font = pygame.font.SysFont('arial', 16, bold=True)
                item_font = pygame.font.SysFont('arial', 13)
                crib_label = "Crib" if dealer == 1 else "Opponent's Crib"
                _draw_label(screen, crib_label, (crib_rect.x + 12, crib_rect.y + 10), crib_font, THEME["text"])
                
                y = crib_rect.y + 38
                for desc, cards, points in crib_breakdown:
                    score_str = f"{desc}: +{points}"
                    item_surf = item_font.render(score_str, True, THEME["text"])
                    screen.blit(item_surf, (crib_rect.x + 12, y))
                    y += 22
                
                total_font = pygame.font.SysFont('arial', 14, bold=True)
                total_str = f"Total: +{crib_pts}"
                total_surf = total_font.render(total_str, True, THEME["gold"])
                screen.blit(total_surf, (crib_rect.x + 12, y + 8))

        # End-of-hand / game-over clickable button (in addition to the R key).
        if game_phase in ('end', 'game_over'):
            sw, sh = screen.get_width(), screen.get_height()
            btn = _primary_button_rect(sw, sh)
            btn_surface = pygame.Surface(btn.size, pygame.SRCALPHA)
            btn_surface.fill((0, 0, 0, 110))
            screen.blit(btn_surface, btn.topleft)
            pygame.draw.rect(screen, THEME["panel"], btn, 2, border_radius=18)

            btn_text = 'Next Round' if game_phase == 'end' else 'Back to Intro'
            btn_font = pygame.font.SysFont('arial', 28, bold=True)
            btn_shadow = btn_font.render(btn_text, True, (0, 0, 0))
            btn_label = btn_font.render(btn_text, True, THEME["panel"])
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

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()

