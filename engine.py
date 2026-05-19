from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

import ai_strategy
import cards as cribbage_cards


@dataclass
class GameState:
    phase: str = "intro"
    dealer: int = 0
    scores: list[int] = field(default_factory=lambda: [0, 0])
    player_hand: list[Any] = field(default_factory=list)
    ai_hand: list[Any] = field(default_factory=list)
    crib: list[Any] = field(default_factory=list)
    pegging_pile: list[Any] = field(default_factory=list)
    player_kept: list[Any] = field(default_factory=list)
    ai_kept: list[Any] = field(default_factory=list)
    starter_card: str | None = None
    player_turn: int = 0
    pegging_passes: list[bool] = field(default_factory=lambda: [False, False])
    last_pegging_player: int | None = None
    message: str = ""
    dad_ai_level: int = 2
    stock_labels: list[str] = field(default_factory=list)


class CribbageEngine:
    def __init__(self):
        self.state = GameState()
        self.score_func = cribbage_cards.score_hand

    @staticmethod
    def _label(card_obj: Any) -> str:
        return getattr(card_obj, "label", str(card_obj))

    def _labels(self, cards: Sequence[Any]) -> list[str]:
        return [self._label(c) for c in cards]

    def start_new_game(
        self,
        player_hand: Sequence[Any],
        ai_hand: Sequence[Any],
        stock_labels: Sequence[str],
        dealer: int = 0,
    ) -> None:
        self.state.phase = "discard"
        self.state.dealer = dealer
        self.state.scores = [0, 0]
        self.state.player_hand = list(player_hand)
        self.state.ai_hand = list(ai_hand)
        self.state.crib = []
        self.state.pegging_pile = []
        self.state.player_kept = []
        self.state.ai_kept = []
        self.state.starter_card = None
        self.state.player_turn = 0
        self.state.pegging_passes = [False, False]
        self.state.last_pegging_player = None
        self.state.message = "Select 2 cards to discard to the crib."
        self.state.stock_labels = list(stock_labels)

    def start_next_round(
        self,
        player_hand: Sequence[Any],
        ai_hand: Sequence[Any],
        stock_labels: Sequence[str],
    ) -> None:
        self.state.phase = "discard"
        self.state.dealer = 1 - self.state.dealer
        self.state.player_hand = list(player_hand)
        self.state.ai_hand = list(ai_hand)
        self.state.crib = []
        self.state.pegging_pile = []
        self.state.player_kept = []
        self.state.ai_kept = []
        self.state.starter_card = None
        self.state.player_turn = 1 - self.state.dealer
        self.state.pegging_passes = [False, False]
        self.state.last_pegging_player = None
        self.state.message = "New Round. Select 2 cards to discard."
        self.state.stock_labels = list(stock_labels)

    def handle_discard(self, selected_indices: Sequence[int]) -> None:
        selected = sorted(set(selected_indices), reverse=True)
        if len(selected) != 2:
            return
        if any(i < 0 or i >= len(self.state.player_hand) for i in selected):
            return

        for i in selected:
            self.state.crib.append(self.state.player_hand.pop(i))

        dad_discards = self.ai_discard()
        for i in sorted(dad_discards, reverse=True):
            if 0 <= i < len(self.state.ai_hand):
                self.state.crib.append(self.state.ai_hand.pop(i))

        self.state.player_kept = self.state.player_hand.copy()
        self.state.ai_kept = self.state.ai_hand.copy()

        self.state.starter_card = None
        if self.state.stock_labels:
            self.state.starter_card = self.state.stock_labels.pop(0)

        self.state.phase = "pegging"
        self.state.player_turn = 1 - self.state.dealer
        self.state.pegging_passes = [False, False]
        self.state.last_pegging_player = None
        self.state.message = "Pegging phase begins!"

    def play_pegging_card(
        self,
        player_idx: int,
        card_index: int,
        score_pegging_play: Callable[[Sequence[Any]], int],
        value_for_15: Callable[[str], int],
        parse_label: Callable[[str], tuple[str, str]],
        player_name: str = "Player",
    ) -> int:
        hand = self.state.player_hand if player_idx == 0 else self.state.ai_hand
        if card_index < 0 or card_index >= len(hand):
            return 0

        card = hand.pop(card_index)
        self.state.pegging_pile.append(card)
        self.state.pegging_passes = [False, False]

        points = score_pegging_play(self.state.pegging_pile)
        self.state.scores[player_idx] += points

        name = player_name if player_idx == 0 else "Dad"
        point_note = f" (+{points})" if points else ""

        total = sum(value_for_15(parse_label(self._label(c))[0]) for c in self.state.pegging_pile)
        if total == 31:
            self.state.message = f"{name} played 31{point_note}. New count."
            self.state.pegging_pile.clear()
            self.state.player_turn = 1 - player_idx
        else:
            self.state.message = f"{name} pegs{point_note}. " + (
                "Dad's turn." if player_idx == 0 else "Your turn."
            )
            self.state.player_turn = 1 - player_idx

        self.state.last_pegging_player = player_idx
        return points

    def ai_discard(self) -> list[int]:
        dad_labels = self._labels(self.state.ai_hand)
        return ai_strategy.choose_discard_indices(
            dad_labels=dad_labels,
            dad_ai_level=self.state.dad_ai_level,
            dealer_is_dad=(self.state.dealer == 1),
            canonical_deck_labels=self._canonical_deck_labels(),
            score_labels_hand=self._score_labels_hand,
        )

    def ai_pegging_move(
        self,
        current_total: int,
        value_for_15: Callable[[str], int],
        parse_label: Callable[[str], tuple[str, str]],
        score_pegging_play: Callable[[Sequence[Any]], int],
        label_card_factory: Callable[[str], Any],
        estimate_opponent_reply_risk: Callable[[Sequence[Any]], float] | None = None,
    ) -> int | None:
        return ai_strategy.choose_pegging_index(
            hand_labels=self._labels(self.state.ai_hand),
            current_total=current_total,
            dad_ai_level=self.state.dad_ai_level,
            value_for_15=value_for_15,
            parse_label=parse_label,
            score_pegging_play=score_pegging_play,
            label_card_factory=label_card_factory,
            current_pegging_labels=self._labels(self.state.pegging_pile),
            estimate_opponent_reply_risk=estimate_opponent_reply_risk,
        )

    def finalize_pegging_if_complete(
        self,
        get_pegging_total: Callable[[], int],
    ) -> bool:
        if self.state.player_hand or self.state.ai_hand:
            return False

        if (
            self.state.pegging_pile
            and get_pegging_total() != 31
            and self.state.last_pegging_player is not None
        ):
            self.state.scores[self.state.last_pegging_player] += 1
            self.state.message = (
                "Last card for 1 point. Counting hands."
                if self.state.last_pegging_player == 0
                else "Dad gets last card for 1 point. Counting hands."
            )
        else:
            self.state.message = "Counting hands."

        self.state.phase = "counting"
        return True

    def count_hands(self, label_to_model_card: Callable[[str], Any]) -> dict:
        if self.state.starter_card is None:
            self.state.phase = "end"
            self.state.message = "No starter card available. Press R to reset."
            return {"player": 0, "ai": 0, "crib": 0}

        starter = label_to_model_card(self.state.starter_card)
        p1 = [label_to_model_card(self._label(c)) for c in self.state.player_kept]
        p2 = [label_to_model_card(self._label(c)) for c in self.state.ai_kept]
        crib_cards = [label_to_model_card(self._label(c)) for c in self.state.crib]

        p1_total, p1_breakdown = self.score_func(p1, starter, is_crib=False)
        p2_total, p2_breakdown = self.score_func(p2, starter, is_crib=False)
        crib_total, crib_breakdown = (
            self.score_func(crib_cards, starter, is_crib=True) if len(crib_cards) == 4 else (0, [])
        )

        self.state.scores[0] += p1_total
        self.state.scores[1] += p2_total
        self.state.scores[self.state.dealer] += crib_total

        return {
            "player": p1_total,
            "ai": p2_total,
            "crib": crib_total,
            "player_breakdown": p1_breakdown,
            "ai_breakdown": p2_breakdown,
            "crib_breakdown": crib_breakdown,
        }

    @staticmethod
    def _canonical_deck_labels() -> list[str]:
        suits = ["clubs", "diamonds", "hearts", "spades"]
        ranks = ["ace", "2", "3", "4", "5", "6", "7", "8", "9", "10", "jack", "queen", "king"]
        return [f"{rank}_of_{suit}" for suit in suits for rank in ranks]

    def _score_labels_hand(self, hand_labels: list[str], starter_label: str, is_crib: bool) -> int:
        hand_model = [self._label_to_model_card(lbl) for lbl in hand_labels]
        starter_model = self._label_to_model_card(starter_label)
        total, _ = self.score_func(hand_model, starter_model, is_crib=is_crib)
        return cast(int, total)

    @staticmethod
    def _label_to_model_card(label: str) -> cribbage_cards.Card:
        return cribbage_cards.label_to_card(label)

    @staticmethod
    def _parse_label(label: str) -> tuple[str, str]:
        return cribbage_cards.parse_card_label(label)
