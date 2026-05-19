class GameState:
    def __init__(self):
        self.phase = 'intro'  # Game phase/state machine
        self.scores = [0, 0]  # [Player, AI]
        self.player_hand = []
        self.ai_hand = []
        self.pegging_pile = []
        self.crib = []
        self.dealer = 0
        self.message = ''
        self.deck = None
        self.cut_card = None
        self.selected_cards = []
        self.winner = None
        self.ai_level = 1
        self.player_name = ''
        self.ai_name = 'Dad'
        self.history = []  # For undo/redo or replay
        # Add any other stateful variables here as needed
