import random
import threading
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from bert_agent import BertAgent
from game_state import GameState

# === Strategy Constants ===

# Keep-score weighting (hand value assessment)
PAIR_WEIGHT: float = 2.4  # Pair bonus multiplier
PAIR_ROYAL_WEIGHT: float = 6.0  # Three-of-a-kind bonus multiplier
RUN_BASE_WEIGHT: float = 1.5  # Run combo base weight
RUN_LENGTH_BONUS: float = 0.8  # Additional bonus for streak >= 4
FIFTEEN_WEIGHT: float = 1.6  # Fifteen-sum combo weight
LOW_CARD_WEIGHT: float = 0.18  # Bonus for low cards {4,5,6,7}
FLUSH_WEIGHT: float = 1.2  # Flush bonus multiplier

# Crib-score weighting (discard penalty/value for opponent's crib)
DISCARD_PAIR_WEIGHT: float = 3.5  # Pair penalty in crib
DISCARD_RUN_ADJACENT: float = 1.4  # Adjacent rank bonus + 10+5 combo weight
DISCARD_15_WEIGHT: float = 2.4  # 15-sum penalty in crib
DISCARD_FIVE_WEIGHT: float = 2.1  # Five-value penalty in crib
DISCARD_FLUSH_WEIGHT: float = 0.35  # Flush penalty in crib

# Pegging shape adjustments (risky vs. safe totals)
PEGGING_RISKY_PENALTY_PRIMARY: float = 1.4  # Penalty for {5, 10, 21}
PEGGING_RISKY_PENALTY_SECONDARY: float = 0.8  # Penalty for {14, 20, 26}
PEGGING_SAFE_BONUS: float = 0.45  # Bonus for {4, 6, 11, 16, 17, 24}
PEGGING_LEAD_FIVE_PENALTY: float = 2.25  # Leading a 5 when not scoring
PEGGING_EARLY_TEN_PENALTY: float = 0.35  # Preserving 10+ cards early

# Discard level weighting (difficulty-dependent strategy)
# Level 2: lighter simulation, intrinsic/crib weight
LEVEL_2_INTRINSIC: float = 0.35
LEVEL_2_DEALER_CRIB: float = 0.22
LEVEL_2_PONE_CRIB: float = -0.18

# Level 3: medium simulation, heavier weights
LEVEL_3_INTRINSIC: float = 0.55
LEVEL_3_DEALER_CRIB: float = 0.5
LEVEL_3_PONE_CRIB: float = -0.32

# Level 4: deep simulation, heaviest weights
LEVEL_4_INTRINSIC: float = 0.8
LEVEL_4_DEALER_CRIB: float = 0.65
LEVEL_4_PONE_CRIB: float = -0.45

# Trial limits (simulation depths)
LEVEL_3_TRIALS: int = 220
LEVEL_4_TRIALS: int = 560

# Pegging-index strategy weights
OPPONENT_REPLY_RISK_DISCOUNT: float = 0.85  # Discount for opponent risk
ENDGAME_IMMEDIATE_BONUS: float = 0.7  # Bonus when close to 121
ENDGAME_PREVENTION_PENALTY: float = 0.4  # Penalty for preventing endgame score
EARLY_DISCIPLINE_PENALTY: float = 0.25  # Penalty for early 10+ preservation
ENDGAME_THRESHOLD: int = 112  # Score threshold (121 - 9 = closest endgame)

# Analysis constants
ANALYSIS_DEALER_CRIB: float = 0.45  # Dealer crib weight in analysis
ANALYSIS_PONE_CRIB: float = -0.35  # Pone crib weight in analysis
PERCENTILE_EPSILON: float = 1e-9  # Epsilon for span normalization

_BERT_AGENT: BertAgent | None = None
_DEFAULT_BERT_MODEL = Path("bert_model.pkl")


def _level5_posture_from_state(state: GameState | None) -> str:
    if state is None:
        return "balanced"
    player_score = int(state.scores[0]) if len(state.scores) > 0 else 0
    bert_score = int(state.scores[1]) if len(state.scores) > 1 else 0
    posture_agent = BertAgent()
    return posture_agent.get_posture_from_score(bert_score, player_score)


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


