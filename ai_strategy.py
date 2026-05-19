import random
from itertools import combinations
from typing import Callable, List, Optional, Sequence


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

        shape_bonus = 0.0
        if trial_total in (5, 10, 21):
            shape_bonus += 0.6
        if trial_total in (14, 20, 26):
            shape_bonus -= 0.5

        score = immediate + shape_bonus
        if dad_ai_level == 3 and estimate_opponent_reply_risk is not None:
            score -= 0.85 * estimate_opponent_reply_risk(trial_pile)

        if score > best_score:
            best_score = score
            best_idx = idx

    return best_idx
