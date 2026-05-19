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
    count = 0
    for r in range(2, len(cards)+1):
        for combo in itertools.combinations(cards, r):
            if sum(card.value() for card in combo) == 15:
                count += 2
    return count

# Score pairs
def score_pairs(cards):
    count = 0
    ranks = [card.rank for card in cards]
    for rank in set(ranks):
        n = ranks.count(rank)
        if n >= 2:
            count += (n * (n-1)) // 2 * 2  # 2 points per pair
    return count

# Score runs
def score_runs(cards):
    ranks_map = {'A':1, '2':2, '3':3, '4':4, '5':5, '6':6, '7':7, '8':8, '9':9, '10':10, 'J':11, 'Q':12, 'K':13,
                 'Jack':11, 'Queen':12, 'King':13, 'jack':11, 'queen':12, 'king':13, 'ace':1}
    ranks = sorted([ranks_map[card.rank] for card in cards])
    max_run = 0
    for r in range(3, len(cards)+1):
        for combo in itertools.combinations(ranks, r):
            if list(combo) == list(range(combo[0], combo[0]+r)):
                if r > max_run:
                    max_run = r
    return max_run * (1 if max_run >= 3 else 0)

# Score flush
def score_flush(hand, starter):
    suits = [card.suit for card in hand]
    if all(s == suits[0] for s in suits):
        # 4-card flush
        if starter.suit == suits[0]:
            return 5
        return 4
    return 0

# Score nobs (Jack of same suit as starter)
def score_nobs(hand, starter):
    for card in hand:
        if card.rank == 'J' and card.suit == starter.suit:
            return 1
    return 0

# Total hand score
def score_hand(hand, starter):
    total = 0
    total += score_15s(hand + [starter])
    total += score_pairs(hand + [starter])
    total += score_runs(hand + [starter])
    total += score_flush(hand, starter)
    total += score_nobs(hand, starter)
    return total
