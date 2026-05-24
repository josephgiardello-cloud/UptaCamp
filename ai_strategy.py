import random
import threading
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from shutil import copy2
from typing import Any, cast

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
LEVEL_2_INTRINSIC: float = 0.18
LEVEL_2_DEALER_CRIB: float = 0.08
LEVEL_2_PONE_CRIB: float = -0.06
LEVEL_2_TOP_DISCARD_PLAY_PROB: float = 0.58
LEVEL_2_TOP_PEGGING_PLAY_PROB: float = 0.55

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

_bert_agent: BertAgent | None = None
_DEFAULT_BERT_MODEL = Path("bert_model.pkl")
_barnabas_agent: BertAgent | None = None
_DEFAULT_BARNABUS_MODEL = Path("barnabas_model.pkl")


def _normalized_ai_level(dad_ai_level: int) -> int:
    level = int(dad_ai_level)
    if level < 1:
        return 1
    if level >= 5:
        return 5
    return level


def _level4_bridge_progress(agent: BertAgent) -> float:
    games = max(0, int(getattr(agent, "games_played", 0)))
    steps = max(0, int(getattr(agent, "update_steps", 0)))
    return max(0.0, min(1.0, (games / 600.0) + (steps / 24000.0)))


def _choose_level4_bridge_action(
    *,
    agent: BertAgent,
    hard_action: Any | None,
    bert_action: Any | None,
    barnabas_action: Any | None,
) -> Any | None:
    if bert_action is None:
        return hard_action if hard_action is not None else barnabas_action

    progress = _level4_bridge_progress(agent)
    barnabas_weight = 0.10 + (0.12 * progress)  # Keep level 4 above hard but below Barnabas.
    hard_weight = 0.60 - (0.08 * progress)
    bert_bonus = 0.30 + (0.10 * progress)

    scores: dict[Any, float] = {}

    def _add(action: Any | None, weight: float) -> None:
        if action is None:
            return
        scores[action] = scores.get(action, 0.0) + float(weight)

    _add(hard_action, hard_weight)
    _add(barnabas_action, barnabas_weight)
    _add(bert_action, bert_bonus)

    # Keep level 4 above pure-hard drift when level 5 disagrees and Bert is still converging.
    if (
        progress >= 0.10
        and hard_action is not None
        and barnabas_action is not None
        and hard_action != barnabas_action
        and bert_action == hard_action
    ):
        _add(barnabas_action, 0.06 + (0.08 * progress))

    if not scores:
        return bert_action

    preference: dict[Any, int] = {
        bert_action: 3,
        barnabas_action: 2,
        hard_action: 1,
    }
    return max(scores, key=lambda action: (scores[action], preference.get(action, 0)))


def _uses_adaptive_ai(dad_ai_level: int) -> bool:
    level = _normalized_ai_level(dad_ai_level)
    return level in {4, 5}


def _agent_for_level(dad_ai_level: int) -> BertAgent:
    if _normalized_ai_level(dad_ai_level) == 5:
        return get_barnabas_agent()
    return get_bert_agent()


def _bert_posture_for_level(dad_ai_level: int, state: GameState | None) -> str:
    level = _normalized_ai_level(dad_ai_level)
    # Bert uses a stable balanced posture; Old House (level 5) uses Barnabas posture.
    if level == 4:
        return "balanced"
    if level == 5:
        return "cutthroat"
    return _level5_posture_from_state(state)


def _level5_posture_from_state(state: GameState | None) -> str:
    if state is None:
        return "balanced"
    player_score = int(state.scores[0]) if len(state.scores) > 0 else 0
    bert_score = int(state.scores[1]) if len(state.scores) > 1 else 0
    posture_agent = BertAgent()
    return posture_agent.get_posture_from_score(bert_score, player_score)


def set_bert_agent(agent: BertAgent) -> None:
    global _bert_agent
    _bert_agent = agent


