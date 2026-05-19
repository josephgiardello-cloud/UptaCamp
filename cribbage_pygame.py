import os
import pygame
import sys
import random
from itertools import combinations
from collections import Counter

# --- Constants ---
CARD_WIDTH = 120
CARD_HEIGHT = 180
FPS = 60
TABLE_COLOR = (34, 139, 34)
MAX_SCORE = 121

# --- Global State ---
message = "Select 2 cards to discard to the crib."
dealer = 0  # 0 for Player, 1 for Dad
crib = []
selected_cards = []
player1_hand = []
player2_hand = []
pegging_pile = []
player_scores = [0, 0]
game_phase = 'discard'
player_turn = 0
show_computer_hand = False
player_name = "Player"
starter_label = None
starter_sprite = None
counting_done = False
counting_step = 0
deck_keys = []
player1_kept_labels = []
player2_kept_labels = []
last_player_to_play = None
passes_in_row = 0
card_images_global = {}

# --- Dummy fallback for missing functions ---
def get_player_name(screen):
    return "Player"

# --- Cribbage scoring helpers ---
def _parse_label(label):
    parts = label.split(' of ')
    if len(parts) == 2:
        return parts[0].lower(), parts[1].lower()
    if '_' in label:
        # Handles keys like "ace_of_spades" and other underscored strings.
        if '_of_' in label:
            r, s = label.split('_of_', 1)
            return r.lower(), s.lower()
        r, s = label.split('_', 1)
        return r.lower(), s.lower()
    return label.lower(), ''

def _rank_index(rank):
    rank = rank.lower()
    mapping = {'ace': 1, 'jack': 11, 'queen': 12, 'king': 13}
    if rank in mapping: return mapping[rank]
    try: return int(rank)
    except: return 0

def _value_for_15(rank):
    rank = rank.lower()
    if rank == 'ace': return 1
    if rank in ('jack', 'queen', 'king', '10'): return 10
    try: return int(rank)
    except: return 0

class CardValueHelper:
    @staticmethod
    def get_val(label):
        rank, _ = _parse_label(label)
        return _value_for_15(rank)

def score_hand_labels(labels, starter_label, is_crib=False):
    all_labels = list(labels) + [starter_label]
    total_points = 0
    breakdown = []
    parsed = [_parse_label(l) for l in all_labels]
    ranks = [p[0] for p in parsed]
    suits = [p[1] for p in parsed]

    # 1) Fifteens
    values = [_value_for_15(r) for r in ranks]
    for r in range(2, len(values)+1):
        for combo_idx in combinations(range(len(values)), r):
            if sum(values[i] for i in combo_idx) == 15:
                total_points += 2
                breakdown.append(("15", [all_labels[i] for i in combo_idx], 2))

    # 2) Pairs
    rc = Counter(ranks)
    for rank, cnt in rc.items():
        if cnt >= 2:
            pts = (cnt * (cnt - 1))
            involved = [l for l in all_labels if _parse_label(l)[0] == rank]
            breakdown.append((f"Pair(s) {rank}", involved, pts))
            total_points += pts

    # 3) Runs (cribbage-correct via combinations)
    # Score only the longest run length; duplicates create multiple combos.
    rank_nums = [_rank_index(r) for r in ranks]
    for run_len in range(5, 2, -1):
        run_combos = []
        for combo_idx in combinations(range(len(rank_nums)), run_len):
            nums = sorted(rank_nums[i] for i in combo_idx)
            if len(set(nums)) != run_len:
                continue
            if nums[-1] - nums[0] == run_len - 1:
                run_combos.append(combo_idx)
        if run_combos:
            total_points += run_len * len(run_combos)
            for combo_idx in run_combos:
                breakdown.append((
                    f"Run ({run_len})",
                    [all_labels[i] for i in combo_idx],
                    run_len,
                ))
            break
    
    # 4) Flush
    hand_suits = suits[:-1]
    sc = Counter(hand_suits)
    if len(sc) == 1:
        s, cnt = sc.most_common(1)[0]
        if cnt == 4:
            if suits[-1] == s:
                total_points += 5
                breakdown.append(("Flush (5)", all_labels, 5))
            elif not is_crib:
                total_points += 4
                breakdown.append(("Flush (4)", all_labels[:-1], 4))

    # 5) His Nobs
    starter_suit = suits[-1]
    for l in labels:
        r, s = _parse_label(l)
        if r == 'jack' and s == starter_suit:
            total_points += 1
            breakdown.append(("His Nobs", [l], 1))
            break
            
    return total_points, breakdown

