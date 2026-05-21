import itertools

# Card representation
from dataclasses import dataclass


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    @property
    def id(self) -> str:
        return f"{self.rank}{self.suit}"

    def value(self):
        rank = _normalize_rank(self.rank)
        if rank in ["J", "Q", "K"]:
            return 10
        elif rank == "A":
            return 1
        else:
            return int(rank)

    def __repr__(self):
        return f"{self.rank} of {self.suit}"


## Deck logic will be handled in CribbageEngine/GameState


def _normalize_rank(rank: str) -> str:
    token = str(rank).strip().lower()
    mapping = {
        "ace": "A",
        "a": "A",
        "ten": "10",
        "t": "10",
        "jack": "J",
        "j": "J",
        "queen": "Q",
        "q": "Q",
        "king": "K",
        "k": "K",
    }
    return mapping.get(token, token.upper())


def parse_card_label(label: str) -> tuple[str, str]:
    token = str(label)
    if " of " in token:
        rank, suit = token.split(" of ", 1)
        return rank.strip().lower(), suit.strip().lower()
    if "_of_" in token:
        rank, suit = token.split("_of_", 1)
        return rank.strip().lower(), suit.strip().lower()
    if "_" in token:
        rank, suit = token.split("_", 1)
        return rank.strip().lower(), suit.strip().lower()
    return token.strip().lower(), ""


def rank_index(rank: str) -> int:
    normalized = _normalize_rank(rank)
    mapping = {"A": 1, "J": 11, "Q": 12, "K": 13}
    if normalized in mapping:
        return mapping[normalized]
    try:
        return int(normalized)
    except ValueError:
        return 0


def value_for_fifteen(rank: str) -> int:
    normalized = _normalize_rank(rank)
    if normalized == "A":
        return 1
    if normalized in {"J", "Q", "K", "10"}:
        return 10
    try:
        return int(normalized)
    except ValueError:
        return 0


def label_to_card(label: str) -> Card:
    rank, suit = parse_card_label(label)
    rank_map = {
        "ace": "A",
        "jack": "J",
        "queen": "Q",
        "king": "K",
    }
    suit_map = {
        "clubs": "Clubs",
        "diamonds": "Diamonds",
        "hearts": "Hearts",
        "spades": "Spades",
    }
    model_rank = rank_map.get(rank, rank.upper())
    model_suit = suit_map.get(suit, suit.title())
    return Card(model_rank, model_suit)


def card_label(card_or_label: object) -> str:
    return str(getattr(card_or_label, "label", card_or_label))


def pegging_total(pile: list[object]) -> int:
    return sum(value_for_fifteen(parse_card_label(card_label(item))[0]) for item in pile)


def score_pegging_play(pile: list[object], new_card: object | None = None) -> int:
    working_pile = list(pile)
    if new_card is not None:
        working_pile.append(new_card)

    pile = working_pile
    if not pile:
        return 0

    total = pegging_total(pile)
    points = 0

    if total in {15, 31}:
        points += 2

    # Pair / pair royal / double pair royal from the end of the pile.
    last_rank = parse_card_label(card_label(pile[-1]))[0]
    same_rank_count = 1
    for i in range(len(pile) - 2, -1, -1):
        if parse_card_label(card_label(pile[i]))[0] == last_rank:
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
        ranks = [rank_index(parse_card_label(card_label(c))[0]) for c in pile[-run_len:]]
        if len(set(ranks)) != run_len:
            continue
        if max(ranks) - min(ranks) + 1 == run_len:
            points += run_len
            break

    return points


def score_15s(cards: list[Card]) -> list[tuple[str, list[str], int]]:
    breakdown: list[tuple[str, list[str], int]] = []
    seen: set[tuple[str, ...]] = set()
    for r in range(2, len(cards) + 1):
        for combo in itertools.combinations(cards, r):
            if sum(card.value() for card in combo) == 15:
                labels = tuple(sorted(str(card) for card in combo))
                if labels in seen:
                    continue
                seen.add(labels)
                breakdown.append(("Fifteen", list(labels), 2))
    return breakdown


