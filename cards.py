import random
import itertools
from collections import Counter

# Card representation
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Card:
    rank: str
    suit: str
    id: str = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, 'id', f"{self.rank}{self.suit}")

    def value(self):
        rank = _normalize_rank(self.rank)
        if rank in ['J', 'Q', 'K']:
            return 10
        elif rank == 'A':
            return 1
        else:
            return int(rank)

    def __repr__(self):
        return f"{self.rank} of {self.suit}"

## Deck logic will be handled in CribbageEngine/GameState

def _normalize_rank(rank: str) -> str:
    token = str(rank).strip().lower()
    mapping = {
        'ace': 'A', 'a': 'A',
        'jack': 'J', 'j': 'J',
        'queen': 'Q', 'q': 'Q',
        'king': 'K', 'k': 'K',
    }
    return mapping.get(token, token.upper())

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
    ranks = [_normalize_rank(card.rank) for card in cards]
    for rank in set(ranks):
        n = ranks.count(rank)
        if n >= 2:
            pairs = (n * (n-1)) // 2
            for _ in range(pairs):
                pair_cards = [card for card in cards if _normalize_rank(card.rank) == rank][:2]
                breakdown.append(("Pair", [str(card) for card in pair_cards], 2))
    return breakdown

# Score runs
def score_runs(cards):
    ranks_map = {
        'A': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
        'J': 11, 'Q': 12, 'K': 13,
    }

    rank_values = [ranks_map[_normalize_rank(card.rank)] for card in cards]
    counts = Counter(rank_values)
    unique = sorted(counts.keys())

    # Cribbage counts only the longest run(s); duplicates multiply run count.
    for run_len in range(len(unique), 2, -1):
        for start in range(1, 15 - run_len):
            seq = list(range(start, start + run_len))
            if all(v in counts for v in seq):
                multiplicity = 1
                for v in seq:
                    multiplicity *= counts[v]
                points = run_len * multiplicity
                return [(f"Run of {run_len} x{multiplicity}", [str(card) for card in cards], points)]

    return []

# Score flush
def score_flush(hand, starter, is_crib=False):
    suits = [card.suit for card in hand]
    if all(s == suits[0] for s in suits):
        # In crib, flush only scores if starter matches (5-card flush).
        if is_crib:
            if starter.suit == suits[0]:
                return [("Flush (5 crib)", [str(card) for card in hand] + [str(starter)], 5)]
            return []
        # Non-crib hand: 4-card flush allowed.
        if starter.suit == suits[0]:
            return [("Flush (5)", [str(card) for card in hand] + [str(starter)], 5)]
        return [("Flush (4)", [str(card) for card in hand], 4)]
    return []

# Score nobs (Jack of same suit as starter)
def score_nobs(hand, starter):
    starter_suit = str(starter.suit).strip().lower()
    for card in hand:
        if _normalize_rank(card.rank) == 'J' and str(card.suit).strip().lower() == starter_suit:
            return [("Nobs", [str(card)], 1)]
    return []

# Total hand score
def score_hand(hand, starter, is_crib=False):
    breakdown = []
    breakdown += score_15s(hand + [starter])
    breakdown += score_pairs(hand + [starter])
    breakdown += score_runs(hand + [starter])
    breakdown += score_flush(hand, starter, is_crib=is_crib)
    breakdown += score_nobs(hand, starter)
    total = sum(item[2] for item in breakdown)
    return total, breakdown
