import random
from collections import Counter
from itertools import combinations
from typing import Callable, List, Optional, Sequence


def _parse_label(label: str) -> tuple[str, str]:
    if "_of_" in label:
        rank, suit = label.split("_of_", 1)
        return rank.lower(), suit.lower()
    if " of " in label:
        rank, suit = label.split(" of ", 1)
        return rank.lower(), suit.lower()
    if "_" in label:
        rank, suit = label.split("_", 1)
        return rank.lower(), suit.lower()
    return label.lower(), ""


def _rank_order(rank: str) -> int:
    mapping = {"ace": 1, "jack": 11, "queen": 12, "king": 13}
    if rank in mapping:
        return mapping[rank]
    return int(rank)


def _value_for_15(rank: str) -> int:
    if rank in {"jack", "queen", "king"}:
        return 10
    if rank == "ace":
        return 1
    return int(rank)


def _count_fifteens(labels: Sequence[str]) -> int:
    values = [_value_for_15(_parse_label(label)[0]) for label in labels]
    total = 0
    for size in range(2, len(values) + 1):
        for combo in combinations(values, size):
            if sum(combo) == 15:
                total += 1
    return total


def _intrinsic_keep_score(labels: Sequence[str]) -> float:
    ranks = [_rank_order(_parse_label(label)[0]) for label in labels]
    suits = [_parse_label(label)[1] for label in labels]
    counts = Counter(ranks)

    pair_bonus = sum(2.4 for count in counts.values() if count == 2)
    pair_bonus += sum(6.0 for count in counts.values() if count == 3)

    unique_ranks = sorted(set(ranks))
    run_bonus = 0.0
    streak = 1
    for idx in range(1, len(unique_ranks)):
        if unique_ranks[idx] == unique_ranks[idx - 1] + 1:
            streak += 1
            scaled_run = 1.5 * streak if streak >= 3 else 0.0
            if streak >= 4:
                scaled_run += 0.8
            run_bonus = max(run_bonus, scaled_run)
        else:
            streak = 1

    fifteen_bonus = 1.6 * _count_fifteens(labels)
    low_card_bonus = sum(0.18 for rank in ranks if rank in {4, 5, 6, 7})
    flush_bonus = 1.2 if len(set(suits)) == 1 and suits[0] else 0.0
    return pair_bonus + run_bonus + fifteen_bonus + low_card_bonus + flush_bonus


def _discard_crib_score(labels: Sequence[str]) -> float:
    ranks = [_rank_order(_parse_label(label)[0]) for label in labels]
    values = [_value_for_15(_parse_label(label)[0]) for label in labels]
    suits = [_parse_label(label)[1] for label in labels]

    score = 0.0
    if len(set(ranks)) == 1:
        score += 3.5
    if abs(ranks[0] - ranks[1]) == 1:
        score += 1.4
    if sum(values) == 15:
        score += 2.4
    if 5 in values:
        score += 2.1
    if 10 in values and 5 in values:
        score += 1.4
    if suits[0] and suits[0] == suits[1]:
        score += 0.35
    return score


def _pegging_shape_adjustment(trial_total: int, immediate: int, hand_labels: Sequence[str], played_label: str) -> float:
    score = 0.0

    # Avoid feeding easy 15/31 replies on common ten-card responses.
    if trial_total in {5, 10, 21}:
        score -= 1.4
    if trial_total in {14, 20, 26}:
        score -= 0.8

    # Favor safer lead/count totals that constrain common responses.
    if trial_total in {4, 6, 11, 16, 17, 24}:
        score += 0.45

    rank = _parse_label(played_label)[0]
    value = _value_for_15(rank)

    # Leading a 5 is usually a gift unless it scores immediately.
    if len(hand_labels) == 4 and value == 5 and immediate == 0:
        score -= 2.25

    # Preserve small cards early when no immediate scoring exists.
    if len(hand_labels) >= 3 and immediate == 0 and value >= 10:
        score -= 0.35

    return score


def choose_discard_indices(
    dad_labels: Sequence[str],
    dad_ai_level: int,
    dealer_is_dad: bool,
    canonical_deck_labels: Sequence[str],
    score_labels_hand: Callable[[List[str], str, bool], int],
) -> List[int]:
    if len(dad_labels) != 6:
        return [0, 1]

    if dad_ai_level == 1:
        return random.sample(range(6), 2)

    unseen_pool = list(set(canonical_deck_labels) - set(dad_labels))
    if not unseen_pool:
        return random.sample(range(6), 2)

    best_idxs = [0, 1]
    best_score = float("-inf")

    for discard_idxs in combinations(range(6), 2):
        discard_set = set(discard_idxs)
        kept = [dad_labels[i] for i in range(6) if i not in discard_set]
        discards = [dad_labels[i] for i in discard_idxs]

        if dad_ai_level == 2:
            total = 0.0
            for starter in unseen_pool:
                total += score_labels_hand(kept, starter, False)
            score = total / len(unseen_pool)
            score += 0.35 * _intrinsic_keep_score(kept)
            score += (0.22 if dealer_is_dad else -0.18) * _discard_crib_score(discards)
        else:
            trials = min(220, len(unseen_pool) * 4)
            total = 0.0
            for _ in range(trials):
                opp_discards = random.sample(unseen_pool, 2)
                rem = [lbl for lbl in unseen_pool if lbl not in opp_discards]
                if not rem:
                    continue
                starter = random.choice(rem)
                own_score = score_labels_hand(kept, starter, False)
                crib_labels = discards + opp_discards
                crib_score = score_labels_hand(crib_labels, starter, True)
                total += own_score + (crib_score if dealer_is_dad else -crib_score)
            score = total / max(1, trials)
            score += 0.55 * _intrinsic_keep_score(kept)
            score += (0.5 if dealer_is_dad else -0.32) * _discard_crib_score(discards)

        if score > best_score:
            best_score = score
            best_idxs = list(discard_idxs)

    return best_idxs


def choose_pegging_index(
    hand_labels: Sequence[str],
    current_total: int,
    dad_ai_level: int,
    value_for_15: Callable[[str], int],
    parse_label: Callable[[str], tuple[str, str]],
    score_pegging_play: Callable[[Sequence], int],
    label_card_factory: Callable[[str], object],
    current_pegging_labels: Sequence[str],
    estimate_opponent_reply_risk: Optional[Callable[[Sequence], float]] = None,
) -> Optional[int]:
    legal = [
        i for i, label in enumerate(hand_labels)
        if current_total + value_for_15(parse_label(label)[0]) <= 31
    ]
    if not legal:
        return None

    if dad_ai_level == 1:
        return random.choice(legal)

    best_idx = legal[0]
    best_score = float("-inf")

    for idx in legal:
        label = hand_labels[idx]
        trial_pile = [label_card_factory(lbl) for lbl in current_pegging_labels] + [label_card_factory(label)]
        immediate = score_pegging_play(trial_pile)
        trial_total = sum(value_for_15(parse_label(lbl)[0]) for lbl in current_pegging_labels + [label])

        shape_bonus = _pegging_shape_adjustment(trial_total, immediate, hand_labels, label)

        score = immediate + shape_bonus
        if dad_ai_level == 3 and estimate_opponent_reply_risk is not None:
            score -= 0.85 * estimate_opponent_reply_risk(trial_pile)

        if score > best_score:
            best_score = score
            best_idx = idx

    return best_idx
