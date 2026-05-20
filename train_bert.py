from __future__ import annotations

import argparse
import random
from pathlib import Path

import cards
from bert_agent import BertAgent
from game_state import GameState


def _canonical_deck_labels() -> list[str]:
    suits = ["clubs", "diamonds", "hearts", "spades"]
    ranks = ["ace", "2", "3", "4", "5", "6", "7", "8", "9", "10", "jack", "queen", "king"]
    return [f"{rank}_of_{suit}" for suit in suits for rank in ranks]


def _score_labels_hand(hand_labels: list[str], starter_label: str, is_crib: bool) -> int:
    hand_model = [cards.label_to_card(lbl) for lbl in hand_labels]
    starter_model = cards.label_to_card(starter_label)
    total, _ = cards.score_hand(hand_model, starter_model, is_crib=is_crib)
    return int(total)


def _discard_episode_reward(
    hand_labels: list[str],
    discard_indices: tuple[int, int],
    dealer_is_dad: bool,
    deck_labels: list[str],
    trials: int,
) -> float:
    discard_set = set(discard_indices)
    kept = [hand_labels[i] for i in range(len(hand_labels)) if i not in discard_set]
    discards = [hand_labels[i] for i in discard_indices]

    unseen_pool = [lbl for lbl in deck_labels if lbl not in set(hand_labels)]
    if len(unseen_pool) < 3:
        return 0.0

    total = 0.0
    for _ in range(trials):
        opp_discards = random.sample(unseen_pool, 2)
        remainder = [lbl for lbl in unseen_pool if lbl not in opp_discards]
        if not remainder:
            continue
        starter = random.choice(remainder)
        own_score = _score_labels_hand(kept, starter, False)
        crib_score = _score_labels_hand(discards + opp_discards, starter, True)
        total += own_score + (crib_score if dealer_is_dad else -crib_score)

    return total / max(1, trials)


def _pegging_episode_reward(
    hand_labels: list[str],
    picked_index: int,
    current_total: int,
    current_pile: list[str],
) -> float:
    if picked_index < 0 or picked_index >= len(hand_labels):
        return -1.0

    picked = hand_labels[picked_index]
    value = cards.value_for_fifteen(cards.parse_card_label(picked)[0])
    new_total = current_total + value
    if new_total > 31:
        return -2.0

    trial_pile = list(current_pile) + [picked]
    immediate = cards.score_pegging_play(trial_pile)

    risk_penalty = 0.0
    if new_total in {5, 10, 21}:
        risk_penalty = 1.1
    elif new_total in {14, 20, 26}:
        risk_penalty = 0.5

    return float(immediate) - risk_penalty


def train(
    episodes: int,
    model_path: Path,
    learning_rate: float,
    discount: float,
    epsilon: float,
    epsilon_decay: float,
    min_epsilon: float,
) -> BertAgent:
    deck = _canonical_deck_labels()
    agent = BertAgent(learning_rate=learning_rate, discount=discount, epsilon=epsilon)

    for episode in range(episodes):
        # Discard learning sample.
        discard_state = GameState(
            dealer=random.randint(0, 1),
            scores=[random.randint(0, 120), random.randint(0, 120)],
        )
        hand = random.sample(deck, 6)
        action = agent.choose_discard(hand, discard_state)
        reward = _discard_episode_reward(
            hand_labels=hand,
            discard_indices=action,
            dealer_is_dad=(discard_state.dealer == 1),
            deck_labels=deck,
            trials=24,
        )
        agent.end_of_hand_update(reward)

        # Pegging learning sample.
        pegging_state = GameState(scores=[random.randint(0, 120), random.randint(0, 120)])
        pegging_hand = random.sample(deck, 4)
        current_total = random.randint(0, 24)
        current_pile = random.sample(deck, k=random.randint(0, 3))
        pegging_state.pegging_pile = current_pile

        idx = agent.choose_pegging(pegging_hand, current_total, pegging_state)
        if idx is not None:
            peg_reward = _pegging_episode_reward(pegging_hand, idx, current_total, current_pile)
            agent.end_of_hand_update(peg_reward)
        else:
            agent.reset_hand_memory()

        agent.epsilon = max(min_epsilon, agent.epsilon * epsilon_decay)

        if (episode + 1) % max(1, episodes // 10) == 0:
            print(
                f"episode={episode + 1}/{episodes} epsilon={agent.epsilon:.4f} "
                f"q_entries={len(agent.q_table)}"
            )

    agent.save(model_path)
    return agent


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train Bert Learning AI model")
    parser.add_argument("--episodes", type=int, default=5000)
    parser.add_argument("--model-path", type=Path, default=Path("bert_model.pkl"))
    parser.add_argument("--lr", type=float, default=0.12)
    parser.add_argument("--discount", type=float, default=0.95)
    parser.add_argument("--epsilon", type=float, default=0.35)
    parser.add_argument("--epsilon-decay", type=float, default=0.9992)
    parser.add_argument("--min-epsilon", type=float, default=0.03)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    random.seed(args.seed)

    train(
        episodes=max(1, int(args.episodes)),
        model_path=args.model_path,
        learning_rate=float(args.lr),
        discount=float(args.discount),
        epsilon=float(args.epsilon),
        epsilon_decay=float(args.epsilon_decay),
        min_epsilon=float(args.min_epsilon),
    )
    print(f"Saved model to {args.model_path}")


if __name__ == "__main__":
    main()
