from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, cast

import ai_strategy
import cards as cribbage_cards
from game_state import GameState


class CribbageEngine:
    def __init__(self, *, debug_validate: bool = False):
        self.state = GameState()
        self.voice: Any | None = None
        self.score_func = cribbage_cards.score_hand
        # Debug builds validate postconditions after mutating public methods.
        self._debug_validate = bool(debug_validate)

    def _validate_state_if_enabled(self) -> None:
        if self._debug_validate:
            self._validate_state()

    @staticmethod
    def _label(card_obj: Any) -> str:
        return getattr(card_obj, "label", str(card_obj))

    def _labels(self, cards: Sequence[Any]) -> list[str]:
        return [self._label(c) for c in cards]

    def _dealer_name(self) -> str:
        return "Bert" if self.state.dad_ai_level in (4, 5) else "AI"

    def _set_winner_if_needed(self) -> bool:
        scores = self.state.scores
        if scores[0] < 121 and scores[1] < 121:
            return False

        if scores[0] > scores[1]:
            self.state.winner = 0
        elif scores[1] > scores[0]:
            self.state.winner = 1
        else:
            self.state.winner = None
        self.state.phase = "game_over"
        self.state.counting_next_phase = "game_over"
        return True

    def _validate_state(self) -> None:
        """Debug-mode validation of game state consistency.

        Raises AssertionError if state violates expected invariants.
        Used for testing and development; safe to call repeatedly.
        """
        assert isinstance(self.state.scores, (list, tuple)), "Scores must be a sequence"
        assert len(self.state.scores) == 2, "Must have exactly 2 players"
        assert all(isinstance(s, int) for s in self.state.scores), "All scores must be integers"
        assert 0 <= self.state.dealer <= 1, "Dealer must be player 0 or 1"

        assert isinstance(self.state.player_hand, list), "Player hand must be a list"
        assert isinstance(self.state.ai_hand, list), "AI hand must be a list"
        assert len(self.state.player_hand) <= 6, "Player hand cannot exceed 6 cards"
        assert len(self.state.ai_hand) <= 6, "AI hand cannot exceed 6 cards"

        assert isinstance(self.state.crib, list), "Crib must be a list"
        assert len(self.state.crib) <= 4, "Crib cannot exceed 4 cards"

        assert self.state.phase in (
            "intro", "discard", "pegging", "counting", "end", "online_login", "online_match"
        ), f"Invalid phase: {self.state.phase}"

        if self.state.phase == "pegging":
            assert isinstance(self.state.pegging_pile, list), "Pegging pile must be a list"
            assert isinstance(self.state.pegging_passes, list), "Pegging passes must be a list"
            assert len(self.state.pegging_passes) == 2, "Must track passes for both players"

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
        self.state.counting_resolved = False
        self.state.counting_next_phase = "end"
        self.state.last_counting_result = {}
        self.state.last_counting_breakdown = {}
        self.state.message = "Select 2 cards to discard to the crib."
        self.state.stock_labels = list(stock_labels)
        self._validate_state_if_enabled()

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
        self.state.counting_resolved = False
        self.state.counting_next_phase = "end"
        self.state.last_counting_result = {}
        self.state.last_counting_breakdown = {}
        self.state.message = "New Round. Select 2 cards to discard."
        self.state.stock_labels = list(stock_labels)
        self._validate_state_if_enabled()

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
        self.state.counting_resolved = False
        self.state.counting_next_phase = "end"
        self.state.message = "Pegging phase begins!"
        self._validate_state_if_enabled()

    def play_pegging_card(
        self,
        player_idx: int,
        card_index: int,
        score_pegging_play: Callable[[Sequence[Any]], int],
        value_for_15: Callable[[str], int],
        parse_label: Callable[[str], tuple[str, str]],
        player_name: str = "Player",
    ) -> int:
        """Play a card during pegging phase with error handling.

        Args:
            player_idx: 0 for player, 1 for AI
            card_index: Index of card to play in hand
            score_pegging_play: Function to score pegging pile
            value_for_15: Function to get card value for 15s
            parse_label: Function to parse card label
            player_name: Player's display name

        Returns:
            Points scored (0 if invalid play or error)
        """
        try:
            hand = self.state.player_hand if player_idx == 0 else self.state.ai_hand

            # Bounds validation
            if not isinstance(card_index, int) or card_index < 0 or card_index >= len(hand):
                return 0

            if not hand:
                return 0

            card = hand[card_index]
            projected_total = cribbage_cards.pegging_total(self.state.pegging_pile)
            rank, _ = parse_label(self._label(card))
            if projected_total + value_for_15(rank) > 31:
                return 0

            card = hand.pop(card_index)
            self.state.pegging_pile.append(card)
            self.state.pegging_passes = [False, False]

            points = score_pegging_play(self.state.pegging_pile)
            self.state.scores[player_idx] += points

            name = player_name if player_idx == 0 else self._dealer_name()
            point_note = f" (+{points})" if points else ""

            total = sum(value_for_15(parse_label(self._label(c))[0]) for c in self.state.pegging_pile)
            if total == 31:
                self.state.message = f"{name} played 31{point_note}. New count."
                self.state.pegging_pile.clear()
                self.state.player_turn = 1 - player_idx
            else:
                self.state.message = f"{name} pegs{point_note}. " + (
                    f"{self._dealer_name()}'s turn." if player_idx == 0 else "Your turn."
                )
                self.state.player_turn = 1 - player_idx

            self.state.last_pegging_player = player_idx
            self._set_winner_if_needed()
            self._validate_state_if_enabled()
            return points
        except (IndexError, KeyError, AttributeError, TypeError) as e:
            # Log error but allow game to continue with safe default
            print(f"Warning: play_pegging_card error: {type(e).__name__}: {e}")
            return 0

    def pass_pegging_turn(self, player_idx: int) -> dict[str, Any]:
        if self.state.phase != "pegging":
            return {"ok": False, "reason": "invalid_phase"}
        if player_idx not in (0, 1):
            return {"ok": False, "reason": "invalid_player"}

        self.state.pegging_passes[player_idx] = True
        other = 1 - player_idx

        if self.state.pegging_passes[other]:
            current_total = cribbage_cards.pegging_total(self.state.pegging_pile)
            last_card_point = 0
            if (
                self.state.pegging_pile
                and current_total < 31
                and self.state.last_pegging_player is not None
            ):
                last_card_point = 1
                self.state.scores[self.state.last_pegging_player] += 1
            self.state.pegging_pile.clear()
            self.state.pegging_passes = [False, False]
            if self.state.last_pegging_player is not None:
                self.state.player_turn = 1 - self.state.last_pegging_player
            self.state.message = (
                "Go for you (+1). New count."
                if last_card_point and self.state.last_pegging_player == 0
                else f"Go for {self._dealer_name()} (+1). New count."
                if last_card_point
                else "No plays. New count."
            )
            self._set_winner_if_needed()
            return {"ok": True, "points": last_card_point, "go_completed": True}

        self.state.player_turn = other
        self.state.message = "Go. " + (
            f"{self._dealer_name()}'s turn." if other == 1 else "Your turn."
        )
        self._set_winner_if_needed()
        return {"ok": True, "points": 0, "go_completed": False}

    def ai_discard(self, strategy: Any | None = None) -> list[int]:
        strategy_module = ai_strategy if strategy is None else strategy
        dad_labels = self._labels(self.state.ai_hand)
        return strategy_module.choose_discard_indices(
            dad_labels=dad_labels,
            dad_ai_level=self.state.dad_ai_level,
            dealer_is_dad=(self.state.dealer == 1),
            canonical_deck_labels=self._canonical_deck_labels(),
            score_labels_hand=self._score_labels_hand,
            game_state=self.state,
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
            game_state=self.state,
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
                else f"{self._dealer_name()} gets last card for 1 point. Counting hands."
            )
        else:
            self.state.message = "Counting hands."

        self.state.phase = "counting"
        self.state.counting_resolved = False
        self.state.counting_next_phase = "end"
        self._validate_state_if_enabled()
        return True

    def count_hands(self, label_to_model_card: Callable[[str], Any]) -> dict[str, Any]:
        if self.state.starter_card is None:
            self.state.phase = "end"
            self.state.message = "No starter card available. Press R to reset."
            self.state.last_counting_result = {}
            self.state.last_counting_breakdown = {}
            self.state.counting_resolved = True
            self.state.counting_next_phase = "end"
            self._validate_state_if_enabled()
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

        result = {"player": 0, "ai": 0, "crib": 0}
        breakdown = {"player": [], "ai": [], "crib": []}

        def _score_player(index: int, total: int, score_breakdown: list[tuple[str, list[str], int]], key: str) -> bool:
            if total <= 0:
                return False
            self.state.scores[index] += total
            result[key] = total
            breakdown[key] = score_breakdown
            if self._set_winner_if_needed():
                self.state.last_counting_result = dict(result)
                self.state.last_counting_breakdown = dict(breakdown)
                self.state.counting_resolved = True
                self.state.counting_next_phase = "game_over"
                return True
            return False

        if _score_player(0, p1_total, p1_breakdown, "player"):
            self._validate_state_if_enabled()
            return result

        if _score_player(1, p2_total, p2_breakdown, "ai"):
            self._validate_state_if_enabled()
            return result

        if len(crib_cards) == 4:
            dealer_idx = self.state.dealer
            self.state.scores[dealer_idx] += crib_total
            result["crib"] = crib_total
            breakdown["crib"] = crib_breakdown
            self._set_winner_if_needed()
        else:
            result["crib"] = 0
            breakdown["crib"] = []

        self.state.last_counting_result = dict(result)
        self.state.last_counting_breakdown = dict(breakdown)
        self.state.counting_resolved = True
        self.state.counting_next_phase = "game_over" if self.state.phase == "game_over" else "end"

        if self.state.dad_ai_level == 5:
            # Reward is net hand value from AI's perspective.
            ai_reward = float(p2_total - p1_total)
            ai_reward += float(crib_total if self.state.dealer == 1 else -crib_total)
            ai_strategy.get_bert_agent().end_of_hand_update(ai_reward)
            try:
                ai_strategy.save_bert_agent()
            except OSError:
                # Gameplay should continue even if model persistence fails.
                pass

        self._validate_state_if_enabled()

        return {
            "player": result["player"],
            "ai": result["ai"],
            "crib": result["crib"],
            "player_breakdown": breakdown["player"],
            "ai_breakdown": breakdown["ai"],
            "crib_breakdown": breakdown["crib"],
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

    @staticmethod
    def _remote_phase_index(phase: str) -> int:
        order = {"deal": 0, "discard": 1, "pegging": 2, "counting": 3, "finished": 4}
        return order.get(phase, 0)

    def _remote_player_index(self, player_id: str, player_one_id: str, player_two_id: str) -> int:
        if player_id == player_one_id:
            return 0
        if player_id == player_two_id:
            return 1
        raise ValueError("Player does not belong to this match")

    def _serialize_remote_cards(self, cards: Sequence[Any]) -> list[str]:
        return [self._label(card) for card in cards]

    def load_remote_snapshot(self, snapshot: dict[str, Any]) -> None:
        state = self.state
        for key, value in snapshot.items():
            if hasattr(state, key):
                setattr(state, key, value)

        # Normalize remote orchestration fields for backward compatibility.
        state.phase = str(getattr(state, "phase", "deal") or "deal")
        raw_scores = getattr(state, "scores", [0, 0])
        if not isinstance(raw_scores, list) or len(raw_scores) != 2:
            state.scores = [0, 0]
        else:
            state.scores = [int(raw_scores[0]), int(raw_scores[1])]

        state.deal_ready = [str(player) for player in list(getattr(state, "deal_ready", []))]
        raw_discards = getattr(state, "discard_by_player", {})
        if isinstance(raw_discards, dict):
            state.discard_by_player = {
                str(pid): [str(card) for card in list(cards)]
                for pid, cards in raw_discards.items()
            }
        else:
            state.discard_by_player = {}

        state.pegging_pile = list(getattr(state, "pegging_pile", []))
        raw_passes = list(getattr(state, "pegging_passes", [False, False]))
        state.pegging_passes = [bool(raw_passes[0]), bool(raw_passes[1])] if len(raw_passes) >= 2 else [False, False]
        state.last_pegging_player = getattr(state, "last_pegging_player", None)
        state.last_action = dict(getattr(state, "last_action", {}) or {})
        state.phase_progress = max(0, int(getattr(state, "phase_progress", 0) or 0))
        state.phase_index = int(getattr(state, "phase_index", self._remote_phase_index(state.phase)) or 0)
        state.count_by_player = {
            str(pid): bool(done)
            for pid, done in dict(getattr(state, "count_by_player", {}) or {}).items()
        }
        state.player_hand = list(getattr(state, "player_hand", []))
        state.ai_hand = list(getattr(state, "ai_hand", []))
        state.pegging_running_total = int(
            getattr(state, "pegging_running_total", cribbage_cards.pegging_total(state.pegging_pile)) or 0
        )

    def dump_remote_snapshot(self) -> dict[str, Any]:
        state = self.state
        return {
            "phase": str(state.phase),
            "phase_index": int(state.phase_index),
            "phase_progress": int(state.phase_progress),
            "scores": [int(state.scores[0]), int(state.scores[1])],
            "dealer": int(state.dealer),
            "player_turn": int(state.player_turn),
            "deal_ready": list(state.deal_ready),
            "discard_by_player": {k: list(v) for k, v in state.discard_by_player.items()},
            "pegging_pile": self._serialize_remote_cards(state.pegging_pile),
            "pegging_running_total": int(state.pegging_running_total),
            "pegging_passes": [bool(state.pegging_passes[0]), bool(state.pegging_passes[1])],
            "last_pegging_player": state.last_pegging_player,
            "count_by_player": dict(state.count_by_player),
            "player_hand": self._serialize_remote_cards(state.player_hand),
            "ai_hand": self._serialize_remote_cards(state.ai_hand),
            "last_action": dict(state.last_action),
            "winner": state.winner,
            "message": state.message,
            "counting_next_phase": state.counting_next_phase,
        }

    def _apply_remote_deal_ready(self, *, player_id: str) -> None:
        ready = set(self.state.deal_ready)
        ready.add(player_id)
        self.state.deal_ready = sorted(ready)
        self.state.phase_progress = len(self.state.deal_ready)
        if len(self.state.deal_ready) >= 2:
            self.state.phase = "discard"
            self.state.phase_index = self._remote_phase_index("discard")
            self.state.phase_progress = 0
            self.state.discard_by_player = {}

    def _apply_remote_discard(self, *, player_id: str, payload: dict[str, Any]) -> None:
        cards = [str(card) for card in list(payload.get("cards", []))]
        discards = dict(self.state.discard_by_player)
        discards[player_id] = cards
        self.state.discard_by_player = discards
        self.state.phase_progress = len(self.state.discard_by_player)
        if len(self.state.discard_by_player) >= 2:
            self.state.phase = "pegging"
            self.state.phase_index = self._remote_phase_index("pegging")
            self.state.phase_progress = 0
            self.state.count_by_player = {}
            self.state.pegging_passes = [False, False]
            self.state.pegging_pile = []
            self.state.pegging_running_total = 0
            self.state.last_pegging_player = None
            self.state.player_hand = ["remote_player_slot"] * 4
            self.state.ai_hand = ["remote_ai_slot"] * 4
            self.state.discard_by_player = {}
            self.state.player_turn = 1 - int(self.state.dealer)

    def _finalize_remote_pegging_if_needed(self) -> None:
        if self.state.phase != "pegging":
            return
        changed = self.finalize_pegging_if_complete(
            lambda: cribbage_cards.pegging_total(self.state.pegging_pile)
        )
        if changed:
            self.state.phase = "counting"
            self.state.phase_index = self._remote_phase_index("counting")
            self.state.phase_progress = 0
            self.state.count_by_player = {}

    def _apply_remote_peg(
        self,
        *,
        player_id: str,
        player_one_id: str,
        player_two_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        idx = self._remote_player_index(player_id, player_one_id, player_two_id)
        hand = self.state.player_hand if idx == 0 else self.state.ai_hand
        card_label = str(payload.get("card"))

        # Remote snapshots do not carry full hand identities; maintain card counts with slots.
        if not hand:
            hand.append("remote_slot")
        hand.append(card_label)
        points = self.play_pegging_card(
            idx,
            len(hand) - 1,
            cribbage_cards.score_pegging_play,
            cribbage_cards.value_for_fifteen,
            cribbage_cards.parse_card_label,
        )

        played = not hand or hand[-1] != card_label
        if not played and hand and hand[-1] == card_label:
            hand.pop()
        elif played and hand:
            hand.pop()

        self.state.pegging_running_total = int(cribbage_cards.pegging_total(self.state.pegging_pile))
        self.state.phase_progress += 1
        self._finalize_remote_pegging_if_needed()
        return {
            **payload,
            "running_total": self.state.pegging_running_total,
            "points": int(points),
        }

    def _apply_remote_go(
        self,
        *,
        player_id: str,
        player_one_id: str,
        player_two_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        idx = self._remote_player_index(player_id, player_one_id, player_two_id)
        result = self.pass_pegging_turn(idx)
        self.state.pegging_running_total = int(cribbage_cards.pegging_total(self.state.pegging_pile))
        self.state.phase_progress += 1
        self._finalize_remote_pegging_if_needed()
        if not result.get("ok"):
            return payload
        return {
            **payload,
            "points": int(result.get("points", 0)),
            "go_completed": bool(result.get("go_completed", False)),
        }

    def _apply_remote_count(
        self,
        *,
        player_id: str,
        player_one_id: str,
        player_two_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        points = payload.get("points")
        if not isinstance(points, int):
            return payload

        if points < 0 or points > 29:
            print(f"Warning: suspicious remote count points={points} from player={player_id}")
            return payload

        idx = self._remote_player_index(player_id, player_one_id, player_two_id)
        counted = dict(self.state.count_by_player)
        if not counted.get(player_id):
            self.state.scores[idx] += points
            counted[player_id] = True
            self.state.count_by_player = counted
            self.state.phase_progress = len(counted)

        if self.state.scores[0] >= 121 or self.state.scores[1] >= 121 or len(counted) >= 2:
            self.state.phase = "finished"
            self.state.phase_index = self._remote_phase_index("finished")
            self.state.phase_progress = 0
        return payload

    def apply_remote_action(
        self,
        *,
        player_id: str,
        player_one_id: str,
        player_two_id: str,
        action_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        phase = getattr(self.state, "phase", None)
        if not isinstance(phase, str) or not phase:
            raise ValueError("Remote state missing valid phase")

        applied_payload = dict(payload)
        if phase == "deal" and action_type == "deal_ready":
            self._apply_remote_deal_ready(player_id=player_id)
        elif phase == "discard" and action_type == "discard":
            self._apply_remote_discard(player_id=player_id, payload=payload)
        elif phase == "pegging" and action_type == "peg":
            applied_payload = self._apply_remote_peg(
                player_id=player_id,
                player_one_id=player_one_id,
                player_two_id=player_two_id,
                payload=payload,
            )
        elif phase == "pegging" and action_type == "go":
            applied_payload = self._apply_remote_go(
                player_id=player_id,
                player_one_id=player_one_id,
                player_two_id=player_two_id,
                payload=payload,
            )
        elif phase == "counting" and action_type == "count":
            applied_payload = self._apply_remote_count(
                player_id=player_id,
                player_one_id=player_one_id,
                player_two_id=player_two_id,
                payload=payload,
            )

        if self.state.phase == "game_over":
            self.state.phase = "finished"
            self.state.phase_index = self._remote_phase_index("finished")
            self.state.phase_progress = 0

        self.state.last_action = {
            "player_id": player_id,
            "action_type": action_type,
            "payload": applied_payload,
        }
        return self.dump_remote_snapshot()
