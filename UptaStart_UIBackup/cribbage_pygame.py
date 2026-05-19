import pygame
pygame.init()
pygame.font.init()
import os
import sys
import random
import pygame_menu

# --- CONFIG ---
CARD_WIDTH, CARD_HEIGHT = 100, 145
TABLE_COLOR = (34, 139, 34)  # Felt green
FPS = 60

# --- ASSET PATHS ---
CARD_FOLDER = os.path.join(os.path.dirname(__file__), 'assets', 'cards')
BACKGROUND_IMG = os.path.join(os.path.dirname(__file__), 'assets', 'table.png')

# --- CARD LOADING ---
def load_card_images():
    card_images = {}
    suits = ['clubs', 'diamonds', 'hearts', 'spades']
    ranks = ['ace', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king']
    for suit in suits:
        for rank in ranks:
            filename = f"{rank}_of_{suit}.png"
            path = os.path.join(CARD_FOLDER, filename)
            if os.path.exists(path):
                image = pygame.image.load(path)
                card_images[f"{rank}_{suit}"] = image
            else:
                # Placeholder rectangle if image missing
                surf = pygame.Surface((CARD_WIDTH, CARD_HEIGHT))
                surf.fill((200, 200, 200))
                pygame.draw.rect(surf, (0,0,0), surf.get_rect(), 2)
                card_images[f"{rank}_{suit}"] = surf
    return card_images

# --- CARD CLASS ---
class CardSprite(pygame.sprite.Sprite):
    def __init__(self, image, pos, label):
        super().__init__()
        self.image = pygame.transform.smoothscale(image, (CARD_WIDTH, CARD_HEIGHT))
        self.rect = self.image.get_rect(topleft=pos)
        self.dragging = False
        self.label = label

    def update(self, mouse_pos):
        if self.dragging:
            self.rect.center = mouse_pos

    def draw(self, surface):
        surface.blit(self.image, self.rect)
        # Removed card value label overlay

# --- MAIN GAME ---
def main():
    # --- PLAYER NAME ENTRY ---
    player_name = "Player 1"
    def get_player_name(screen):
        import pygame_menu
        from pygame_menu import themes
        import pygame
        # Draw gradient background: mostly white, gold accent at bottom
        menu_width, menu_height = 500, 260
        for y in range(menu_height):
            # White to gold gradient (white dominates)
            r = 255
            g = 255 - int(40 * y / menu_height)
            b = 255 - int(55 * y / menu_height)
            pygame.draw.line(screen, (r, g, b), (0, y), (menu_width, y))
        custom_theme = themes.Theme(
            background_color=(255,255,255),  # White dominant
            title_background_color=(0, 51, 160),  # Rhode Island blue
            title_font=pygame_menu.font.FONT_COMIC_NEUE,  # Cutesy/friendly font
            title_font_size=48,
            widget_font=pygame_menu.font.FONT_COMIC_NEUE,
            widget_font_size=28,
            widget_border_width=0,
            widget_border_color=(0, 51, 160),
            selection_color=(0, 51, 160),
            title_font_color=(255,215,0),  # Gold accent for title text
            widget_font_color=(0, 51, 160),
            widget_background_color=(255,255,255),
            widget_margin=(0, 16),
            title_close_button=True,
        )
        menu = pygame_menu.Menu('Enter Your Name', menu_width, menu_height, theme=custom_theme)
        name_input = menu.add.text_input('Name: ', default='', maxchar=16, textinput_id='player_name', font_name=pygame_menu.font.FONT_MUNRO, font_size=30)
        menu_done = [False]
        def close_menu():
            menu_done[0] = True
        menu.add.button('Start Game', close_menu, button_id='start_btn', font_name=pygame_menu.font.FONT_MUNRO, font_size=28)
        print("DEBUG: Before menu.mainloop")
        while not menu_done[0]:
            events = pygame.event.get()
            menu.update(events)
            menu.draw(screen)
            pygame.display.flip()
        print("DEBUG: After menu.mainloop")
        result = name_input.get_value().strip() if name_input.get_value().strip() else "Challenger"
        print(f"DEBUG: get_player_name returning: {result}")
        return result
    # --- SCREEN INITIALIZATION ---
    screen = pygame.display.set_mode((1100, 700))
    pygame.display.set_caption("Cribbage Game")
    # Prompt for player name after screen is initialized
    try:
        player_name = get_player_name(screen)
        print(f"DEBUG: Name entered: {player_name}")
    except Exception as e:
        import traceback
        print('ERROR during name entry:', e)
        traceback.print_exc()
        raise
    print("DEBUG: Proceeding to main game loop initialization.")

    # --- MOUSE POSITION INITIALIZATION ---
    mouse_pos = pygame.mouse.get_pos()

    # --- GAME STATE MANAGEMENT (initialize at top) ---
    GAME_PHASES = ['discard', 'pegging', 'counting', 'end']
    game_phase = 'discard'
    dealer = 0  # 0 for Player 1, 1 for Dad
    crib = []
    selected_cards = []
    message = "Select 2 cards to discard to the crib."
    show_computer_hand = False
    pegging_pile = []
    pegging_scores = [0, 0]
    player_turn = 0
    pegging_turn = 0
    player_scores = [0, 0]

    # --- TUTORIAL/HELP BUTTON ---
    show_tutorial = False
    tutorial_text = [
        "Welcome to Cribbage!",
        "How to Play:",
        "- Each player is dealt 6 cards. Dealer alternates each round.",
        "- Discard Phase: Select 2 cards to discard to the crib (shared pot).",
        "- Pegging Phase: Play cards in turn, aiming for 15, 31, pairs, and runs.",
        "- Counting Phase: Points are scored for hands and crib.",
        "- First to 121 points wins.",
        "Scoring:",
        "- 15 or 31: 2 points.",
        "- Pairs, runs, and combinations: see rules for details.",
        "- Crib points go to the dealer.",
        "Controls:",
        "- Click cards to select/play.",
        "- '?' button: Show this help overlay.",
        "- R: Restart round.",
        "- H: Show help.",
        "- U: Undo last move.",
        "- S: Show/hide crib."
    ]

    def get_move_options():
        if game_phase == 'discard':
            return [
                "Discard Phase:",
                "- Select 2 cards to discard to the crib.",
                "- Click a card to select, click again to confirm.",
                "- After discarding, computer will discard automatically."
            ]
        elif game_phase == 'pegging':
            if player_turn == 0:
                return [
                    "Pegging Phase:",
                    "- Your turn: Select a card to play.",
                    "- Try to make totals of 15 or 31, pairs, or runs for points.",
                    "- Legal moves are highlighted in green."
                ]
            else:
                return [
                    "Pegging Phase:",
                    "- Dad's turn: Wait for computer to play.",
                    "- Watch for scoring popups."
                ]
        elif game_phase == 'counting':
            return [
                "Counting Phase:",
                "- Points are scored for hands and crib.",
                "- Wait for scores to be displayed."
            ]
        elif game_phase == 'end':
            return [
                "End of Round:",
                "- Press R to start a new round.",
                "- Dealer alternates each round."
            ]
        return ["Game in progress."]

    # --- TOOLTIP STATE ---
    tooltip = ""

    # --- UNDO/REDO STATE ---
    undo_stack = []
    redo_stack = []

    # --- SHOW/HIDE CRIB OPTION ---
    show_crib = False

    def draw_contrast_message(text, x, y, max_width=800, font_size=32, color=(34,139,34), border_radius=12):
        # Word wrap and dynamic font sizing
        def simple_wrap(text, font, max_width):
            words = text.split(' ')
            lines = []
            current = ''
            for word in words:
                test = current + (' ' if current else '') + word
                if font.size(test)[0] > max_width:
                    if current:
                        lines.append(current)
                    current = word
                else:
                    current = test
            if current:
                lines.append(current)
            return lines
        while True:
            camping_font = pygame.font.SysFont('papyrus,comic sans ms,arial', font_size, bold=True)
            wrapped_message = simple_wrap(text, camping_font, max_width)
            total_height = len(wrapped_message) * (font_size + 4)
            if total_height <= int(len(wrapped_message) * (font_size + 4) * 1.1):
                break
            font_size -= 2
            if font_size < 18:
                break
        font_size = int(font_size * 0.85)
        camping_font = pygame.font.SysFont('papyrus,comic sans ms,arial', font_size, bold=True)
        bg_height = int(len(wrapped_message) * (font_size + 4) * 1.1)
        bg_rect = pygame.Rect(x, y, max_width + 20, bg_height)
        big_rect_margin = int(bg_rect.width * 0.1)
        big_rect_height_margin = int(bg_rect.height * 0.1)
        if len(wrapped_message) > 3 or any(len(line) > 80 for line in wrapped_message):
            big_rect_margin = int(bg_rect.width * 0.18)
            big_rect_height_margin = int(bg_rect.height * 0.18)
        big_rect = pygame.Rect(bg_rect.x - big_rect_margin, bg_rect.y - big_rect_height_margin,
                              bg_rect.width + 2 * big_rect_margin, bg_rect.height + 2 * big_rect_height_margin)
        pygame.draw.rect(screen, (0,0,0), big_rect, border_radius=border_radius+6)
        pygame.draw.rect(screen, (0,0,0), bg_rect, border_radius=border_radius)
        for i, line in enumerate(wrapped_message):
            screen.blit(camping_font.render(line, True, color), (x+10, y+10 + i*(font_size + 4)))

    # Draw phase indicator with contrast layer
    phase_text = f"Phase: {game_phase.title()}"
    draw_contrast_message(phase_text, screen.get_width()//2 - 120, 10, max_width=400, font_size=36, color=(0,128,255), border_radius=16)

    # Draw dealer/turn display with contrast layer
    dealer_text = f"Dealer: {player_name if dealer==0 else 'Dad'}"
    turn_text = f"Turn: {player_name if player_turn==0 else 'Dad'}"
    player_color = (255, 97, 0)  # Hunter orange
    draw_contrast_message(dealer_text, 30, screen.get_height()-90, max_width=350, font_size=28, color=player_color if dealer==0 else (255,0,128), border_radius=14)
    draw_contrast_message(turn_text, 30, screen.get_height()-50, max_width=350, font_size=28, color=player_color if player_turn==0 else (255,0,128), border_radius=14)

    # Draw help button
    help_rect = pygame.Rect(screen.get_width()-70, 20, 50, 50)
    pygame.draw.rect(screen, (200,200,255), help_rect, border_radius=25)
    help_font = pygame.font.SysFont('arial', 40, bold=True)
    screen.blit(help_font.render("?", True, (0,0,128)), (help_rect.x+10, help_rect.y+2))
    if help_rect.collidepoint(mouse_pos):
        tooltip = "Show tutorial/help"

    # Keyboard shortcuts (move outside help button logic)
    keys = pygame.key.get_pressed()
    if keys[pygame.K_r]:
        reset_round()
    if keys[pygame.K_h]:
        show_tutorial = not show_tutorial
    if keys[pygame.K_u] and undo_stack:
        # Undo last move
        state = undo_stack.pop()
        redo_stack.append((player1_hand[:], player2_hand[:], crib[:], pegging_pile[:], player_scores[:]))
        player1_hand, player2_hand, crib, pegging_pile, player_scores = state
    if keys[pygame.K_s]:
        show_crib = not show_crib

    # Draw tutorial/help overlay if active
    if show_tutorial:
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0,0,0,200))
        screen.blit(overlay, (0,0))
        tut_font = pygame.font.SysFont('comicneue,papyrus,comic sans ms,arial', 36, bold=True)
        y_start = 80
        for i, line in enumerate(tutorial_text):
            screen.blit(tut_font.render(line, True, (255,255,255)), (80, y_start + i*38))

        # Draw current move options below tutorial
        move_font = pygame.font.SysFont('comicneue,papyrus,comic sans ms,arial', 32, bold=True)
        move_options = get_move_options()
        y_move = y_start + len(tutorial_text)*38 + 30
        for i, line in enumerate(move_options):
            screen.blit(move_font.render(line, True, (255,255,180)), (100, y_move + i*34))

        # Draw dismiss instruction
        dismiss_font = pygame.font.SysFont('comicneue,papyrus,comic sans ms,arial', 28, bold=True)
        screen.blit(dismiss_font.render("Click '?' or press H to close help.", True, (255,200,200)), (100, y_move + len(move_options)*34 + 20))

    # Draw tooltip if set
    if tooltip:
        tip_font = pygame.font.SysFont('arial', 24)
        tip_rect = pygame.Rect(mouse_pos[0]+10, mouse_pos[1]+10, 220, 32)
        pygame.draw.rect(screen, (255,255,200), tip_rect, border_radius=8)
        screen.blit(tip_font.render(tooltip, True, (0,0,0)), (tip_rect.x+8, tip_rect.y+4))

    # Draw show/hide crib button
    crib_btn_rect = pygame.Rect(screen.get_width()-170, 20, 80, 50)
    pygame.draw.rect(screen, (200,255,200), crib_btn_rect, border_radius=15)
    crib_btn_font = pygame.font.SysFont('arial', 24, bold=True)
    crib_btn_label = "Show Crib" if not show_crib else "Hide Crib"
    screen.blit(crib_btn_font.render(crib_btn_label, True, (0,128,0)), (crib_btn_rect.x+8, crib_btn_rect.y+12))
    if crib_btn_rect.collidepoint(mouse_pos):
        tooltip = "Toggle crib card visibility"

    # Draw crib as hidden cards in upper left corner or reveal if toggled
    for i, card in enumerate(crib):
        if show_crib:
            card.draw(screen)
        else:
            back = pygame.Surface((CARD_WIDTH, CARD_HEIGHT))
            back.fill((100, 100, 100))
            pygame.draw.rect(back, (0,0,0), back.get_rect(), 2)
            screen.blit(back, (30 + i*30, 30))

    # Sound effects for actions (deal, score, win, error)
    if not hasattr(main, 'score_sound'):
        try:
            main.score_sound = pygame.mixer.Sound(os.path.join(os.path.dirname(__file__), 'assets', 'score.wav'))
        except:
            main.score_sound = None
    if hasattr(main, 'last_scores'):
        if player_scores != main.last_scores and main.score_sound:
            main.score_sound.play()
    main.last_scores = list(player_scores)

    # Keyboard shortcuts
    keys = pygame.key.get_pressed()
    if keys[pygame.K_r]:
        reset_round()
    if keys[pygame.K_h]:
        show_tutorial = not show_tutorial
    if keys[pygame.K_u] and undo_stack:
        # Undo last move
        state = undo_stack.pop()
        redo_stack.append((player1_hand[:], player2_hand[:], crib[:], pegging_pile[:], player_scores[:]))
        player1_hand, player2_hand, crib, pegging_pile, player_scores = state
    if keys[pygame.K_s]:
        show_crib = not show_crib

    # Mouse click handling for help and crib buttons
    if pygame.mouse.get_pressed()[0]:
        if help_rect.collidepoint(mouse_pos):
            show_tutorial = not show_tutorial
        if crib_btn_rect.collidepoint(mouse_pos):
            show_crib = not show_crib
            if crib_btn_rect.collidepoint(mouse_pos):
                show_crib = not show_crib
    # Animated scoring feedback state
    score_popups = []  # List of (score, position, timer)

    pygame.init()
    pygame.font.init()
    screen = pygame.display.set_mode((1800, 1200))  # Enlarged table and board
    pygame.display.set_caption("Cribbage - Intricate Styled Table")
    clock = pygame.time.Clock()

    # Load background
    background = None
    for bg_file in [BACKGROUND_IMG, os.path.join(os.path.dirname(__file__), 'assets', 'table.jpg')]:
        if os.path.exists(bg_file):
            try:
                background = pygame.image.load(bg_file)
                background = pygame.transform.smoothscale(background, screen.get_size())
                break
            except pygame.error:
                continue
    if background is None:
        background = pygame.Surface(screen.get_size())
        background.fill(TABLE_COLOR)

    # Load cards
    card_images = load_card_images()

    # Deal sample hands
    keys = list(card_images.keys())
    random.shuffle(keys)
    def fixed_hand_positions(player, n):
        y = 500 if player == 1 else 100  # Ensure player 1's cards are visible
        return [(300 + i*220, y) for i in range(n)]
    player1_hand = [CardSprite(card_images[keys[i]], fixed_hand_positions(1,6)[i], keys[i].replace('_', ' of ')) for i in range(6)]
    player2_hand = [CardSprite(card_images[keys[i+6]], fixed_hand_positions(2,6)[i], keys[i+6].replace('_', ' of ')) for i in range(6)]

    sprites = player1_hand + player2_hand

    dragging_card = None

    # Track which player's turn it is
    player_turn = 1  # Start with computer (Dad) as dealer
    pegging_turn = 1

    # Use only the board.jpg image for the board
    def load_board_image(board_file):
        path = os.path.join(os.path.dirname(__file__), 'assets', board_file)
        if os.path.exists(path):
            try:
                img = pygame.image.load(path)
                return pygame.transform.smoothscale(img, (600, 100))
            except pygame.error:
                return None
        return None
    board_img = load_board_image('board.jpg')

    # Board scaling and peg positions
    board_scale = 1.5
    board_rect = pygame.Rect(200, 400, int(1200 * board_scale), int(200 * board_scale))  # Enlarged area inside table for board
    peg_radius = int(10 * board_scale)
    peg_path = []
    # Generate 121 evenly spaced peg positions along the board
    for i in range(121):
        x = board_rect.left + int((board_rect.width - 2 * peg_radius) * i / 120) + peg_radius
        y = board_rect.centery
        peg_path.append((x, y))

    def get_peg_position(score):
        return peg_path[min(score, 120)]

    # Scoring system
    player_scores = [0, 0]  # Player 1, Player 2
    max_score = 121  # Standard cribbage board
    def enforce_score_limits():
        player_scores[0] = min(player_scores[0], max_score)
        player_scores[1] = min(player_scores[1], max_score)

    # Difficulty selection
    DIFFICULTY_LEVELS = ['Easy', 'Medium', 'Hard']
    selected_difficulty = 0

    def show_difficulty_menu():
        nonlocal selected_difficulty
        running = True
        while running:
            screen.fill((30, 30, 30))
            font = pygame.font.SysFont('arial', 40, bold=True)
            screen.blit(font.render('Select Computer Difficulty', True, (255,255,255)), (180, 120))
            for i, level in enumerate(DIFFICULTY_LEVELS):
                color = (255,255,0) if i == selected_difficulty else (200,200,200)
                screen.blit(font.render(level, True, color), (350, 200 + i*60))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        selected_difficulty = (selected_difficulty - 1) % len(DIFFICULTY_LEVELS)
                    elif event.key == pygame.K_DOWN:
                        selected_difficulty = (selected_difficulty + 1) % len(DIFFICULTY_LEVELS)
                    elif event.key == pygame.K_RETURN:
                        running = False
    show_difficulty_menu()

    # Computer opponent logic
    def computer_move_easy(hand):
        # Random legal move (placeholder)
        import random
        if hand:
            return hand[random.randint(0, len(hand)-1)]
        return None

    def computer_move_medium(hand):
        # Basic strategy: play lowest card
        if hand:
            return min(hand, key=lambda card: card.value())
        return None

    def computer_move_hard(hand, player_hand=None):
        # Perfect technique: evaluate all legal moves and pick the one with highest immediate score
        import cards
        def normalize_rank(rank):
            rank = rank.lower()
            if rank == 'ace': return 'A'
            if rank == 'jack': return 'J'
            if rank == 'queen': return 'Q'
            if rank == 'king': return 'K'
            return rank if rank.isdigit() else rank.title()
        def normalize_suit(suit):
            return suit.title()
        best_score = -1
        best_card = None
        for card in hand:
            # Simulate playing this card
            pile = [c for c in hand if c != card]
            pile_total = 0
            # Use pegging_pile from outer scope if available
            try:
                from inspect import currentframe
                frame = currentframe().f_back
                pegging_pile = frame.f_locals.get('pegging_pile', [])
            except:
                pegging_pile = []
            pile_total = sum(cards.Card(normalize_rank(c.label.split(' of ')[0]), normalize_suit(c.label.split(' of ')[1])).value() for c in pegging_pile)
            card_value = cards.Card(normalize_rank(card.label.split(' of ')[0]), normalize_suit(card.label.split(' of ')[1])).value()
            total = pile_total + card_value
            score = 0
            if total == 15:
                score += 2
            if total == 31:
                score += 2
            pile_cards = [cards.Card(c.label.split(' of ')[0], c.label.split(' of ')[1]) for c in pegging_pile[-3:]] + [cards.Card(card.label.split(' of ')[0], card.label.split(' of ')[1])]
            score += cards.score_pairs(pile_cards)
            score += cards.score_runs(pile_cards)
            if score > best_score:
                best_score = score
                best_card = card
        if best_card:
            return best_card
        # Fallback: play lowest card
        if hand:
            return min(hand, key=lambda card: card.value())
        return None

    def computer_play(hand, player_hand=None):
        if DIFFICULTY_LEVELS[selected_difficulty] == 'Easy':
            return computer_move_easy(hand)
        elif DIFFICULTY_LEVELS[selected_difficulty] == 'Medium':
            return computer_move_medium(hand)
        else:
            return computer_move_hard(hand, player_hand)

    computer_player_name = "Dad"

    # Load Dad character image
    dad_img_path = os.path.join(os.path.dirname(__file__), 'assets', 'dad.png')
    dad_img = None
    if os.path.exists(dad_img_path):
        try:
            dad_img = pygame.image.load(dad_img_path)
            dad_img = pygame.transform.smoothscale(dad_img, (64, 64))
        except pygame.error:
            dad_img = None

    # Load Tony character image
    tony_img_path = os.path.join(os.path.dirname(__file__), 'assets', 'tony.png')
    tony_img = None
    if os.path.exists(tony_img_path):
        try:
            tony_img = pygame.image.load(tony_img_path)
            tony_img = pygame.transform.smoothscale(tony_img, (64, 64))
        except pygame.error:
            tony_img = None

    # --- GAME STATE MANAGEMENT ---
    GAME_PHASES = ['discard', 'pegging', 'counting', 'end']
    game_phase = 'discard'
    dealer = 0  # 0 for Player 1, 1 for Dad
    crib = []
    selected_cards = []
    message = "Select 2 cards to discard to the crib."
    show_computer_hand = False

    def reset_round():
        nonlocal player1_hand, player2_hand, crib, selected_cards, game_phase, dealer, show_computer_hand, pegging_pile, pegging_scores, player_turn, pegging_turn, message
        keys = list(card_images.keys())
        random.shuffle(keys)
        player1_hand = [CardSprite(card_images[keys[i]], fixed_hand_positions(1,6)[i], keys[i].replace('_', ' of ')) for i in range(6)]
        player2_hand = [CardSprite(card_images[keys[i+6]], fixed_hand_positions(2,6)[i], keys[i+6].replace('_', ' of ')) for i in range(6)]
        crib = []
        selected_cards = []
        game_phase = 'discard'
        show_computer_hand = False
        pegging_pile = []
        pegging_scores = [0, 0]
        # Set starting player for pegging phase: non-dealer starts
        player_turn = 1 - dealer
        pegging_turn = 1 - dealer
    message = f"Dealer is {'Player 1' if dealer==0 else 'Dad'}. Select 2 cards to discard to the crib. First, click two cards in your hand to select them. Then, click either of those selected cards again to confirm and discard both."

    game_phase = 'discard'
    show_computer_hand = False
    pegging_pile = []
    pegging_scores = [0, 0]
    # Set starting player for pegging phase: non-dealer starts
    player_turn = 1 - dealer
    pegging_turn = 1 - dealer
    message = f"Dealer is {'Player 1' if dealer==0 else 'Dad'}. Select 2 cards to discard to the crib. Click two cards in your hand to discard."

    # --- COUNTING PHASE (auto scoring) ---
    def handle_counting():
        nonlocal game_phase, message, player_scores, dealer, player1_hand, player2_hand, crib, pegging_pile
        def normalize_rank(rank):
            rank = rank.lower()
            if rank == 'ace': return 'A'
            if rank == 'jack': return 'J'
            if rank == 'queen': return 'Q'
            if rank == 'king': return 'K'
            return rank if rank.isdigit() else rank.title()
        def normalize_suit(suit):
            return suit.title()
        # Score hands and crib using cards.py logic
        import cards
        # Assume starter card is top of deck (simulate)
        deck = cards.Deck()
        starter = deck.deal(1)[0]
        # Score player hands (only if 4 cards)
        p1_hand_cards = [cards.Card(normalize_rank(card.label.split(' of ')[0]), normalize_suit(card.label.split(' of ')[1])) for card in player1_hand]
        p2_hand_cards = [cards.Card(normalize_rank(card.label.split(' of ')[0]), normalize_suit(card.label.split(' of ')[1])) for card in player2_hand]
        crib_cards = [cards.Card(normalize_rank(card.label.split(' of ')[0]), normalize_suit(card.label.split(' of ')[1])) for card in crib]
        p1_score = cards.score_hand(p1_hand_cards[:4], starter) if len(p1_hand_cards) == 4 else 0
        p2_score = cards.score_hand(p2_hand_cards[:4], starter) if len(p2_hand_cards) == 4 else 0
        crib_score = cards.score_hand(crib_cards[:4], starter) if len(crib_cards) == 4 else 0
        # Award points
        player_scores[0] += p1_score
        player_scores[1] += p2_score
        # Crib goes to dealer
        player_scores[dealer] += crib_score
        enforce_score_limits()
        # Clear cards no longer in play (after scoring)
        player1_hand.clear()
        player2_hand.clear()
        crib.clear()
        pegging_pile.clear()
        game_phase = 'end'
        message = f"Round over. Starter: {starter}. P1: +{p1_score}, P2: +{p2_score}, Crib: +{crib_score} to {'Player 1' if dealer==0 else 'Dad'}. Press R to start new round."

    # --- DISCARD TO CRIB ---
    def handle_discard(event):
        nonlocal game_phase, message, selected_cards, crib, show_computer_hand, player_turn
        if event.type == pygame.MOUSEBUTTONDOWN and player_turn == 0 and game_phase == 'discard':
            if event.button == 1:  # Left click
                clicked_idx = None
                for idx, card in enumerate(player1_hand):
                    if card.rect.collidepoint(event.pos):
                        clicked_idx = idx
                        break
                if clicked_idx is not None:
                    if clicked_idx not in selected_cards and len(selected_cards) < 2:
                        selected_cards.append(clicked_idx)
                    elif clicked_idx in selected_cards:
                        # Allow unselecting any selected card
                        selected_cards.remove(clicked_idx)
                    # If two cards are selected and user clicks either again, discard both
                    if len(selected_cards) == 2 and clicked_idx in selected_cards:
                        for idx2 in sorted(selected_cards, reverse=True):
                            card2 = player1_hand.pop(idx2)
                            card2.image = pygame.Surface((CARD_WIDTH, CARD_HEIGHT))
                            card2.image.fill((100, 100, 100))
                            pygame.draw.rect(card2.image, (0,0,0), card2.image.get_rect(), 2)
                            crib.append(card2)
                        selected_cards.clear()
                        # Computer discards automatically
                        computer_discards = []
                        for _ in range(2):
                            idx2 = random.randint(0, len(player2_hand)-1)
                            computer_discards.append(player2_hand.pop(idx2))
                        for card2 in computer_discards:
                            card2.image = pygame.Surface((CARD_WIDTH, CARD_HEIGHT))
                            card2.image.fill((100, 100, 100))
                            pygame.draw.rect(card2.image, (0,0,0), card2.image.get_rect(), 2)
                            crib.append(card2)
                        game_phase = 'pegging'
                        show_computer_hand = False
                        player_turn = 1 - player_turn  # Switch to computer for pegging if needed
                        if player_turn == 0:
                            message = "Pegging phase: Your turn. Select a card to play."
                        else:
                            message = "Pegging phase: Dad's turn. Please wait for Dad to play."
                # Update message
                if len(selected_cards) < 2:
                    message = "Click to select up to two cards for discard. After selecting two, click either selected card again to confirm and discard both."
                elif len(selected_cards) == 2:
                    message = "Click either selected card again to confirm and discard both cards to the crib."
        elif game_phase == 'discard' and player_turn == 1:
            # Computer discards automatically
            computer_discards = []
            for _ in range(2):
                idx = random.randint(0, len(player2_hand)-1)
                computer_discards.append(player2_hand.pop(idx))
            for card in computer_discards:
                card.image = pygame.Surface((CARD_WIDTH, CARD_HEIGHT))
                card.image.fill((100, 100, 100))
                pygame.draw.rect(card.image, (0,0,0), card.image.get_rect(), 2)
                crib.append(card)
            player_turn = 0
            message = "Select two cards to discard to the crib by clicking them."

    # --- PEGGING PHASE (placeholder logic) ---
    pegging_pile = []
    pegging_scores = [0, 0]
    pegging_turn = 0  # 0 for Player 1, 1 for Dad
    def pegging_total():
        import cards
        def normalize_rank(rank):
            rank = rank.lower()
            if rank == 'ace': return 'A'
            if rank == 'jack': return 'J'
            if rank == 'queen': return 'Q'
            if rank == 'king': return 'K'
            return rank if rank.isdigit() else rank.title()
        def normalize_suit(suit):
            return suit.title()
        return sum(cards.Card(normalize_rank(card.label.split(' of ')[0]), normalize_suit(card.label.split(' of ')[1])).value() for card in pegging_pile)

    def normalize_rank(rank):
        rank = rank.lower()
        if rank == 'ace': return 'A'
        if rank == 'jack': return 'J'
        if rank == 'queen': return 'Q'
        if rank == 'king': return 'K'
        return rank if rank.isdigit() else rank.title()
    def normalize_suit(suit):
        return suit.title()
    def legal_pegging_moves(hand):
        import cards
        total = pegging_total()
        return [i for i, card in enumerate(hand) if total + cards.Card(normalize_rank(card.label.split(' of ')[0]), normalize_suit(card.label.split(' of ')[1])).value() <= 31]

    def handle_pegging(event):
        nonlocal pegging_turn, game_phase, message, player_scores, player_turn
        def normalize_rank(rank):
            rank = rank.lower()
            if rank == 'ace': return 'A'
            if rank == 'jack': return 'J'
            if rank == 'queen': return 'Q'
            if rank == 'king': return 'K'
            return rank if rank.isdigit() else rank.title()
        def normalize_suit(suit):
            return suit.title()
        if game_phase == 'pegging' and player_scores[0] < max_score and player_scores[1] < max_score:
            # Player 1's turn: allow manual pegging
            if pegging_turn == 0 and event.type == pygame.MOUSEBUTTONDOWN:
                legal_moves_p1 = legal_pegging_moves(player1_hand)
                for idx in legal_moves_p1:
                    card = player1_hand[idx]
                    if card.rect.collidepoint(event.pos):
                        pegging_pile.append(player1_hand.pop(idx))
                        import cards
                        total = pegging_total()
                        score_delta = 0
                        if total == 15:
                            score_delta += 2
                            message = "15 for 2! Dad's turn to peg."
                        elif total == 31:
                            score_delta += 2
                            message = "31 for 2! Dad's turn to peg."
                        pile_cards = [cards.Card(c.label.split(' of ')[0], c.label.split(' of ')[1]) for c in pegging_pile[-4:]]
                        pair_score = cards.score_pairs(pile_cards)
                        run_score = cards.score_runs(pile_cards)
                        score_delta += pair_score + run_score
                        player_scores[0] += score_delta
                        peg_pos = get_peg_position(player_scores[0])
                        if score_delta:
                            score_popups.append((f"+{score_delta}", peg_pos, 60))
                        message = message if score_delta else "Dad's turn to peg."
                        pegging_turn = 1
                        break
            # Dad's turn: automatic pegging
            elif pegging_turn == 1:
                legal_moves_p2 = legal_pegging_moves(player2_hand)
                if legal_moves_p2:
                    idx = legal_moves_p2[0]
                    pegging_pile.append(player2_hand.pop(idx))
                    import cards
                    total = pegging_total()
                    score_delta = 0
                    if total == 15:
                        score_delta += 2
                        message = "15 for 2! Your turn to peg."
                    elif total == 31:
                        score_delta += 2
                        message = "31 for 2! Your turn to peg."
                    pile_cards = [cards.Card(c.label.split(' of ')[0], c.label.split(' of ')[1]) for c in pegging_pile[-4:]]
                    pair_score = cards.score_pairs(pile_cards)
                    run_score = cards.score_runs(pile_cards)
                    score_delta += pair_score + run_score
                    player_scores[1] += score_delta
                    peg_pos = get_peg_position(player_scores[1])
                    if score_delta:
                        score_popups.append((f"+{score_delta}", peg_pos, 60))
                    message = message if score_delta else "Your turn to peg."
                    pegging_turn = 0
                else:
                    message = "You say Go!"
                    pegging_turn = 0
            # If no legal moves for either, advance to counting but do NOT clear hands yet
            if not legal_pegging_moves(player1_hand) and not legal_pegging_moves(player2_hand):
                game_phase = 'counting'

    # --- END OF GAME ---
    def handle_end(event):
        nonlocal game_phase, message, player_scores, dealer
        if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
            dealer = 1 - dealer  # Alternate dealer
            reset_round()
            # Keep scores between rounds
            message = f"Dealer is now {'Player 1' if dealer==0 else 'Dad'}. Select 2 cards to discard to the crib."

    # --- MAIN LOOP ---
    print("DEBUG: Entered main game loop.")
    while True:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            # Only handle discard events in discard phase
            if game_phase == 'discard':
                handle_discard(event)
            # Only handle pegging events in pegging phase
            elif game_phase == 'pegging':
                handle_pegging(event)
            # Counting phase
            if game_phase == 'counting':
                handle_counting()
            handle_end(event)
            # Dragging logic only in pegging phase
            if event.type == pygame.MOUSEBUTTONDOWN and game_phase == 'pegging':
                if player_turn == 0:
                    for card in player1_hand:
                        if card.rect.collidepoint(event.pos):
                            card.dragging = True
                            dragging_card = card
                            break
            elif event.type == pygame.MOUSEBUTTONUP:
                if 'dragging_card' in locals() and dragging_card:
                    dragging_card.dragging = False
                    dragging_card = None

        # Update
        for card in player1_hand + player2_hand + crib:
            card.update(mouse_pos)

        # Draw
        screen.blit(background, (0,0))
        # Draw Dad's image as the board (replace board.jpg)
        if dad_img:
            board_dad = pygame.transform.smoothscale(dad_img, (board_rect.width, board_rect.height))
            screen.blit(board_dad, (board_rect.x, board_rect.y))
        # Overlay peg tokens directly on board
        peg1_pos = get_peg_position(player_scores[0])
        peg2_pos = get_peg_position(player_scores[1])
        pygame.draw.circle(screen, (255, 0, 0), peg1_pos, peg_radius)
        pygame.draw.circle(screen, (0, 0, 255), peg2_pos, peg_radius)
        # Draw player hands
        legal_pegging = []
        if game_phase == 'pegging' and player_turn == 0:
            # Highlight legal pegging moves
            import cards
            def normalize_rank(rank):
                rank = rank.lower()
                if rank == 'ace': return 'A'
                if rank == 'jack': return 'J'
                if rank == 'queen': return 'Q'
                if rank == 'king': return 'K'
                return rank if rank.isdigit() else rank.title()
            def normalize_suit(suit):
                return suit.title()
            total = sum(cards.Card(normalize_rank(c.label.split(' of ')[0]), normalize_suit(c.label.split(' of ')[1])).value() for c in pegging_pile)
            legal_pegging = [i for i, card in enumerate(player1_hand) if total + cards.Card(normalize_rank(card.label.split(' of ')[0]), normalize_suit(card.label.split(' of ')[1])).value() <= 31]
        for idx, card in enumerate(player1_hand):
            # Highlight selected cards in discard phase
            if idx in selected_cards and game_phase == 'discard':
                highlight = pygame.Surface((CARD_WIDTH, CARD_HEIGHT), pygame.SRCALPHA)
                highlight.fill((255,255,0,120))
                screen.blit(highlight, card.rect)
                # Light hunter orange border for actively selected crib card
                pygame.draw.rect(screen, (255, 140, 0), card.rect, 5)
            # Outline legal pegging moves
            if game_phase == 'pegging' and player_turn == 0 and idx in legal_pegging:
                pygame.draw.rect(screen, (0,255,0), card.rect, 4)
            card.draw(screen)
        # Draw computer hand as card backs
        if show_computer_hand:
            for card in player2_hand:
                back = pygame.Surface((CARD_WIDTH, CARD_HEIGHT))
                back.fill((50, 50, 50))
                pygame.draw.rect(back, (0,0,0), back.get_rect(), 2)
                screen.blit(back, card.rect)
        # Draw crib as hidden cards in upper left corner
        for i, card in enumerate(crib):
            screen.blit(card.image, (30 + i*30, 30))
        # Draw pegging pile
        for i, card in enumerate(pegging_pile):
            card.rect.topleft = (400 + i*30, 200)
            card.draw(screen)
        # Show current pegging pile score
        if game_phase == 'pegging':
            import cards
            def normalize_rank(rank):
                rank = rank.lower()
                if rank == 'ace': return 'A'
                if rank == 'jack': return 'J'
                if rank == 'queen': return 'Q'
                if rank == 'king': return 'K'
                return rank if rank.isdigit() else rank.title()
            def normalize_suit(suit):
                return suit.title()
            pile_total = sum(cards.Card(normalize_rank(c.label.split(' of ')[0]), normalize_suit(c.label.split(' of ')[1])).value() for c in pegging_pile)
            font = pygame.font.SysFont('arial', 32, bold=True)
            screen.blit(font.render(f"Pegging Total: {pile_total}", True, (255,255,0)), (400, 170))
        # Score/Player areas
        font = pygame.font.SysFont('arial', 32, bold=True)
        screen.blit(font.render("Player 1", True, (0,0,0)), (30, 260))
        if tony_img:
            screen.blit(tony_img, (30, 320))
        if dad_img:
            screen.blit(dad_img, (770, 320))
        screen.blit(font.render(f"Score: {player_scores[0]}", True, (0,0,0)), (30, 300))
        screen.blit(font.render(f"Score: {player_scores[1]}", True, (0,0,0)), (770, 300))
        # Enforce score limits for standard board
        enforce_score_limits()
        # Pegs move along the board
        peg1_pos = get_peg_position(player_scores[0])
        peg2_pos = get_peg_position(player_scores[1])
        pygame.draw.circle(screen, (255, 0, 0), peg1_pos, peg_radius)
        pygame.draw.circle(screen, (0, 0, 255), peg2_pos, peg_radius)
        # Draw Dad's image at top right corner, after table/background and before UI overlays
        if dad_img:
            dad_width, dad_height = dad_img.get_width(), dad_img.get_height()
            screen.blit(dad_img, (screen.get_width() - dad_width - 30, 30))
        # Display message
        font = pygame.font.SysFont('arial', 28)
        # Simple word wrap for message
        def simple_wrap(text, font, max_width):
            words = text.split(' ')
            lines = []
            current = ''
            for word in words:
                test = current + (' ' if current else '') + word
                if font.size(test)[0] > max_width:
                    if current:
                        lines.append(current)
                    current = word
                else:
                    current = test
            if current:
                lines.append(current)
            return lines
        # Display message with hunter/forest green text on a black background for contrast
        draw_contrast_message(message, 40, 40, max_width=800, font_size=32, color=(34,139,34), border_radius=12)
        pygame.display.flip()
        clock.tick(FPS)

        # Check for winner and end game if score reaches 121
        if player_scores[0] >= max_score or player_scores[1] >= max_score:
            winner = player_name if player_scores[0] >= max_score else 'Dad'
            message = f"{winner} wins with {max_score} points! Press R to restart."
            draw_contrast_message(message, 40, 40, max_width=800, font_size=40, color=(255,0,0), border_radius=16)
            pygame.display.flip()
            while True:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                        # Reset everything for a new game
                        player_scores[0] = 0
                        player_scores[1] = 0
                        dealer = 1 - dealer
                        reset_round()
                        message = f"Dealer is now {'Player 1' if dealer==0 else 'Dad'}. Select 2 cards to discard to the crib."
                        break
                else:
                    continue
                break
        # Automatically advance to next round after scoring (end phase)
        elif game_phase == 'end':
            pygame.time.wait(1500)  # Wait 1.5 seconds to show scores
            dealer = 1 - dealer  # Alternate dealer
            reset_round()
            message = f"Dealer is now {'Player 1' if dealer==0 else 'Dad'}. Select 2 cards to discard to the crib."

# --- RUN GAME ---
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print('An error occurred:', e)
        traceback.print_exc()
