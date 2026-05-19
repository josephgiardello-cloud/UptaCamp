import random
import itertools

# Card representation
class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit

    def value(self):
        if self.rank in ['J', 'Q', 'K']:
            return 10
        elif self.rank == 'A':
            return 1
        else:
            return int(self.rank)

    def __repr__(self):
        return f"{self.rank} of {self.suit}"

# Deck representation
class Deck:
    suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
    ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

    def __init__(self):
        self.cards = [Card(rank, suit) for suit in self.suits for rank in self.ranks]
        random.shuffle(self.cards)

    def deal(self, num):
        return [self.cards.pop() for _ in range(num)]

# Simple deal for two players
deck = Deck()
player1_hand = deck.deal(6)
player2_hand = deck.deal(6)

print("Player 1 hand:", player1_hand)
print("Player 2 hand:", player2_hand)

# Crib will be filled after discards
crib = []

def score_15s(cards):
    breakdown = []
    for r in range(2, len(cards)+1):
        for combo in itertools.combinations(cards, r):
            if sum(card.value() for card in combo) == 15:
                breakdown.append(("Fifteen", [str(card) for card in combo], 2))
    return breakdown

# Score pairs
def score_pairs(cards):
    breakdown = []
    ranks = [card.rank for card in cards]
    for rank in set(ranks):
        n = ranks.count(rank)
        if n >= 2:
            pairs = (n * (n-1)) // 2
            for _ in range(pairs):
                pair_cards = [card for card in cards if card.rank == rank][:2]
                breakdown.append(("Pair", [str(card) for card in pair_cards], 2))
    return breakdown

# Score runs
def score_runs(cards):
    ranks_map = {'A':1, '2':2, '3':3, '4':4, '5':5, '6':6, '7':7, '8':8, '9':9, '10':10, 'J':11, 'Q':12, 'K':13,
                 'Jack':11, 'Queen':12, 'King':13, 'jack':11, 'queen':12, 'king':13, 'ace':1}
    breakdown = []
    for r in range(3, len(cards)+1):
        for combo in itertools.combinations(cards, r):
            ranks = sorted([ranks_map[card.rank] for card in combo])
            if list(ranks) == list(range(ranks[0], ranks[0]+r)):
                breakdown.append((f"Run of {r}", [str(card) for card in combo], r))
    return breakdown

# Score flush
def score_flush(hand, starter):
    suits = [card.suit for card in hand]
    if all(s == suits[0] for s in suits):
        # 4-card flush
        if starter.suit == suits[0]:
            return [("Flush (5)", [str(card) for card in hand] + [str(starter)], 5)]
        return [("Flush (4)", [str(card) for card in hand], 4)]
    return []

# Score nobs (Jack of same suit as starter)
def score_nobs(hand, starter):
    for card in hand:
        if card.rank == 'J' and card.suit == starter.suit:
            return [("Nobs", [str(card)], 1)]
    return []

# Total hand score
def score_hand(hand, starter):
    breakdown = []
    breakdown += score_15s(hand + [starter])
    breakdown += score_pairs(hand + [starter])
    breakdown += score_runs(hand + [starter])
    breakdown += score_flush(hand, starter)
    breakdown += score_nobs(hand, starter)
    total = sum(item[2] for item in breakdown)
    return total, breakdown
