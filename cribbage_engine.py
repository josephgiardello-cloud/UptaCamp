from __future__ import annotations

import random
from collections.abc import Sequence
from itertools import combinations
from typing import Any

import ai_strategy
import cards as cribbage_cards
from game_state import GameState


class CribbageEngine:
    GAME_POINT = 121

    def __init__(self, *, seed: int | None = None):
        self.state = GameState()
        self.current_phase = self.state.phase
        self.players: list[str] = []
        self.ai_agents: dict[str, Any] = {}
        self.deck: list[cribbage_cards.Card] = []
        self.voice: Any = None
        self._rng = random.Random(seed)

    def _sync_phase(self, phase: str) -> None:
        self.current_phase = phase
        self.state.phase = phase

    def _declare_winner_if_reached(self) -> bool:
        p0 = int(self.state.scores[0])
        p1 = int(self.state.scores[1])
        if p0 < self.GAME_POINT and p1 < self.GAME_POINT:
            return False

        if p0 > p1:
            self.state.winner = 0
            self.state.message = f"{self.state.player_name or 'You'} wins at {self.GAME_POINT}!"
        elif p1 > p0:
            self.state.winner = 1
            self.state.message = f"{self.state.ai_name or 'Bert'} wins at {self.GAME_POINT}!"
        else:
            self.state.winner = None
            self.state.message = f"Tie game at {self.GAME_POINT}."

        self._sync_phase("game_over")
        return True

    def _add_points(self, player_idx: int, points: int) -> int:
        pts = max(0, int(points))
        if pts <= 0:
            return 0
        current = int(self.state.scores[player_idx])
        room = max(0, self.GAME_POINT - current)
        awarded = min(pts, room)
        self.state.scores[player_idx] = current + awarded
        self._declare_winner_if_reached()
        return awarded

    @staticmethod
    def _card_to_label(card: cribbage_cards.Card) -> str:
        rank = cribbage_cards._normalize_rank(card.rank)
        rank_label = {
            "A": "ace",
            "J": "jack",
            "Q": "queen",
            "K": "king",
        }.get(rank, rank.lower())
        return f"{rank_label}_of_{str(card.suit).strip().lower()}"

    @staticmethod
    def _to_label(card_or_label: Any) -> str:
        if isinstance(card_or_label, cribbage_cards.Card):
            return CribbageEngine._card_to_label(card_or_label)
        return str(getattr(card_or_label, "label", card_or_label))

    @staticmethod
    def _to_card(card_or_label: Any) -> cribbage_cards.Card:
        if isinstance(card_or_label, cribbage_cards.Card):
            return card_or_label
        return cribbage_cards.label_to_card(CribbageEngine._to_label(card_or_label))

    def _create_deck(self) -> None:
        suits = ["Clubs", "Diamonds", "Hearts", "Spades"]
        ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
        self.deck = [cribbage_cards.Card(rank, suit) for suit in suits for rank in ranks]

    def _shuffle_and_deal(self) -> None:
        self._rng.shuffle(self.deck)
        self.state.player_hand = list(self.deck[:6])
        self.state.ai_hand = list(self.deck[6:12])
        self.state.stock_labels = [self._card_to_label(c) for c in self.deck[12:]]

    def set_seed(self, seed: int) -> None:
        self._rng.seed(seed)

    def start_new_game(
        self,
        player_name: str = "You",
        opponent_type: str = "Bert",
        *,
        seed: int | None = None,
    ) -> GameState:
        if seed is not None:
            self._rng.seed(seed)
        self.state.reset()
        self.players = [player_name, opponent_type]
        self.ai_agents = {"opponent": opponent_type}
        self.state.player_name = player_name
        self.state.ai_name = opponent_type
        self.state.ai_last_decision_reason = ""
        self.state.scores = [0, 0]
        self.state.winner = None
        self.state.dealer = 0
        self._create_deck()
        self._shuffle_and_deal()
        self.state.crib = []
        self.state.player_kept = []
        self.state.ai_kept = []
        self.state.pegging_pile = []
        self.state.pegging_passes = [False, False]
        self.state.last_pegging_player = None
        self.state.player_turn = 1 - self.state.dealer
        self.state.starter_card = None
        self.state.message = "Select 2 cards to discard to the crib."
        self._sync_phase("discard")
        return self.state

    def start_next_round(self) -> GameState:
        self.state.dealer = 1 - int(self.state.dealer)
        self.state.winner = None
        self.state.ai_last_decision_reason = ""
        self._create_deck()
        self._shuffle_and_deal()
        self.state.crib = []
        self.state.player_kept = []
        self.state.ai_kept = []
        self.state.pegging_pile = []
        self.state.pegging_passes = [False, False]
        self.state.last_pegging_player = None
        self.state.player_turn = 1 - self.state.dealer
        self.state.starter_card = None
        self.state.message = "Select 2 cards to discard to the crib."
        self._sync_phase("discard")
        return self.state

    def _ai_discard_indices(self) -> list[int]:
        hand_labels = [self._to_label(c) for c in self.state.ai_hand]
        level = int(getattr(self.state, "dad_ai_level", 2))
        try:
            picked = ai_strategy.choose_discard_indices(
                dad_labels=hand_labels,
                dad_ai_level=level,
                dealer_is_dad=bool(int(self.state.dealer) == 1),
                canonical_deck_labels=self._canonical_deck_labels(),
                score_labels_hand=self._score_labels_hand,
                game_state=self.state,
            )
            if len(picked) == 2:
                i1, i2 = int(picked[0]), int(picked[1])
                if (
                    i1 != i2
                    and 0 <= i1 < len(self.state.ai_hand)
                    and 0 <= i2 < len(self.state.ai_hand)
                ):
                    labels = sorted([hand_labels[i1], hand_labels[i2]])
                    self.state.ai_last_decision_reason = (
                        f"L{level} discard: kept pressure, tossed {labels[0]} and {labels[1]}."
                    )
                    return sorted([i1, i2], reverse=True)
        except Exception:
            pass

        indexed = list(enumerate(self.state.ai_hand))
        indexed.sort(key=lambda pair: cribbage_cards.value_for_fifteen(self._to_card(pair[1]).rank))
        chosen = sorted([indexed[0][0], indexed[1][0]], reverse=True)
        labels = sorted([self._to_label(self.state.ai_hand[chosen[0]]), self._to_label(self.state.ai_hand[chosen[1]])])
        self.state.ai_last_decision_reason = (
            f"L{level} discard fallback: tossed lowest-value cards {labels[0]} and {labels[1]}."
        )
        return chosen

    @staticmethod
    def _canonical_deck_labels() -> list[str]:
        suits = ["clubs", "diamonds", "hearts", "spades"]
        ranks = ["ace", "2", "3", "4", "5", "6", "7", "8", "9", "10", "jack", "queen", "king"]
        return [f"{rank}_of_{suit}" for suit in suits for rank in ranks]

    def _score_labels_hand(self, hand_labels: list[str], starter_label: str, is_crib: bool) -> int:
        hand_model = [cribbage_cards.label_to_card(lbl) for lbl in hand_labels]
        starter_model = cribbage_cards.label_to_card(starter_label)
        total, _ = cribbage_cards.score_hand(hand_model, starter_model, is_crib=is_crib)
        return int(total)

    def ai_pegging_move(self) -> int | None:
        hand_labels = [self._to_label(c) for c in self.state.ai_hand]
        current_labels = [self._to_label(c) for c in self.state.pegging_pile]
        level = int(getattr(self.state, "dad_ai_level", 2))
        picked = ai_strategy.choose_pegging_index(
            hand_labels=hand_labels,
            current_total=self._current_pegging_total(),
            dad_ai_level=level,
            value_for_15=cribbage_cards.value_for_fifteen,
            parse_label=cribbage_cards.parse_card_label,
            score_pegging_play=cribbage_cards.score_pegging_play,
            label_card_factory=cribbage_cards.label_to_card,
            current_pegging_labels=current_labels,
            game_state=self.state,
        )
        if picked is None:
            self.state.ai_last_decision_reason = f"L{level} pegging: no legal play, calling go."
            return None
        idx = int(picked)
        valid = self.get_valid_moves() if self.state.phase == "pegging" and int(self.state.player_turn) == 1 else []
        if idx in valid:
            label = hand_labels[idx]
            rank, _ = cribbage_cards.parse_card_label(label)
            total_after = self._current_pegging_total() + cribbage_cards.value_for_fifteen(rank)
            self.state.ai_last_decision_reason = (
                f"L{level} pegging: played {label} for total {total_after}."
            )
            return idx

        if valid:
            total = self._current_pegging_total()
            best_idx = int(valid[0])
            best_score = float("-inf")
            for cand in valid:
                label = hand_labels[int(cand)]
                rank, _ = cribbage_cards.parse_card_label(label)
                trial_total = total + cribbage_cards.value_for_fifteen(rank)
                trial_pile = list(self.state.pegging_pile) + [cribbage_cards.label_to_card(label)]
                immediate = float(cribbage_cards.score_pegging_play(trial_pile))
                score = immediate
                if trial_total in {15, 31}:
                    score += 2.0
                if trial_total in {11, 16, 21, 24}:
                    score += 0.6
                if trial_total in {5, 10, 20, 26}:
                    score -= 0.6
                score -= abs(15 - trial_total) * 0.03
                if score > best_score or (score == best_score and int(cand) < best_idx):
                    best_score = score
                    best_idx = int(cand)

            label = hand_labels[best_idx]
            rank, _ = cribbage_cards.parse_card_label(label)
            total_after = total + cribbage_cards.value_for_fifteen(rank)
            self.state.ai_last_decision_reason = (
                f"L{level} pegging fallback: strategy pick invalid, played {label} for total {total_after}."
            )
            return best_idx

        self.state.ai_last_decision_reason = f"L{level} pegging: no legal play, calling go."
        return None

    def process_discard(self, player_cards_to_crib: Sequence[int]) -> bool:
        if self.state.phase != "discard":
            return False

        selected = sorted({int(i) for i in player_cards_to_crib}, reverse=True)
        if len(selected) != 2:
            return False
        if any(i < 0 or i >= len(self.state.player_hand) for i in selected):
            return False

        for i in selected:
            self.state.crib.append(self.state.player_hand.pop(i))

        for i in self._ai_discard_indices():
            self.state.crib.append(self.state.ai_hand.pop(i))

        self.state.player_kept = list(self.state.player_hand)
        self.state.ai_kept = list(self.state.ai_hand)
        if not self.state.stock_labels:
            self.state.message = "No starter card available. Round cannot continue."
            self._sync_phase("end")
            return False
        self.state.starter_card = self.state.stock_labels.pop(0)
        starter_rank, _ = cribbage_cards.parse_card_label(self.state.starter_card)
        heels_awarded = 0
        if starter_rank == "jack":
            heels_awarded = self._add_points(int(self.state.dealer), 2)
            if heels_awarded > 0 and self.state.phase != "game_over":
                dealer_name = self.state.ai_name if int(self.state.dealer) == 1 else (self.state.player_name or "You")
                self.state.message = f"{dealer_name} scores 2 for his heels."
        if self.state.phase == "game_over":
            return True
        self.state.pegging_pile = []
        self.state.pegging_passes = [False, False]
        self.state.last_pegging_player = None
        self.state.player_turn = 1 - self.state.dealer
        if heels_awarded > 0:
            self.state.message = f"{self.state.message} Pegging phase begins!"
        else:
            self.state.message = "Pegging phase begins!"
        self._sync_phase("pegging")
        return True

    # Canonical aliases so external orchestration paths do not diverge.
    def handle_discard(self, selected_indices: Sequence[int]) -> bool:
        return self.process_discard(selected_indices)

    def _current_pegging_total(self) -> int:
        return cribbage_cards.pegging_total(self.state.pegging_pile)

    def get_valid_moves(self) -> list[Any]:
        if self.state.phase == "discard":
            hand_size = len(self.state.player_hand)
            return [list(pair) for pair in combinations(range(hand_size), 2)]

        if self.state.phase == "pegging":
            hand = self.state.player_hand if self.state.player_turn == 0 else self.state.ai_hand
            total = self._current_pegging_total()
            valid: list[int] = []
            for idx, card in enumerate(hand):
                rank, _ = cribbage_cards.parse_card_label(self._to_label(card))
                if total + cribbage_cards.value_for_fifteen(rank) <= 31:
                    valid.append(idx)
            return valid

        return []

    def pass_pegging_turn(self, player_idx: int) -> dict[str, Any]:
        if self.state.phase != "pegging":
            return {"ok": False, "reason": "invalid_phase"}
        if player_idx not in (0, 1):
            return {"ok": False, "reason": "invalid_player"}

        self.state.pegging_passes[player_idx] = True
        other = 1 - player_idx
        if self.state.pegging_passes[other]:
            current_total = self._current_pegging_total()
            points = 0
            if (
                self.state.pegging_pile
                and current_total < 31
                and self.state.last_pegging_player is not None
            ):
                points = 1
                points = self._add_points(self.state.last_pegging_player, 1)
            self.state.pegging_pile = []
            self.state.pegging_passes = [False, False]
            if self.state.last_pegging_player is not None:
                self.state.player_turn = 1 - self.state.last_pegging_player
            return {"ok": True, "go_completed": True, "points": points}

        self.state.player_turn = other
        return {"ok": True, "go_completed": False, "points": 0}

    def process_pegging_play(self, card: int | Any) -> dict[str, Any]:
        if self.state.phase != "pegging":
            return {"ok": False, "reason": "invalid_phase"}

        hand = self.state.player_hand if self.state.player_turn == 0 else self.state.ai_hand
        valid_moves = self.get_valid_moves()
        if card == "go":
            return self.pass_pegging_turn(self.state.player_turn)
        if not valid_moves:
            result = self.pass_pegging_turn(self.state.player_turn)
            return {"ok": False, "reason": "go", **result}

        if isinstance(card, int):
            card_index = card
        else:
            target = self._to_label(card)
            card_index = next(
                (i for i, c in enumerate(hand) if self._to_label(c) == target),
                -1,
            )

        if card_index not in valid_moves:
            return {"ok": False, "reason": "invalid_move"}

        played = hand.pop(card_index)
        self.state.pegging_pile.append(played)
        self.state.pegging_passes = [False, False]
        raw_points = cribbage_cards.score_pegging_play(self.state.pegging_pile)
        scorer = self.state.player_turn
        points = self._add_points(scorer, raw_points)
        total = self._current_pegging_total()
        self.state.last_pegging_player = scorer

        if self.state.phase == "game_over":
            return {
                "ok": True,
                "points": points,
                "total": total,
                "next_turn": self.state.player_turn,
            }

        if total == 31:
            self.state.pegging_pile = []
            self.state.pegging_passes = [False, False]

        if not self.state.player_hand and not self.state.ai_hand:
            if self.state.pegging_pile and total != 31 and self.state.last_pegging_player is not None:
                self._add_points(self.state.last_pegging_player, 1)
            if self.state.phase == "game_over":
                return {
                    "ok": True,
                    "points": points,
                    "total": total,
                    "next_turn": self.state.player_turn,
                }
            self._sync_phase("counting")
        else:
            self.state.player_turn = 1 - scorer

        return {
            "ok": True,
            "points": points,
            "total": total,
            "next_turn": self.state.player_turn,
        }

    def play_pegging_card(self, player_idx: int, card_index: int) -> int:
        if self.state.player_turn != player_idx:
            return 0
        result = self.process_pegging_play(card_index)
        if not result.get("ok"):
            return 0
        return int(result.get("points", 0))

    def end_hand_counting(self) -> dict[str, Any]:
        if self.state.starter_card is None:
            self._sync_phase("end")
            return {"player": 0, "ai": 0, "crib": 0}

        starter = self._to_card(self.state.starter_card)
        player_cards = [self._to_card(c) for c in (self.state.player_kept or self.state.player_hand)]
        ai_cards = [self._to_card(c) for c in (self.state.ai_kept or self.state.ai_hand)]
        crib_cards = [self._to_card(c) for c in self.state.crib]

        p_total, p_breakdown = cribbage_cards.score_hand(player_cards, starter, is_crib=False)
        a_total, a_breakdown = cribbage_cards.score_hand(ai_cards, starter, is_crib=False)
        c_total, c_breakdown = (
            cribbage_cards.score_hand(crib_cards, starter, is_crib=True) if len(crib_cards) == 4 else (0, [])
        )

        awarded_player = self._add_points(0, p_total)
        if self.state.phase == "game_over":
            return {
                "player": awarded_player,
                "ai": 0,
                "crib": 0,
                "player_breakdown": p_breakdown,
                "ai_breakdown": [],
                "crib_breakdown": [],
            }

        awarded_ai = self._add_points(1, a_total)
        if self.state.phase == "game_over":
            return {
                "player": awarded_player,
                "ai": awarded_ai,
                "crib": 0,
                "player_breakdown": p_breakdown,
                "ai_breakdown": a_breakdown,
                "crib_breakdown": [],
            }

        awarded_crib = self._add_points(self.state.dealer, c_total)
        if self.state.phase != "game_over":
            self._sync_phase("end")
        return {
            "player": awarded_player,
            "ai": awarded_ai,
            "crib": awarded_crib,
            "player_breakdown": p_breakdown,
            "ai_breakdown": a_breakdown,
            "crib_breakdown": c_breakdown,
        }