def get_reward(
    points: int,
    opponent_points_lost: int,
    action_type: str = "general",
    game_context: dict | None = None,
) -> float:
    """Calculate shaped reward for learning agent.

    Reward function balances immediate points with strategic value.
    Positive for favorable outcomes, negative for poor decisions.

    Args:
        points: Points scored by AI in this action/step
        opponent_points_lost: Opportunity cost (points opponent could have scored)
        action_type: "discard", "pegging", or "general"
        game_context: Optional dict with "own_score", "opp_score" for endgame scaling

    Returns:
        Float reward value for TD update
    """
    reward = float(points)

    # Reward avoiding opponent scoring
    reward += 0.3 * float(opponent_points_lost)

    # Action-type modulation
    if action_type == "discard":
        # Discard is critical; weight more heavily
        reward *= 1.2
    elif action_type == "pegging":
        # Pegging is fine-grained; reduce variance
        reward *= 0.8

    # Endgame scaling: boost immediate points when close to 121
    if game_context:
        own_score = game_context.get("own_score", 0)
        if own_score >= 112:
            reward *= 1.5

    return reward


def _run_discard_with_timeout(
    dad_labels: Sequence[str],
    dad_ai_level: int,
    dealer_is_dad: bool,
    canonical_deck_labels: Sequence[str],
    score_labels_hand: Callable[[list[str], str, bool], int],
    game_state: GameState | None,
    timeout_seconds: float = 2.0,
) -> list[int]:
    """Run discard selection with timeout (Windows-safe threading.Timer).

    If timeout expires, returns random valid discard.

    Args:
        dad_labels: AI's 6 cards
        dad_ai_level: Difficulty level 1-5
        dealer_is_dad: Whether AI is dealer
        canonical_deck_labels: Full deck labels
        score_labels_hand: Scoring function
        game_state: Current game state
        timeout_seconds: Max seconds to allow for discard (default 2.0)

    Returns:
        List of 2 card indices to discard
    """
    result: list[int] = [0, 1]  # Default if timeout
    result_lock = threading.Lock()
    result_computed = threading.Event()

    def compute_discard() -> None:
        nonlocal result
        try:
            computed = choose_discard_indices(
                dad_labels=dad_labels,
                dad_ai_level=dad_ai_level,
                dealer_is_dad=dealer_is_dad,
                canonical_deck_labels=canonical_deck_labels,
                score_labels_hand=score_labels_hand,
                game_state=game_state,
            )
            with result_lock:
                result = computed
        except Exception:
            # On error, use safe default
            pass
        finally:
            result_computed.set()

    # Start computation in background thread
    thread = threading.Thread(target=compute_discard, daemon=True)
    thread.start()

    # Wait for completion or timeout
    if result_computed.wait(timeout=timeout_seconds):
        with result_lock:
            return result
    else:
        # Timeout: return safe default
        return [0, 1]


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
    if len(labels) != 4:
        return 0.0

    ranks = [_rank_order(_parse_label(label)[0]) for label in labels]
    suits = [_parse_label(label)[1] for label in labels]
    values = [_value_for_15(_parse_label(label)[0]) for label in labels]
    counts = Counter(ranks)

    pair_bonus = sum(PAIR_WEIGHT * (count * (count - 1) // 2) for count in counts.values())
    trips_bonus = sum(PAIR_ROYAL_WEIGHT * (count == 3) for count in counts.values())

    sorted_ranks = sorted(set(ranks))
    run_bonus = 0.0
    streak = 1
    for idx in range(1, len(sorted_ranks)):
        if sorted_ranks[idx] == sorted_ranks[idx - 1] + 1:
            streak += 1
            if streak >= 3:
                run_bonus += RUN_BASE_WEIGHT * streak + (streak - 3) * RUN_LENGTH_BONUS
        else:
            streak = 1

    fifteen_bonus = FIFTEEN_WEIGHT * _count_fifteens(labels)
    low_card_bonus = sum(LOW_CARD_WEIGHT for rank in ranks if rank in {4, 5, 6, 7})
    flush_bonus = FLUSH_WEIGHT if len(set(suits)) == 1 and suits[0] else 0.0
    five_bonus = 0.65 * values.count(5)

    return pair_bonus + trips_bonus + run_bonus + fifteen_bonus + low_card_bonus + flush_bonus + five_bonus


def _discard_crib_score(labels: Sequence[str]) -> float:
    ranks = [_rank_order(_parse_label(label)[0]) for label in labels]
    values = [_value_for_15(_parse_label(label)[0]) for label in labels]
    suits = [_parse_label(label)[1] for label in labels]

    score = 0.0
    if len(set(ranks)) == 1:
        score += DISCARD_PAIR_WEIGHT
    if abs(ranks[0] - ranks[1]) == 1:
        score += DISCARD_RUN_ADJACENT
    if sum(values) == 15:
        score += DISCARD_15_WEIGHT
    if 5 in values:
        score += DISCARD_FIVE_WEIGHT
    if 10 in values and 5 in values:
        score += DISCARD_RUN_ADJACENT
    if suits[0] and suits[0] == suits[1]:
        score += DISCARD_FLUSH_WEIGHT
    return score


def _pegging_shape_adjustment(
    trial_total: int, immediate: int, hand_labels: Sequence[str], played_label: str
) -> float:
    score = 0.0

    # Avoid feeding easy 15/31 replies on common ten-card responses.
    if trial_total in {5, 10, 21}:
        score -= PEGGING_RISKY_PENALTY_PRIMARY
    if trial_total in {14, 20, 26}:
        score -= PEGGING_RISKY_PENALTY_SECONDARY

    # Favor safer lead/count totals that constrain common responses.
    if trial_total in {4, 6, 11, 16, 17, 24}:
        score += PEGGING_SAFE_BONUS

    rank = _parse_label(played_label)[0]
    value = _value_for_15(rank)

    # Leading a 5 is usually a gift unless it scores immediately.
    if len(hand_labels) == 4 and value == 5 and immediate == 0:
        score -= PEGGING_LEAD_FIVE_PENALTY

    # Preserve small cards early when no immediate scoring exists.
    if len(hand_labels) >= 3 and immediate == 0 and value >= 10:
        score -= PEGGING_EARLY_TEN_PENALTY

    return score


def choose_discard_indices(
    dad_labels: Sequence[str],
    dad_ai_level: int,
    dealer_is_dad: bool,
    canonical_deck_labels: Sequence[str],
    score_labels_hand: Callable[[list[str], str, bool], int],
    game_state: GameState | None = None,
    timeout_seconds: float | None = None,
) -> list[int]:
    """Choose which 2 cards to discard (main entry point with optional timeout).

    Args:
        dad_labels: AI's 6 cards
        dad_ai_level: Difficulty level 1-5
        dealer_is_dad: Whether AI is dealer
        canonical_deck_labels: Full deck labels
        score_labels_hand: Scoring function
        game_state: Current game state
        timeout_seconds: Optional timeout in seconds for levels 3-4

    Returns:
        List of 2 card indices [i, j] to discard
    """
    # Apply timeout wrapper for expensive levels if requested
    if timeout_seconds and dad_ai_level >= 3:
        return _run_discard_with_timeout(
            dad_labels=dad_labels,
            dad_ai_level=dad_ai_level,
            dealer_is_dad=dealer_is_dad,
            canonical_deck_labels=canonical_deck_labels,
            score_labels_hand=score_labels_hand,
            game_state=game_state,
            timeout_seconds=timeout_seconds,
        )

    # Standard path without timeout
    return _choose_discard_indices_impl(
        dad_labels=dad_labels,
        dad_ai_level=dad_ai_level,
        dealer_is_dad=dealer_is_dad,
        canonical_deck_labels=canonical_deck_labels,
        score_labels_hand=score_labels_hand,
        game_state=game_state,
    )


def _choose_discard_indices_impl(
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
        posture = _level5_posture_from_state(state)
        agent = get_bert_agent()
        agent.set_posture(posture)
        try:
            idx1, idx2 = agent.choose_discard(dad_labels, state, posture=posture)
        except TypeError:
            # Backward compatibility for older BertAgent signatures.
            idx1, idx2 = agent.choose_discard(dad_labels, state)
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
            score += LEVEL_2_INTRINSIC * _intrinsic_keep_score(kept)
            score += (LEVEL_2_DEALER_CRIB if dealer_is_dad else LEVEL_2_PONE_CRIB) * _discard_crib_score(discards)
        elif dad_ai_level == 3:
            trials = LEVEL_3_TRIALS
            total = 0.0
            for _ in range(trials):
                weights = [3.0 if _value_for_15(_parse_label(lbl)[0]) >= 10 else 1.0 for lbl in unseen_pool]
                opp_discards = random.choices(unseen_pool, weights=weights, k=2)
                rem = [lbl for lbl in unseen_pool if lbl not in opp_discards]
                if not rem:
                    continue
                starter = random.choice(rem)
                own_score = score_labels_hand(kept, starter, False)
                crib_labels = discards + opp_discards
                crib_score = score_labels_hand(crib_labels, starter, True)
                total += own_score + (crib_score if dealer_is_dad else -crib_score)
            score = total / max(1, trials)
            score += LEVEL_3_INTRINSIC * _intrinsic_keep_score(kept)
            score += (LEVEL_3_DEALER_CRIB if dealer_is_dad else LEVEL_3_PONE_CRIB) * _discard_crib_score(discards)
        else:
            # Brutal mode: deeper simulation with heavier intrinsic weighting.
            trials = LEVEL_4_TRIALS
            total = 0.0
            for _ in range(trials):
                weights = [3.0 if _value_for_15(_parse_label(lbl)[0]) >= 10 else 1.0 for lbl in unseen_pool]
                opp_discards = random.choices(unseen_pool, weights=weights, k=2)
                rem = [lbl for lbl in unseen_pool if lbl not in opp_discards]
                if not rem:
                    continue
                starter = random.choice(rem)
                own_score = score_labels_hand(kept, starter, False)
                crib_labels = discards + opp_discards
                crib_score = score_labels_hand(crib_labels, starter, True)
                total += own_score + (crib_score if dealer_is_dad else -crib_score)
            score = total / max(1, trials)
            score += LEVEL_4_INTRINSIC * _intrinsic_keep_score(kept)
            score += (LEVEL_4_DEALER_CRIB if dealer_is_dad else LEVEL_4_PONE_CRIB) * _discard_crib_score(discards)

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
                (ANALYSIS_DEALER_CRIB if dealer_is_player else ANALYSIS_PONE_CRIB) * _discard_crib_score(discards)
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
        if span <= PERCENTILE_EPSILON:
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
        posture = _level5_posture_from_state(state)
        agent = get_bert_agent()
        agent.set_posture(posture)
        try:
            return agent.choose_pegging(hand_labels, current_total, state, posture=posture)
        except TypeError:
            # Backward compatibility for older BertAgent signatures.
            return agent.choose_pegging(hand_labels, current_total, state)

    best_idx = legal[0]
    best_score = float("-inf")
    posture = _level5_posture_from_state(game_state) if game_state else "balanced"

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
        if posture == "cutthroat":
            score += immediate * 1.35
        elif posture == "aggressive":
            score += immediate * 1.15
        elif posture == "deliberate":
            score = immediate * 0.9 + shape_bonus * 1.4

        if dad_ai_level >= 3 and estimate_opponent_reply_risk is not None:
            score -= OPPONENT_REPLY_RISK_DISCOUNT * estimate_opponent_reply_risk(trial_pile)

        if dad_ai_level >= 4:
            # Endgame awareness: when close to 121, prioritize immediate points.
            if own_score is not None and own_score >= ENDGAME_THRESHOLD:
                score += ENDGAME_IMMEDIATE_BONUS * immediate
            if opp_score is not None and opp_score >= ENDGAME_THRESHOLD and immediate == 0:
                score -= ENDGAME_PREVENTION_PENALTY

            # Early-round discipline in brutal mode.
            if own_cards_remaining is not None and own_cards_remaining >= 3 and immediate == 0:
                val = value_for_15(parse_label(label)[0])
                if val >= 10:
                    score -= EARLY_DISCIPLINE_PENALTY

        if score > best_score:
            best_score = score
            best_idx = idx

    return best_idx
