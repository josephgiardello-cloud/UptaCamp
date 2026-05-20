from __future__ import annotations

import pickle
import random
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import cards
from game_state import GameState


class BertAgent:
    """Lightweight learning agent for discard and pegging choices.

    The agent uses a tabular Q-value dictionary over compact string state keys.
    We update values with a simple Monte Carlo-style hand reward at the end of
    each hand, applying the same terminal reward to each visited state-action.
    """

    def __init__(self, learning_rate: float = 0.1, discount: float = 0.95, epsilon: float = 0.2):
        self.q_table: defaultdict[tuple[str, Any], float] = defaultdict(float)
        self.lr = float(learning_rate)
        self.gamma = float(discount)
        self.epsilon = float(epsilon)
        self._trajectory: list[tuple[str, Any]] = []

    def _discard_state_key(self, hand_labels: Sequence[str], state: GameState) -> str:
        hand_vals = tuple(
            sorted(cards.value_for_fifteen(cards.parse_card_label(lbl)[0]) for lbl in hand_labels)
        )
        dealer_flag = 1 if state.dealer == 1 else 0
        scores = (int(state.scores[0]), int(state.scores[1]))
        return f"discard|{hand_vals}|dealer{dealer_flag}|scores{scores}"

    def _pegging_state_key(
        self,
        hand_labels: Sequence[str],
        current_total: int,
        state: GameState,
    ) -> str:
        hand_vals = tuple(
            sorted(cards.value_for_fifteen(cards.parse_card_label(lbl)[0]) for lbl in hand_labels)
        )
        scores = (int(state.scores[0]), int(state.scores[1]))
        last_val = 0
        if state.pegging_pile:
            last = cards.card_label(state.pegging_pile[-1])
            last_val = cards.value_for_fifteen(cards.parse_card_label(last)[0])
        return f"pegging|total{int(current_total)}|hand{hand_vals}|last{last_val}|scores{scores}"

    def choose_discard(self, hand_labels: Sequence[str], state: GameState) -> tuple[int, int]:
        from itertools import combinations

        actions = list(combinations(range(len(hand_labels)), 2))
        if not actions:
            return (0, 1)

        state_key = self._discard_state_key(hand_labels, state)
        if random.random() < self.epsilon:
            action = random.choice(actions)
        else:
            action = max(actions, key=lambda a: self.q_table[(state_key, a)])

        self._trajectory.append((state_key, action))
        return action

    def choose_pegging(
        self,
        hand_labels: Sequence[str],
        current_total: int,
        state: GameState,
    ) -> int | None:
        legal = [
            i
            for i, lbl in enumerate(hand_labels)
            if current_total + cards.value_for_fifteen(cards.parse_card_label(lbl)[0]) <= 31
        ]
        if not legal:
            return None

        state_key = self._pegging_state_key(hand_labels, current_total, state)
        if random.random() < self.epsilon:
            action = random.choice(legal)
        else:
            action = max(legal, key=lambda i: self.q_table[(state_key, i)])

        self._trajectory.append((state_key, action))
        return action

    def end_of_hand_update(self, hand_reward: float) -> None:
        """Apply a discounted terminal-reward update over trajectory."""
        if not self._trajectory:
            return

        target = float(hand_reward)
        for depth, (state_key, action) in enumerate(reversed(self._trajectory)):
            decay = self.gamma**depth
            td_target = target * decay
            old = self.q_table[(state_key, action)]
            self.q_table[(state_key, action)] = old + self.lr * (td_target - old)
        self._trajectory.clear()

    def update(
        self,
        state_key: str,
        action: tuple[int, int] | int,
        reward: float,
        next_state_key: str | None = None,
        done: bool = False,
    ) -> None:
        """Temporal-difference (TD) learning update for single step.

        Uses standard 1-step TD(0) update: Q(s,a) = Q(s,a) + lr * (r + gamma * max_a' Q(s',a') - Q(s,a))

        Args:
            state_key: Current state key
            action: Action taken (discard tuple or pegging index)
            reward: Immediate reward received
            next_state_key: Next state key (None if terminal)
            done: Whether episode is complete
        """
        old_q = self.q_table[(state_key, action)]

        if done or next_state_key is None:
            td_target = float(reward)
        else:
            # Find max Q-value for any action in next state
            next_actions = [k for k, _ in self.q_table.keys() if k == next_state_key] if next_state_key else []
            if next_actions:
                max_next_q = max(self.q_table[(next_state_key, a)] for a in next_actions)
            else:
                max_next_q = 0.0
            td_target = float(reward) + self.gamma * max_next_q

        td_error = td_target - old_q
        self.q_table[(state_key, action)] = old_q + self.lr * td_error

    def reset_hand_memory(self) -> None:
        self._trajectory.clear()

    def save(self, path: str | Path) -> None:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "q_table": dict(self.q_table),
            "lr": self.lr,
            "gamma": self.gamma,
            "epsilon": self.epsilon,
        }
        with file_path.open("wb") as f:
            pickle.dump(payload, f)

    def load(self, path: str | Path) -> None:
        file_path = Path(path)
        with file_path.open("rb") as f:
            payload = pickle.load(f)

        if isinstance(payload, dict) and "q_table" in payload:
            data = payload.get("q_table", {})
            self.lr = float(payload.get("lr", self.lr))
            self.gamma = float(payload.get("gamma", self.gamma))
            self.epsilon = float(payload.get("epsilon", self.epsilon))
        else:
            data = payload

        self.q_table = defaultdict(float, data)