def get_bert_agent() -> BertAgent:
    global _bert_agent
    if _bert_agent is None:
        _bert_agent = BertAgent()
        if _DEFAULT_BERT_MODEL.exists():
            try:
                _bert_agent.load(_DEFAULT_BERT_MODEL)
            except Exception:
                pass
    return _bert_agent


def load_bert_agent(path: str | Path = _DEFAULT_BERT_MODEL) -> BertAgent:
    agent = BertAgent()
    agent.load(path)
    set_bert_agent(agent)
    return agent


def save_bert_agent(path: str | Path = _DEFAULT_BERT_MODEL) -> None:
    agent = get_bert_agent()
    agent.save(path)


def set_barnabas_agent(agent: BertAgent) -> None:
    global _barnabas_agent
    _barnabas_agent = agent


def get_barnabas_agent() -> BertAgent:
    global _barnabas_agent
    if _barnabas_agent is None:
        _barnabas_agent = BertAgent(
            learning_rate=0.09,
            discount=0.95,
            epsilon=0.0,
            epsilon_min=0.0,
            epsilon_decay=0.9998,
        )
        try:
            if _DEFAULT_BARNABUS_MODEL.exists():
                _barnabas_agent.load(_DEFAULT_BARNABUS_MODEL)
            elif _DEFAULT_BERT_MODEL.exists():
                # Bootstrap Barnabas from Bert so Old House starts strong.
                _barnabas_agent.load(_DEFAULT_BERT_MODEL)
                _barnabas_agent.epsilon = 0.0
                _barnabas_agent.epsilon_min = 0.0
        except Exception:
            pass
    return _barnabas_agent


def load_barnabas_agent(path: str | Path = _DEFAULT_BARNABUS_MODEL) -> BertAgent:
    agent = BertAgent(
        learning_rate=0.09,
        discount=0.95,
        epsilon=0.0,
        epsilon_min=0.0,
        epsilon_decay=0.9998,
    )
    agent.load(path)
    set_barnabas_agent(agent)
    return agent


def save_barnabas_agent(path: str | Path = _DEFAULT_BARNABUS_MODEL) -> None:
    agent = get_barnabas_agent()
    agent.save(path)


def bootstrap_barnabas_from_bert(
    bert_path: str | Path = _DEFAULT_BERT_MODEL,
    barnabas_path: str | Path = _DEFAULT_BARNABUS_MODEL,
    overwrite: bool = False,
) -> bool:
    src = Path(bert_path)
    dst = Path(barnabas_path)
    if not src.exists():
        return False
    if dst.exists() and not overwrite:
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    copy2(src, dst)
    return True


def shape_end_of_hand_learning_reward(
    dad_ai_level: int,
    player_points: int,
    ai_points: int,
    crib_points: int,
    dealer_index: int,
    state: GameState | None = None,
) -> float:
    dad_ai_level = _normalized_ai_level(dad_ai_level)
    base = float(ai_points - player_points)
    base += float(crib_points if dealer_index == 1 else -crib_points)
    if dad_ai_level != 5:
        return base

    # Barnabas (Old House): pressure-heavy scoring profile with strict anti-crib leakage.
    reward = base
    reward += 0.35 * float(ai_points)
    if dealer_index == 0 and crib_points > 0:
        reward -= 0.55 * float(crib_points)
    if state is not None:
        player_score = int(state.scores[0]) if len(state.scores) > 0 else 0
        ai_score = int(state.scores[1]) if len(state.scores) > 1 else 0
        if ai_score >= 112 and ai_points > 0:
            reward += 0.45 * float(ai_points)
        if player_score >= 108 and player_points > 0:
            reward -= 0.2 * float(player_points)
    return reward


