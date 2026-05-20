import random
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from bert_agent import BertAgent
from game_state import GameState

_BERT_AGENT: BertAgent | None = None
_DEFAULT_BERT_MODEL = Path("bert_model.pkl")


def set_bert_agent(agent: BertAgent) -> None:
    global _BERT_AGENT
    _BERT_AGENT = agent


def get_bert_agent() -> BertAgent:
    global _BERT_AGENT
    if _BERT_AGENT is None:
        _BERT_AGENT = BertAgent()
        if _DEFAULT_BERT_MODEL.exists():
            try:
                _BERT_AGENT.load(_DEFAULT_BERT_MODEL)
            except Exception:
                pass
    return _BERT_AGENT


def load_bert_agent(path: str | Path = _DEFAULT_BERT_MODEL) -> BertAgent:
    agent = BertAgent()
    agent.load(path)
    set_bert_agent(agent)
    return agent


def save_bert_agent(path: str | Path = _DEFAULT_BERT_MODEL) -> None:
    agent = get_bert_agent()
    agent.save(path)


@dataclass(frozen=True)
class DiscardOption:
    discard_indices: tuple[int, int]
    discard_labels: tuple[str, str]
    keep_labels: tuple[str, str, str, str]
    expected_points: float
    percentile: float


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


def _pegging_shape_adjustment(
    trial_total: int, immediate: int, hand_labels: Sequence[str], played_label: str
) -> float:
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
    score_labels_hand: Callable[[list[str], str, bool], int],
    game_state: GameState | None = None,
) -> list[int]:
    if len(dad_labels) != 6:
        return [0, 1]

    if dad_ai_level == 1:
        return random.sample(range(6), 2)

    if dad_ai_level == 5:
        state = game_state or GameState()
        idx1, idx2 = get_bert_agent().choose_discard(dad_labels, state)
        return [idx1, idx2]

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
        elif dad_ai_level == 3:
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
        else:
            # Brutal mode: deeper simulation with heavier intrinsic weighting.
            trials = min(560, len(unseen_pool) * 10)
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
            score += 0.8 * _intrinsic_keep_score(kept)
            score += (0.65 if dealer_is_dad else -0.45) * _discard_crib_score(discards)

        if score > best_score:
            best_score = score
            best_idxs = list(discard_idxs)

    return best_idxs


def analyze_discard_options(
    hand_labels: Sequence[str],
    dealer_is_player: bool,
    canonical_deck_labels: Sequence[str],
    score_labels_hand: Callable[[list[str], str, bool], int],
) -> list[DiscardOption]:
    if len(hand_labels) != 6:
        return []

    unseen_pool = [lbl for lbl in canonical_deck_labels if lbl not in set(hand_labels)]
    if not unseen_pool:
        return []

    scored: list[tuple[tuple[int, int], tuple[str, str], tuple[str, str, str, str], float]] = []
    for discard_idxs in combinations(range(6), 2):
        discard_set = set(discard_idxs)
        kept = [hand_labels[i] for i in range(6) if i not in discard_set]
        discards = [hand_labels[i] for i in discard_idxs]

        total = 0.0
        for starter in unseen_pool:
            own_score = score_labels_hand(kept, starter, False)
            # Approximate crib influence by expected random opponent discard value.
            # This keeps analysis deterministic and fast for learning feedback.
            total += own_score + (
                (0.45 if dealer_is_player else -0.35) * _discard_crib_score(discards)
            )
        expected = total / len(unseen_pool)
        scored.append(
            (
                (discard_idxs[0], discard_idxs[1]),
                (discards[0], discards[1]),
                (kept[0], kept[1], kept[2], kept[3]),
                expected,
            )
        )

    scored.sort(key=lambda row: row[3], reverse=True)
    if not scored:
        return []

    lo = scored[-1][3]
    hi = scored[0][3]
    span = hi - lo

    analyzed: list[DiscardOption] = []
    for discard_idxs, discard_labels, keep_labels, expected in scored:
        if span <= 1e-9:
            percentile = 100.0
        else:
            percentile = max(0.0, min(100.0, ((expected - lo) / span) * 100.0))
        analyzed.append(
            DiscardOption(
                discard_indices=discard_idxs,
                discard_labels=discard_labels,
                keep_labels=keep_labels,
                expected_points=expected,
                percentile=percentile,
            )
        )

    return analyzed


def choose_pegging_index(
    hand_labels: Sequence[str],
    current_total: int,
    dad_ai_level: int,
    value_for_15: Callable[[str], int],
    parse_label: Callable[[str], tuple[str, str]],
    score_pegging_play: Callable[[Sequence], int],
    label_card_factory: Callable[[str], object],
    current_pegging_labels: Sequence[str],
    estimate_opponent_reply_risk: Callable[[Sequence], float] | None = None,
    own_score: int | None = None,
    opp_score: int | None = None,
    own_cards_remaining: int | None = None,
    game_state: GameState | None = None,
) -> int | None:
    legal = [
        i
        for i, label in enumerate(hand_labels)
        if current_total + value_for_15(parse_label(label)[0]) <= 31
    ]
    if not legal:
        return None

    if dad_ai_level == 1:
        return random.choice(legal)

    if dad_ai_level == 5:
        state = game_state or GameState()
        return get_bert_agent().choose_pegging(hand_labels, current_total, state)

    best_idx = legal[0]
    best_score = float("-inf")

    for idx in legal:
        label = hand_labels[idx]
        trial_pile = [label_card_factory(lbl) for lbl in current_pegging_labels] + [
            label_card_factory(label)
        ]
        immediate = score_pegging_play(trial_pile)
        trial_total = sum(
            value_for_15(parse_label(lbl)[0]) for lbl in [*list(current_pegging_labels), label]
        )

        shape_bonus = _pegging_shape_adjustment(trial_total, immediate, hand_labels, label)

        score = immediate + shape_bonus
        if dad_ai_level >= 3 and estimate_opponent_reply_risk is not None:
            score -= 0.85 * estimate_opponent_reply_risk(trial_pile)

        if dad_ai_level >= 4:
            # Endgame awareness: when close to 121, prioritize immediate points.
            if own_score is not None and own_score >= 112:
                score += 0.7 * immediate
            if opp_score is not None and opp_score >= 112 and immediate == 0:
                score -= 0.4

            # Early-round discipline in brutal mode.
            if own_cards_remaining is not None and own_cards_remaining >= 3 and immediate == 0:
                val = value_for_15(parse_label(label)[0])
                if val >= 10:
                    score -= 0.25

        if score > best_score:
            best_score = score
            best_idx = idx

    return best_idx