# Score pairs
def score_pairs(cards: list[Card]) -> list[tuple[str, list[str], int]]:
    breakdown: list[tuple[str, list[str], int]] = []
    ranks = [_normalize_rank(card.rank) for card in cards]
    for rank in sorted(set(ranks)):
        matched = [card for card in cards if _normalize_rank(card.rank) == rank]
        if len(matched) < 2:
            continue
        for combo in itertools.combinations(matched, 2):
            breakdown.append(("Pair", [str(card) for card in combo], 2))
    return breakdown


def find_all_runs(cards: list[Card]) -> list[tuple[int, int, list[Card]]]:
    if len(cards) < 3:
        return []

    def _is_run(combo: tuple[Card, ...]) -> tuple[bool, tuple[int, ...]]:
        ranks = tuple(sorted(rank_index(card.rank) for card in combo))
        if len(set(ranks)) != len(combo):
            return False, ()
        for i in range(1, len(ranks)):
            if ranks[i] != ranks[i - 1] + 1:
                return False, ()
        return True, ranks

    valid: list[tuple[int, tuple[int, ...], tuple[Card, ...]]] = []
    for size in range(3, len(cards) + 1):
        for combo in itertools.combinations(cards, size):
            ok, rank_seq = _is_run(combo)
            if ok:
                valid.append((size, rank_seq, combo))

    if not valid:
        return []

    max_len = max(item[0] for item in valid)
    longest = [item for item in valid if item[0] == max_len]

    grouped: dict[tuple[int, ...], list[tuple[Card, ...]]] = {}
    for _, rank_seq, combo in longest:
        grouped.setdefault(rank_seq, []).append(combo)

    runs: list[tuple[int, int, list[Card]]] = []
    for rank_seq in sorted(grouped.keys()):
        combos = grouped[rank_seq]
        multiplicity = len(combos)
        run_cards_set: set[Card] = set()
        for combo in combos:
            run_cards_set.update(combo)
        run_cards = sorted(
            run_cards_set,
            key=lambda c: (rank_index(c.rank), str(c.suit)),
        )
        runs.append((max_len, multiplicity, run_cards))

    return runs


def _run_card_combinations(cards: list[Card]) -> list[tuple[Card, ...]]:
    by_rank: dict[int, list[Card]] = {}
    for card in cards:
        key = rank_index(card.rank)
        by_rank.setdefault(key, []).append(card)

    ordered_ranks = sorted(by_rank.keys())
    return list(itertools.product(*(by_rank[rank] for rank in ordered_ranks)))


# Score runs
def score_runs(cards: list[Card]) -> list[tuple[str, list[str], int]]:
    runs = find_all_runs(cards)
    if not runs:
        return []

    breakdown: list[tuple[str, list[str], int]] = []
    for run_len, multiplicity, run_cards in runs:
        for combo in _run_card_combinations(run_cards):
            breakdown.append((f"Run of {run_len} (x{multiplicity})", [str(card) for card in combo], run_len))
    return breakdown


# Score flush
def score_flush(hand: list[Card], starter: Card, is_crib: bool = False) -> list[tuple[str, list[str], int]]:
    suits = [card.suit for card in hand]
    if not suits or not all(s == suits[0] for s in suits):
        return []

    if is_crib:
        if starter.suit == suits[0]:
            return [("Flush (5 crib)", [str(card) for card in hand] + [str(starter)], 5)]
        return []

    if starter.suit == suits[0]:
        return [("Flush (5)", [str(card) for card in hand] + [str(starter)], 5)]
    return [("Flush (4)", [str(card) for card in hand], 4)]


# Score nobs (Jack of same suit as starter)
def score_nobs(hand: list[Card], starter: Card) -> list[tuple[str, list[str], int]]:
    starter_suit = str(starter.suit).strip().lower()
    for card in hand:
        if _normalize_rank(card.rank) == "J" and str(card.suit).strip().lower() == starter_suit:
            return [("Nobs", [str(card)], 1)]
    return []


# Total hand score
def score_hand(hand: list[Card], starter: Card, is_crib: bool = False) -> tuple[int, list[tuple[str, list[str], int]]]:
    breakdown: list[tuple[str, list[str], int]] = []
    breakdown += score_15s(hand + [starter])
    breakdown += score_pairs(hand + [starter])
    breakdown += score_runs(hand + [starter])
    breakdown += score_flush(hand, starter, is_crib=is_crib)
    breakdown += score_nobs(hand, starter)
    total = sum(item[2] for item in breakdown)
    return total, breakdown