def get_reward(
    points: int,
    opponent_points_lost: int,
    action_type: str = "general",
    game_context: dict[str, Any] | None = None,
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
        dad_ai_level: Difficulty level 1-6
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
    dad_ai_level = _normalized_ai_level(dad_ai_level)

    # Apply timeout wrapper for expensive levels if requested
    if timeout_seconds and dad_ai_level >= 3 and not _uses_adaptive_ai(dad_ai_level):
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
    dad_ai_level = _normalized_ai_level(dad_ai_level)

    if len(dad_labels) != 6:
        return [0, 1]

    if dad_ai_level == 1:
        return random.sample(range(6), 2)

    if _uses_adaptive_ai(dad_ai_level):
        state = game_state or GameState()
        posture = _bert_posture_for_level(dad_ai_level, state)
        agent = _agent_for_level(dad_ai_level)
        agent.set_posture(posture)
        try:
            idx1, idx2 = agent.choose_discard(dad_labels, state, posture=posture)
        except TypeError:
            # Backward compatibility for older BertAgent signatures.
            idx1, idx2 = agent.choose_discard(dad_labels, state)
        if dad_ai_level == 4:
            # For Bert level 4, clamp decision pressure between hard baseline and Barnabas signal.
            unseen_pool = list(set(canonical_deck_labels) - set(dad_labels))
            if unseen_pool:
                hard_pick = _choose_discard_indices_impl(
                    dad_labels=dad_labels,
                    dad_ai_level=3,
                    dealer_is_dad=dealer_is_dad,
                    canonical_deck_labels=canonical_deck_labels,
                    score_labels_hand=score_labels_hand,
                    game_state=game_state,
                )
                barnabas_pick: tuple[int, int] | None = None
                barnabas = get_barnabas_agent()
                barnabas.set_posture("cutthroat")
                try:
                    b1, b2 = barnabas.choose_discard(dad_labels, state, posture="cutthroat")
                except TypeError:
                    b1, b2 = barnabas.choose_discard(dad_labels, state)
                barnabas_pick = (int(b1), int(b2))
                resolved = _choose_level4_bridge_action(
                    agent=agent,
                    hard_action=tuple(hard_pick),
                    bert_action=(int(idx1), int(idx2)),
                    barnabas_action=barnabas_pick,
                )
                if (
                    isinstance(resolved, tuple)
                    and len(resolved) == 2
                    and all(isinstance(v, int) for v in resolved)
                ):
                    resolved_pair = cast(tuple[int, int], resolved)
                    return [resolved_pair[0], resolved_pair[1]]
        if dad_ai_level == 5:
            hard_pick = _choose_discard_indices_impl(
                dad_labels=dad_labels,
                dad_ai_level=3,
                dealer_is_dad=dealer_is_dad,
                canonical_deck_labels=canonical_deck_labels,
                score_labels_hand=score_labels_hand,
                game_state=game_state,
            )

            unseen_pool = list(set(canonical_deck_labels) - set(dad_labels))

            def _score_pair(pair: tuple[int, int]) -> float:
                i1, i2 = int(pair[0]), int(pair[1])
                if i1 == i2 or i1 < 0 or i2 < 0 or i1 >= len(dad_labels) or i2 >= len(dad_labels):
                    return float("-inf")
                discard_set = {i1, i2}
                kept = [dad_labels[i] for i in range(6) if i not in discard_set]
                discards = [dad_labels[i1], dad_labels[i2]]
                if not unseen_pool:
                    return float("-inf")
                own_total = 0.0
                for starter in unseen_pool:
                    own_total += float(score_labels_hand(kept, starter, False))
                own_ev = own_total / float(len(unseen_pool))
                crib_bias = LEVEL_4_DEALER_CRIB if dealer_is_dad else LEVEL_4_PONE_CRIB
                return own_ev + (LEVEL_4_INTRINSIC * _intrinsic_keep_score(kept)) + (crib_bias * _discard_crib_score(discards))

            barnabas_pair = (int(idx1), int(idx2))
            hard_pair = (int(hard_pick[0]), int(hard_pick[1]))
            if _score_pair(hard_pair) > _score_pair(barnabas_pair):
                return [hard_pair[0], hard_pair[1]]
        return [idx1, idx2]

    unseen_pool = list(set(canonical_deck_labels) - set(dad_labels))
    if not unseen_pool:
        return random.sample(range(6), 2)

    best_idxs = [0, 1]
    best_score = float("-inf")
    level2_scored: list[tuple[float, tuple[int, int]]] = []

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
            level2_scored.append((float(score), (int(discard_idxs[0]), int(discard_idxs[1]))))
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
            # Legacy high-tier predefined simulation (e.g. Barnabas):
            # deeper search with heavier intrinsic weighting.
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

    if dad_ai_level == 2 and level2_scored and game_state is not None:
        level2_scored.sort(key=lambda row: (row[0], -row[1][0], -row[1][1]), reverse=True)
        top = level2_scored[0][1]
        if len(level2_scored) >= 3:
            second = level2_scored[1][1]
            third = level2_scored[2][1]
            choice = random.choices(
                [top, second, third],
                weights=[LEVEL_2_TOP_DISCARD_PLAY_PROB, 0.28, 0.14],
                k=1,
            )[0]
            return [int(choice[0]), int(choice[1])]
        if len(level2_scored) >= 2:
            second = level2_scored[1][1]
            choice = random.choices(
                [top, second],
                weights=[LEVEL_2_TOP_DISCARD_PLAY_PROB, 1.0 - LEVEL_2_TOP_DISCARD_PLAY_PROB],
                k=1,
            )[0]
            return [int(choice[0]), int(choice[1])]
        return [int(top[0]), int(top[1])]

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
    score_pegging_play: Callable[[Sequence[object]], int],
    label_card_factory: Callable[[str], object],
    current_pegging_labels: Sequence[str],
    estimate_opponent_reply_risk: Callable[[Sequence[object]], float] | None = None,
    own_score: int | None = None,
    opp_score: int | None = None,
    own_cards_remaining: int | None = None,
    game_state: GameState | None = None,
) -> int | None:
    dad_ai_level = _normalized_ai_level(dad_ai_level)

    legal = [
        i
        for i, label in enumerate(hand_labels)
        if current_total + value_for_15(parse_label(label)[0]) <= 31
    ]
    if not legal:
        return None

    if game_state is not None:
        if own_score is None and len(getattr(game_state, "scores", [])) > 1:
            own_score = int(game_state.scores[1])
        if opp_score is None and len(getattr(game_state, "scores", [])) > 0:
            opp_score = int(game_state.scores[0])
        if own_cards_remaining is None:
            own_cards_remaining = len(hand_labels)

    posture = _level5_posture_from_state(game_state) if game_state else "balanced"
    if dad_ai_level == 5:
        posture = "cutthroat"

    def _score_legal_choice(idx: int, fallback_posture: str) -> float:
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
        if fallback_posture == "cutthroat":
            score += immediate * 1.35
        elif fallback_posture == "aggressive":
            score += immediate * 1.15
        elif fallback_posture == "deliberate":
            score = immediate * 0.9 + shape_bonus * 1.4

        if dad_ai_level >= 3 and estimate_opponent_reply_risk is not None:
            score -= OPPONENT_REPLY_RISK_DISCOUNT * estimate_opponent_reply_risk(trial_pile)

        if dad_ai_level >= 4:
            if own_score is not None and own_score >= ENDGAME_THRESHOLD:
                score += ENDGAME_IMMEDIATE_BONUS * immediate
            if opp_score is not None and opp_score >= ENDGAME_THRESHOLD and immediate == 0:
                score -= ENDGAME_PREVENTION_PENALTY

            if own_cards_remaining is not None and own_cards_remaining >= 3 and immediate == 0:
                val = value_for_15(parse_label(label)[0])
                if val >= 10:
                    score -= EARLY_DISCIPLINE_PENALTY

        return float(score)

    def _fallback_legal_pick(fallback_posture: str) -> int:
        best_idx = int(legal[0])
        best_score = float("-inf")
        scored_moves: list[tuple[float, int]] = []

        for idx in legal:
            score = _score_legal_choice(idx, fallback_posture)
            scored_moves.append((float(score), int(idx)))

            if score > best_score:
                best_score = score
                best_idx = idx

        if dad_ai_level == 2 and len(scored_moves) >= 2:
            scored_moves.sort(key=lambda row: (row[0], -row[1]), reverse=True)
            top = scored_moves[0][1]
            second = scored_moves[1][1]
            if len(scored_moves) >= 3:
                third = scored_moves[2][1]
                pick_pool = [top, second, third]
                pick_weights = [LEVEL_2_TOP_PEGGING_PLAY_PROB, 0.22, 0.10]
            else:
                pick_pool = [top, second]
                pick_weights = [LEVEL_2_TOP_PEGGING_PLAY_PROB, 1.0 - LEVEL_2_TOP_PEGGING_PLAY_PROB]
            return int(random.choices(pick_pool, weights=pick_weights, k=1)[0])

        return int(best_idx)

    if dad_ai_level == 1:
        return random.choice(legal)

    if _uses_adaptive_ai(dad_ai_level):
        state = game_state or GameState()
        posture = _bert_posture_for_level(dad_ai_level, state)
        agent = _agent_for_level(dad_ai_level)
        agent.set_posture(posture)
        try:
            bert_pick = agent.choose_pegging(hand_labels, current_total, state, posture=posture)
        except TypeError:
            # Backward compatibility for older BertAgent signatures.
            bert_pick = agent.choose_pegging(hand_labels, current_total, state)

        if dad_ai_level == 4 and len(legal) >= 3:
            hard_pick = choose_pegging_index(
                hand_labels=hand_labels,
                current_total=current_total,
                dad_ai_level=3,
                value_for_15=value_for_15,
                parse_label=parse_label,
                score_pegging_play=score_pegging_play,
                label_card_factory=label_card_factory,
                current_pegging_labels=current_pegging_labels,
                estimate_opponent_reply_risk=estimate_opponent_reply_risk,
                own_score=own_score,
                opp_score=opp_score,
                own_cards_remaining=own_cards_remaining,
                game_state=game_state,
            )
            barnabas = get_barnabas_agent()
            barnabas.set_posture("cutthroat")
            try:
                barnabas_pick = barnabas.choose_pegging(
                    hand_labels,
                    current_total,
                    state,
                    posture="cutthroat",
                )
            except TypeError:
                barnabas_pick = barnabas.choose_pegging(hand_labels, current_total, state)

            resolved = _choose_level4_bridge_action(
                agent=agent,
                hard_action=hard_pick,
                bert_action=bert_pick,
                barnabas_action=barnabas_pick,
            )
            if resolved is not None:
                resolved_idx = int(resolved)
                # Pegging-only lift: if bridge resolves to hard but Barnabas has a
                # clearly stronger immediate scoring play, allow that upgrade.
                if (
                    hard_pick is not None
                    and resolved_idx == int(hard_pick)
                    and barnabas_pick is not None
                    and int(barnabas_pick) in legal
                    and int(barnabas_pick) != resolved_idx
                ):
                    trial_hard = [label_card_factory(lbl) for lbl in current_pegging_labels] + [
                        label_card_factory(hand_labels[resolved_idx])
                    ]
                    trial_barnabas = [label_card_factory(lbl) for lbl in current_pegging_labels] + [
                        label_card_factory(hand_labels[int(barnabas_pick)])
                    ]
                    hard_now = int(score_pegging_play(trial_hard))
                    barnabas_now = int(score_pegging_play(trial_barnabas))
                    if barnabas_now >= hard_now + 1:
                        return int(barnabas_pick)
                if resolved_idx in legal:
                    return resolved_idx

        if bert_pick is not None:
            try:
                bert_idx = int(bert_pick)
                if bert_idx in legal:
                    if dad_ai_level == 5:
                        baseline_idx = _fallback_legal_pick("cutthroat")
                        if _score_legal_choice(baseline_idx, "cutthroat") > _score_legal_choice(bert_idx, "cutthroat"):
                            return baseline_idx
                    return bert_idx
            except (TypeError, ValueError):
                pass

        return _fallback_legal_pick(posture)

    return _fallback_legal_pick(posture)
