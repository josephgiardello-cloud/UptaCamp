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

    def __init__(self, learning_rate: float = 0.12, discount: float = 0.93, epsilon: float = 0.18):
        self.q_table: defaultdict[tuple[str, Any], float] = defaultdict(float)
        self.lr = float(learning_rate)
        self.gamma = float(discount)
        self.epsilon = float(epsilon)
        self._trajectory: list[tuple[str, Any]] = []
        self.games_played = 0
        self.posture = "balanced"

    def set_posture(self, posture: str) -> None:
        valid = {"balanced", "aggressive", "deliberate", "cutthroat"}
        self.posture = posture if posture in valid else "balanced"

    def get_posture_from_score(self, bert_score: int, player_score: int) -> str:
        """Map score gap to play posture for strategy/dialogue sync.

        Gap is bert_score - player_score.
        """
        gap = int(bert_score) - int(player_score)
        if gap <= -22:
            return "cutthroat"
        if gap <= -12:
            return "aggressive"
        if gap >= 18:
            return "deliberate"
        if gap >= 9:
            return "balanced"
        return "balanced"

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

    def _discard_posture_bonus(
        self,
        hand_labels: Sequence[str],
        action: tuple[int, int],
        state: GameState,
        posture: str | None = None,
    ) -> float:
        posture = posture or self.posture
        if posture == "balanced":
            return 0.0

        keep_idxs = [i for i in range(len(hand_labels)) if i not in action]
        keep_vals = [
            cards.value_for_fifteen(cards.parse_card_label(hand_labels[i])[0]) for i in keep_idxs
        ]
        discard_vals = [
            cards.value_for_fifteen(cards.parse_card_label(hand_labels[i])[0]) for i in action
        ]

        low_keep = sum(1 for v in keep_vals if v <= 5)
        fives_keep = sum(1 for v in keep_vals if v == 5)
        discard_crib_risk = sum(1 for v in discard_vals if v in {5, 10})

        if posture == "cutthroat":
            # High-pressure catch-up mode: keep volatile scorers and punish crib leaks.
            return 0.28 * low_keep + 0.48 * fives_keep - 0.15 * discard_crib_risk

        if posture == "aggressive":
            # Chase volatile scoring by preserving low/five-heavy pegging potential.
            return 0.24 * low_keep + 0.42 * fives_keep

        # deliberate: reduce obvious crib leaks and prefer steadier keeps.
        dealer_is_bert = state.dealer == 1
        crib_risk_penalty = -0.22 * discard_crib_risk
        if dealer_is_bert:
            crib_risk_penalty *= -0.4  # Dealer can tolerate/select for crib value more.
        return crib_risk_penalty + 0.06 * low_keep

    def choose_discard(
        self,
        hand_labels: Sequence[str],
        state: GameState,
        posture: str | None = None,
    ) -> tuple[int, int]:
        from itertools import combinations

        actions = list(combinations(range(len(hand_labels)), 2))
        if not actions:
            return (0, 1)

        posture = posture or self.posture
        state_key = self._discard_state_key(hand_labels, state)
        if random.random() < self.epsilon:
            action = random.choice(actions)
        else:
            action = max(
                actions,
                key=lambda a: self.q_table[(state_key, a)]
                + self._discard_posture_bonus(hand_labels, a, state, posture),
            )

        self._trajectory.append((state_key, action))
        return action

    def choose_pegging(
        self,
        hand_labels: Sequence[str],
        current_total: int,
        state: GameState,
        posture: str | None = None,
    ) -> int | None:
        legal = [
            i
            for i, lbl in enumerate(hand_labels)
            if current_total + cards.value_for_fifteen(cards.parse_card_label(lbl)[0]) <= 31
        ]
        if not legal:
            return None

        posture = posture or self.posture
        state_key = self._pegging_state_key(hand_labels, current_total, state)
        if random.random() < self.epsilon:
            action = random.choice(legal)
        else:
            def _pegging_posture_bonus(idx: int) -> float:
                rank = cards.parse_card_label(hand_labels[idx])[0]
                val = cards.value_for_fifteen(rank)
                new_total = current_total + val

                if posture in {"aggressive", "cutthroat"}:
                    bonus = 0.0
                    if new_total >= 24:
                        bonus += 0.45
                    if val <= 5:
                        bonus += 0.24
                    if posture == "cutthroat" and new_total in {26, 27, 28, 29, 30, 31}:
                        bonus += 0.18
                    return bonus

                if posture == "deliberate":
                    bonus = 0.0
                    if new_total in {16, 17, 18, 24}:
                        bonus += 0.22
                    if val == 5 and current_total == 0:
                        bonus -= 0.36
                    return bonus

                return 0.0

            action = max(legal, key=lambda i: self.q_table[(state_key, i)] + _pegging_posture_bonus(i))

        self._trajectory.append((state_key, action))
        return action

    def end_of_hand_update(self, hand_reward: float) -> None:
        """Apply a discounted terminal-reward update over trajectory."""
        if not self._trajectory:
            return

        self.games_played += 1
        effective_lr = self.lr * (0.999 ** (self.games_played // 50))
        target = float(hand_reward)
        for depth, (state_key, action) in enumerate(reversed(self._trajectory)):
            decay = self.gamma**depth
            td_target = target * decay
            old = self.q_table[(state_key, action)]
            self.q_table[(state_key, action)] = old + effective_lr * (td_target - old)
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


def encode_game_state_as_vector(
    hand_labels: Sequence[str],
    current_total: int,
    state: GameState,
    state_type: str = "pegging",
) -> list[float]:
    """Encode game state as fixed-size feature vector for neural network.

    Feature vector (20 dims total):
    - [0-5]: Hand card values (sorted, padded with 0s to 6 cards)
    - [6]: Dealer flag (1.0 if dealer, 0.0)
    - [7-8]: Scores normalized to [0, 1] range (own_score / 121, opp_score / 121)
    - [9]: Pegging total normalized to [0, 1] range (current_total / 31)
    - [10]: Last card value in pegging pile (0-10 scale)
    - [11]: Remaining cards in deck (0-52 scale)
    - [12-13]: Pass flags for players [0, 1] (1.0 if passed, 0.0)
    - [14-19]: Reserved for phase encoding (one-hot: discard, pegging, counting, end)

    Args:
        hand_labels: Card labels in hand
        current_total: Current pegging total (0-31)
        state: GameState object
        state_type: "discard", "pegging", "counting", "end"

    Returns:
        List of 20 floats suitable for neural network input
    """
    vector: list[float] = []

    # Hand values (6 dims)
    hand_vals = []
    for lbl in hand_labels[:6]:
        rank, _ = cards.parse_card_label(lbl)
        val = cards.value_for_fifteen(rank)
        hand_vals.append(float(val))
    # Pad to 6 dims
    while len(hand_vals) < 6:
        hand_vals.append(0.0)
    vector.extend(hand_vals[:6])

    # Dealer flag (1 dim)
    vector.append(1.0 if state.dealer == 1 else 0.0)

    # Scores normalized (2 dims)
    own_score = float(state.scores[0]) / 121.0
    opp_score = float(state.scores[1]) / 121.0
    vector.append(max(0.0, min(1.0, own_score)))
    vector.append(max(0.0, min(1.0, opp_score)))

    # Pegging total (1 dim)
    pegging_norm = float(current_total) / 31.0 if current_total else 0.0
    vector.append(max(0.0, min(1.0, pegging_norm)))

    # Last card value (1 dim)
    last_val = 0.0
    if state.pegging_pile:
        try:
            last_label = cards.card_label(state.pegging_pile[-1])
            rank, _ = cards.parse_card_label(last_label)
            last_val = float(cards.value_for_fifteen(rank)) / 10.0
        except Exception:
            pass
    vector.append(max(0.0, min(1.0, last_val)))

    # Remaining cards (1 dim)
    remaining = len(state.stock_labels) if hasattr(state, "stock_labels") else 0
    remaining_norm = float(remaining) / 52.0
    vector.append(max(0.0, min(1.0, remaining_norm)))

    # Pass flags (2 dims)
    if hasattr(state, "pegging_passes") and isinstance(state.pegging_passes, list):
        vector.append(1.0 if state.pegging_passes[0] else 0.0)
        vector.append(1.0 if state.pegging_passes[1] else 0.0)
    else:
        vector.append(0.0)
        vector.append(0.0)

    # Phase encoding one-hot (6 dims)
    phase_index = {"discard": 0, "pegging": 1, "counting": 2, "end": 3, "online_login": 4, "online_match": 5}
    phase = state.phase if state.phase in phase_index else "end"
    for i in range(6):
        vector.append(1.0 if i == phase_index[phase] else 0.0)

    return vector


class DQN:
    """Deep Q-Network for cribbage decision-making (requires PyTorch).

    Architecture:
    - Input: 20-dim feature vector (state encoding)
    - Hidden layers: 64 -> 64 neurons with ReLU
    - Output: Q-values for actions (variable based on action space)

    This is a stub that gracefully handles missing PyTorch.
    """

    def __init__(self, input_dim: int = 20, output_dim: int = 15, hidden_dim: int = 64):
        """Initialize DQN network.

        Args:
            input_dim: Input feature vector dimension (default 20)
            output_dim: Output Q-value dimension (e.g., 15 for discard, 4 for pegging)
            hidden_dim: Hidden layer dimension (default 64)
        """
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.hidden_dim = hidden_dim

        try:
            import torch
            import torch.nn as nn

            self.device = torch.device("cpu")
            self.model = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, output_dim),
            ).to(self.device)
            self.optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
            self.criterion = nn.MSELoss()
            self.torch_available = True
        except ImportError:
            self.torch_available = False
            self.model = None
            self.optimizer = None
            self.criterion = None
            self.device = None

    def forward(self, state_vector: list[float]) -> list[float] | None:
        """Compute Q-values for a state.

        Args:
            state_vector: Feature vector from encode_game_state_as_vector

        Returns:
            List of Q-values, or None if PyTorch unavailable
        """
        if not self.torch_available or self.model is None:
            return None

        try:
            import torch

            with torch.no_grad():
                state_tensor = torch.tensor(state_vector, dtype=torch.float32, device=self.device).unsqueeze(0)
                q_values = self.model(state_tensor).squeeze(0)
                return q_values.cpu().numpy().tolist()
        except Exception:
            return None

    def update(self, state_vector: list[float], target_q_values: list[float], learning_rate: float = 0.001) -> float:
        """Perform a single gradient update.

        Args:
            state_vector: Feature vector
            target_q_values: Target Q-values for this state
            learning_rate: Learning rate (unused, set in __init__)

        Returns:
            Loss value, or -1.0 if PyTorch unavailable
        """
        if not self.torch_available or self.model is None:
            return -1.0

        try:
            import torch

            state_tensor = torch.tensor(state_vector, dtype=torch.float32, device=self.device).unsqueeze(0)
            target_tensor = torch.tensor(target_q_values, dtype=torch.float32, device=self.device).unsqueeze(0)

            self.optimizer.zero_grad()
            output = self.model(state_tensor)
            loss = self.criterion(output, target_tensor)
            loss.backward()
            self.optimizer.step()

            return float(loss.item())
        except Exception:
            return -1.0

    def save_weights(self, path: str | Path) -> bool:
        """Save model weights to file.

        Args:
            path: File path to save to

        Returns:
            True if successful, False otherwise
        """
        if not self.torch_available or self.model is None:
            return False

        try:
            import torch

            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save(self.model.state_dict(), file_path)
            return True
        except Exception:
            return False

    def load_weights(self, path: str | Path) -> bool:
        """Load model weights from file.

        Args:
            path: File path to load from

        Returns:
            True if successful, False otherwise
        """
        if not self.torch_available or self.model is None:
            return False

        try:
            import torch

            file_path = Path(path)
            if not file_path.exists():
                return False
            self.model.load_state_dict(torch.load(file_path, map_location=self.device))
            return True
        except Exception:
            return False