def draw_starter_from_deck(in_play_labels):
    ranks = ['ace','2','3','4','5','6','7','8','9','10','jack','queen','king']
    suits = ['clubs','diamonds','hearts','spades']
    deck = [f"{r} of {s}" for r in ranks for s in suits]
    in_play_set = set(in_play_labels)
    deck = [c for c in deck if c not in in_play_set]
    random.shuffle(deck)
    return deck.pop(), deck

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

def load_card_images():
    card_images = {}
    suits = ['clubs', 'diamonds', 'hearts', 'spades']
    ranks = ['ace', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king']

    cards_dir = os.path.join(os.path.dirname(__file__), 'assets', 'cards')

    # Load real PNG assets if they exist; fall back to simple generated faces.
    font_small = pygame.font.SysFont('arial', 18)
    font_big = pygame.font.SysFont('arial', 28, bold=True)

    for suit in suits:
        for rank in ranks:
            key = f"{rank}_of_{suit}"
            png_path = os.path.join(cards_dir, f"{key}.png")
            if os.path.exists(png_path):
                img = pygame.image.load(png_path).convert_alpha()
                card_images[key] = img
                continue

            # Fallback (keeps game playable if an asset is missing)
            surf = pygame.Surface((CARD_WIDTH, CARD_HEIGHT))
            surf.fill((255, 255, 255))
            pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 2)
            is_red = suit in ('hearts', 'diamonds')
            color = (180, 0, 0) if is_red else (0, 0, 0)
            rank_text = {'ace': 'A', 'jack': 'J', 'queen': 'Q', 'king': 'K'}.get(rank, rank)
            suit_text = {'clubs': 'C', 'diamonds': 'D', 'hearts': 'H', 'spades': 'S'}[suit]
            corner = font_small.render(f"{rank_text}{suit_text}", True, color)
            surf.blit(corner, (8, 6))
            corner2 = pygame.transform.rotate(corner, 180)
            surf.blit(corner2, (CARD_WIDTH - corner2.get_width() - 8, CARD_HEIGHT - corner2.get_height() - 6))
            center = font_big.render(f"{rank_text}{suit_text}", True, color)
            surf.blit(center, (CARD_WIDTH // 2 - center.get_width() // 2, CARD_HEIGHT // 2 - center.get_height() // 2))
            card_images[key] = surf

    return card_images

def fixed_hand_positions(player, n, screen_width):
    margin = 60
    available_width = screen_width - 2 * margin
    if n <= 1:
        spacing = 0
    else:
        spacing = (available_width - CARD_WIDTH) // (n - 1)
        spacing = max(10, min(spacing, CARD_WIDTH + 20))
    y = 600 if player == 1 else 50
    return [(margin + i * spacing, y) for i in range(n)]


def _labels_to_key(label: str) -> str:
    rank, suit = _parse_label(label)
    return f"{rank}_of_{suit}" if suit else rank


def _key_to_label(key: str) -> str:
    if '_of_' in key:
        rank, suit = key.split('_of_', 1)
        return f"{rank} of {suit}"
    return key.replace('_', ' ')


def _hand_has_legal_play(hand, current_total):
    return any(current_total + CardValueHelper.get_val(c.label) <= 31 for c in hand)


def _peg_points_for_play(sequence):
    """Compute pegging points caused by the latest card in sequence."""
    if not sequence:
        return 0, []

    points = 0
    reasons = []
    total = sum(CardValueHelper.get_val(c.label) for c in sequence)
    if total == 15:
        points += 2
        reasons.append("15 for 2")
    if total == 31:
        points += 2
        reasons.append("31 for 2")

    # Pairs/triples/quads from the end
    last_rank, _ = _parse_label(sequence[-1].label)
    same = 1
    for c in reversed(sequence[:-1]):
        r, _ = _parse_label(c.label)
        if r == last_rank:
            same += 1
        else:
            break
    if same == 2:
        points += 2
        reasons.append("Pair for 2")
    elif same == 3:
        points += 6
        reasons.append("Three of a kind for 6")
    elif same >= 4:
        points += 12
        reasons.append("Four of a kind for 12")

    # Runs from the end (find longest run length >= 3)
    max_run = 0
    for run_len in range(min(7, len(sequence)), 2, -1):
        window = sequence[-run_len:]
        nums = [_rank_index(_parse_label(c.label)[0]) for c in window]
        if len(set(nums)) != run_len:
            continue
        nums_sorted = sorted(nums)
        if nums_sorted[-1] - nums_sorted[0] == run_len - 1:
            max_run = run_len
            break
    if max_run:
        points += max_run
        reasons.append(f"Run of {max_run}")

    return points, reasons

def handle_discard(event):
    global selected_cards, player1_hand, player2_hand, crib, game_phase, message, player_turn
    global pegging_pile, starter_label, starter_sprite, counting_done, counting_step
    global last_player_to_play, passes_in_row, deck_keys, player1_kept_labels, player2_kept_labels
    global player_scores
    if event.type == pygame.MOUSEBUTTONDOWN:
        for idx, card in enumerate(player1_hand):
            if card.rect.collidepoint(event.pos) and idx not in selected_cards:
                selected_cards.append(idx)
                if len(selected_cards) == 2:
                    for i in sorted(selected_cards, reverse=True):
                        crib.append(player1_hand.pop(i))
                    # Dad discards
                    dad_discards = random.sample(range(len(player2_hand)), 2)
                    for i in sorted(dad_discards, reverse=True):
                        crib.append(player2_hand.pop(i))

                    # Save kept hands for the counting phase BEFORE pegging consumes them.
                    player1_kept_labels = [c.label for c in player1_hand]
                    player2_kept_labels = [c.label for c in player2_hand]

                    # Cut starter from remaining deck.
                    if deck_keys:
                        starter_key = deck_keys.pop()
                        starter_label = _key_to_label(starter_key)
                        starter_sprite = CardSprite(card_images_global[starter_key], (0, 0), starter_label)
                        # His heels: if starter is a Jack, dealer scores 2.
                        r, _ = _parse_label(starter_label)
                        if r == 'jack':
                            player_scores[dealer] += 2
                            who = player_name if dealer == 0 else "Dad"
                            message = f"His heels! {who} scores 2. Pegging begins!"
                        else:
                            message = "Pegging phase begins!"
                    else:
                        starter_label = None
                        starter_sprite = None
                        message = "Pegging phase begins!"

                    selected_cards = []
                    game_phase = 'pegging'
                    player_turn = 1 - dealer
                    pegging_pile = []
                    counting_done = False
                    counting_step = 0
                    last_player_to_play = None
                    passes_in_row = 0
                break

def handle_pegging(event=None):
    global player1_hand, player2_hand, pegging_pile, player_turn, message, game_phase
    global player_scores, last_player_to_play, passes_in_row
    current_total = sum(CardValueHelper.get_val(c.label) for c in pegging_pile)

    # Auto-pass if current player has no legal move.
    if player_turn == 0 and not _hand_has_legal_play(player1_hand, current_total):
        passes_in_row += 1
        player_turn = 1
    elif player_turn == 1 and not _hand_has_legal_play(player2_hand, current_total):
        passes_in_row += 1
        player_turn = 0

    if player_turn == 0:  # Player
        if event is not None and event.type == pygame.MOUSEBUTTONDOWN:
            for idx, card in enumerate(player1_hand):
                val = CardValueHelper.get_val(card.label)
                if card.rect.collidepoint(event.pos) and current_total + val <= 31:
                    pegging_pile.append(player1_hand.pop(idx))
                    last_player_to_play = 0
                    passes_in_row = 0

                    pts, reasons = _peg_points_for_play(pegging_pile)
                    if pts:
                        player_scores[0] += pts
                        message = f"{player_name} scores {pts}: {', '.join(reasons)}"
                    else:
                        message = "Dad's turn."

                    player_turn = 1
                    break
    else:  # Dad (Simple AI)
        if event is None:
            legal_moves = [
                i
                for i, c in enumerate(player2_hand)
                if current_total + CardValueHelper.get_val(c.label) <= 31
            ]
            if legal_moves:
                pegging_pile.append(player2_hand.pop(legal_moves[0]))
                last_player_to_play = 1
                passes_in_row = 0

                pts, reasons = _peg_points_for_play(pegging_pile)
                if pts:
                    player_scores[1] += pts
                    message = f"Dad scores {pts}: {', '.join(reasons)}"
                else:
                    message = f"{player_name}'s turn."

                player_turn = 0
            else:
                player_turn = 0  # Pass

    current_total = sum(CardValueHelper.get_val(c.label) for c in pegging_pile)

    # If both players have passed, award 1 point for "go" to last player who laid a card,
    # then reset the count (new pegging stack).
    if passes_in_row >= 2:
        if last_player_to_play is not None and current_total != 31:
            player_scores[last_player_to_play] += 1
            who = player_name if last_player_to_play == 0 else "Dad"
            message = f"{who} scores 1 for go."
        pegging_pile = []
        passes_in_row = 0
        current_total = 0

    # If we hit 31 exactly, reset the count automatically.
    if current_total == 31:
        pegging_pile = []
        current_total = 0

    # End pegging when both hands are empty.
    if not player1_hand and not player2_hand:
        # Last card (if not 31) scores 1.
        if pegging_pile:
            current_total = sum(CardValueHelper.get_val(c.label) for c in pegging_pile)
            if current_total not in (0, 31) and last_player_to_play is not None:
                player_scores[last_player_to_play] += 1
                who = player_name if last_player_to_play == 0 else "Dad"
                message = f"{who} scores 1 for last card. Counting hands..."
            else:
                message = "Counting hands..."
        else:
            message = "Counting hands..."
        game_phase = 'counting'
        return

    if not any(
        current_total + CardValueHelper.get_val(c.label) <= 31
        for c in (player1_hand + player2_hand)
    ):
        # If nobody can play but we didn't already process passes, treat as go.
        passes_in_row = max(passes_in_row, 2)


def _deal_new_round(card_images):
    global dealer, crib, selected_cards, player1_hand, player2_hand, pegging_pile
    global game_phase, player_turn, message, starter_label, starter_sprite, counting_done, counting_step
    global last_player_to_play, passes_in_row, deck_keys, player1_kept_labels, player2_kept_labels

    crib = []
    selected_cards = []
    pegging_pile = []
    starter_label = None
    starter_sprite = None
    counting_done = False
    counting_step = 0
    last_player_to_play = None
    passes_in_row = 0
    player1_kept_labels = []
    player2_kept_labels = []

    deck_keys = list(card_images.keys())
    random.shuffle(deck_keys)

    player1_hand = []
    player2_hand = []
    for _ in range(6):
        k = deck_keys.pop()
        player1_hand.append(CardSprite(card_images[k], (0, 0), _key_to_label(k)))
    for _ in range(6):
        k = deck_keys.pop()
        player2_hand.append(CardSprite(card_images[k], (0, 0), _key_to_label(k)))

    game_phase = 'discard'
    player_turn = 0
    message = "Select 2 cards to discard to the crib."


def _advance_counting_step():
    global counting_done, counting_step, message
    global player_scores, dealer, crib, starter_label
    global player1_kept_labels, player2_kept_labels

    if starter_label is None:
        message = "Missing starter card. Click to deal next hand."
        counting_done = True
        return

    non_dealer = 1 - dealer

    if counting_step == 0:
        message = "Click to score non-dealer hand."
        counting_step = 1
        return

    if counting_step == 1:
        labels = player1_kept_labels if non_dealer == 0 else player2_kept_labels
        pts, _ = score_hand_labels(labels, starter_label, is_crib=False)
        player_scores[non_dealer] += pts
        who = player_name if non_dealer == 0 else "Dad"
        message = f"{who} scores {pts} for hand. Click to score dealer hand."
        counting_step = 2
        return

    if counting_step == 2:
        labels = player1_kept_labels if dealer == 0 else player2_kept_labels
        pts, _ = score_hand_labels(labels, starter_label, is_crib=False)
        player_scores[dealer] += pts
        who = player_name if dealer == 0 else "Dad"
        message = f"{who} scores {pts} for hand. Click to score crib."
        counting_step = 3
        return

    if counting_step == 3:
        if len(crib) == 4:
            pts, _ = score_hand_labels([c.label for c in crib], starter_label, is_crib=True)
            player_scores[dealer] += pts
            who = player_name if dealer == 0 else "Dad"
            message = f"{who} scores {pts} in the crib. Click to deal next hand."
        else:
            message = "Click to deal next hand."
        counting_done = True
        counting_step = 4
        return
        
def main():
    global message, dealer, player1_hand, player2_hand, game_phase, player_name
    global starter_sprite
    pygame.init()
    screen = pygame.display.set_mode((1280, 900), pygame.RESIZABLE)
    clock = pygame.time.Clock()
    card_images = load_card_images()
    global card_images_global
    card_images_global = card_images
    
    player_name = get_player_name(screen)

    _deal_new_round(card_images)

    running = True
    table_bg = None
    table_path = os.path.join(os.path.dirname(__file__), 'assets', 'table.jpg')
    if os.path.exists(table_path):
        table_bg = pygame.image.load(table_path).convert()

    while running:
        if table_bg is not None:
            screen.blit(pygame.transform.smoothscale(table_bg, screen.get_size()), (0, 0))
        else:
            screen.fill(TABLE_COLOR)
        sw = screen.get_width()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if game_phase == 'discard':
                handle_discard(event)
            elif game_phase == 'pegging':
                handle_pegging(event)
            elif game_phase == 'counting':
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if not counting_done:
                        _advance_counting_step()
                    else:
                        dealer = 1 - dealer
                        _deal_new_round(card_images)

        if game_phase == 'pegging' and player_turn == 1:
            handle_pegging(None)

        if game_phase == 'counting' and not counting_done and counting_step == 0:
            _advance_counting_step()

        # Update Positions
        p1_pos = fixed_hand_positions(1, len(player1_hand), sw)
        for i, card in enumerate(player1_hand):
            card.rect.topleft = p1_pos[i]
            card.draw(screen)
            
        p2_pos = fixed_hand_positions(2, len(player2_hand), sw)
        for i, card in enumerate(player2_hand):
            card.rect.topleft = p2_pos[i]
            # Draw back of card for Dad
            pygame.draw.rect(screen, (50, 50, 50), card.rect)
            pygame.draw.rect(screen, (0, 0, 0), card.rect, 2)

        for i, card in enumerate(pegging_pile):
            card.rect.topleft = (400 + i*30, 300)
            card.draw(screen)

        if starter_sprite is not None:
            starter_sprite.rect.topleft = (sw // 2 - CARD_WIDTH // 2, 200)
            starter_sprite.draw(screen)

        # UI Text
        font = pygame.font.SysFont('arial', 24)
        msg_surf = font.render(message, True, (255, 255, 255))
        screen.blit(msg_surf, (sw//2 - msg_surf.get_width()//2, 450))

        score_surf = font.render(f"{player_name}: {player_scores[0]}    Dad: {player_scores[1]}    Dealer: {'Player' if dealer == 0 else 'Dad'}", True, (255, 255, 255))
        screen.blit(score_surf, (20, 10))

        if game_phase == 'pegging':
            total = sum(CardValueHelper.get_val(c.label) for c in pegging_pile)
            t_surf = font.render(f"Pegging total: {total}", True, (255, 255, 255))
            screen.blit(t_surf, (20, 40))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()