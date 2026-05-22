from __future__ import annotations

import random
from collections.abc import Sequence
from itertools import combinations
from typing import Any

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
        indexed = list(enumerate(self.state.ai_hand))
        indexed.sort(key=lambda pair: cribbage_cards.value_for_fifteen(self._to_card(pair[1]).rank))
        return sorted([indexed[0][0], indexed[1][0]], reverse=True)

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
        self.state.pegging_pile = []
        self.state.pegging_passes = [False, False]
        self.state.last_pegging_player = None
        self.state.player_turn = 1 - self.state.dealer
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
