from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import cards as cribbage_cards
from bert_persona import choose_line
from engine import CribbageEngine
from voice_manager import VoiceManager


class BasePhaseState:
    phase_name: str = ""
    allowed_transitions: set[str] = set()

    def enter(self, engine: CribbageEngine, ctx: dict[str, Any] | None = None) -> None:
        return None

    def exit(self, engine: CribbageEngine, ctx: dict[str, Any] | None = None) -> None:
        return None

    def update_state(self, state: Any, ctx: Any, dt: float = 0.0) -> str | None:
        return None

    def handle_event(
        self,
        event: Any,
        engine: CribbageEngine,
        ctx: dict[str, Any] | None = None,
    ) -> str | None:
        return None

    def update(self, engine: CribbageEngine) -> str | None:
        return None

    def _speak_event(
        self,
        engine: CribbageEngine,
        event: str,
        ctx: dict[str, Any] | None = None,
        *,
        force: bool = False,
    ) -> None:
        voice = getattr(engine, "voice", None)
        if voice is None:
            return
        if not isinstance(voice, VoiceManager):
            return
        context = ctx or {}
        line = choose_line(event, style="downeast", dad_ai_level=5, context=context)
        if line:
            voice.speak_bert(line, dad_ai_level=5, bypass_cooldown=force)


class IntroState(BasePhaseState):
    phase_name = "intro"
    allowed_transitions = {"discard", "pegging", "game_over"}

    def enter(self, engine: CribbageEngine, ctx: dict[str, Any] | None = None) -> None:
        engine.state.message = "Ayuh, welcome to the table, deah."
        self._speak_event(engine, "level_selected", ctx)


class DiscardState(BasePhaseState):
    phase_name = "discard"
    allowed_transitions = {"pegging", "intro", "game_over"}

    def enter(self, engine: CribbageEngine, ctx: dict[str, Any] | None = None) -> None:
        engine.state.message = "Select two cards to discard to the crib."
        self._speak_event(engine, "cards_dealt", ctx)

    def handle_event(
        self,
        event: Any,
        engine: CribbageEngine,
        ctx: dict[str, Any] | None = None,
    ) -> str | None:
        if not isinstance(event, dict):
            return None
        event_dict = cast(dict[str, Any], event)
        if event_dict.get("action") != "discard":
            return None
        selected = cast(list[int], event_dict.get("selected_indices", []))
        if not isinstance(selected, list):
            return None
        engine.handle_discard(selected)
        return engine.state.phase if engine.state.phase != self.phase_name else None


class PeggingState(BasePhaseState):
    phase_name = "pegging"
    allowed_transitions = {"counting", "discard", "game_over"}

    def enter(self, engine: CribbageEngine, ctx: dict[str, Any] | None = None) -> None:
        engine.state.pegging_pile.clear()
        engine.state.message = "Pegging phase."
        self._speak_event(engine, "round_start", ctx)

    def update(self, engine: CribbageEngine) -> str | None:
        # Auto-progress once both hands are exhausted.
        if engine.finalize_pegging_if_complete(
            lambda: cribbage_cards.pegging_total(engine.state.pegging_pile)
        ):
            return engine.state.phase

        # Let AI make pegging plays in this phase when it's AI turn.
        if engine.state.player_turn == 1 and engine.state.ai_hand:
            current_total = cribbage_cards.pegging_total(engine.state.pegging_pile)
            ai_index = engine.ai_pegging_move(
                current_total=current_total,
                value_for_15=cribbage_cards.value_for_fifteen,
                parse_label=cribbage_cards.parse_card_label,
                score_pegging_play=cribbage_cards.score_pegging_play,
                label_card_factory=lambda label: type("_CardRef", (), {"label": label})(),
            )
            if isinstance(ai_index, int):
                engine.play_pegging_card(
                    player_idx=1,
                    card_index=ai_index,
                    score_pegging_play=cribbage_cards.score_pegging_play,
                    value_for_15=cribbage_cards.value_for_fifteen,
                    parse_label=cribbage_cards.parse_card_label,
                )
        return None

    def handle_event(
        self,
        event: Any,
        engine: CribbageEngine,
        ctx: dict[str, Any] | None = None,
    ) -> str | None:
        if not isinstance(event, dict):
            return None
        event_dict = cast(dict[str, Any], event)
        if event_dict.get("action") != "peg_play":
            return None
        if engine.state.player_turn != 0:
            return None

        card_index = cast(int | None, event_dict.get("card_index"))
        if not isinstance(card_index, int):
            return None

        engine.play_pegging_card(
            player_idx=0,
            card_index=card_index,
            score_pegging_play=cribbage_cards.score_pegging_play,
            value_for_15=cribbage_cards.value_for_fifteen,
            parse_label=cribbage_cards.parse_card_label,
            player_name=engine.state.player_name or "Player",
        )
        if engine.finalize_pegging_if_complete(
            lambda: cribbage_cards.pegging_total(engine.state.pegging_pile)
        ):
            return engine.state.phase
        return None


class CountingState(BasePhaseState):
    phase_name = "counting"
    allowed_transitions = {"end", "game_over"}

    def enter(self, engine: CribbageEngine, ctx: dict[str, Any] | None = None) -> None:
        engine.state.message = "Counting hands and crib."
        self._speak_event(engine, "hand_scored", ctx)

    def update(self, engine: CribbageEngine) -> str | None:
        result = engine.count_hands(cribbage_cards.label_to_card)
        winner = 0 if engine.state.scores[0] >= 121 else (1 if engine.state.scores[1] >= 121 else None)
        if winner is not None:
            engine.state.winner = winner
            engine.state.phase = "game_over"
            return "game_over"
        engine.state.message = (
            f"Round counted: You +{result['player']}, "
            f"{engine.state.ai_name} +{result['ai']}, crib +{result['crib']}."
        )
        engine.state.phase = "end"
        return "end"


class EndState(BasePhaseState):
    phase_name = "end"
    allowed_transitions = {"discard", "intro", "game_over"}

    def enter(self, engine: CribbageEngine, ctx: dict[str, Any] | None = None) -> None:
        engine.state.message = "Round complete. Ready for the next hand?"
        self._speak_event(engine, "round_start", ctx)


class GameOverState(BasePhaseState):
    phase_name = "game_over"
    allowed_transitions = {"intro", "discard"}

    def enter(self, engine: CribbageEngine, ctx: dict[str, Any] | None = None) -> None:
        engine.state.message = "Game over."
        context = ctx or {}
        event = "bert_won" if bool(context.get("bert_won", False)) else "player_won"
        self._speak_event(engine, event, context, force=True)


@dataclass
class PhaseStateMachine:
    engine: CribbageEngine
    voice: VoiceManager | None = None

    def __post_init__(self) -> None:
        self.states: dict[str, BasePhaseState] = {
            "intro": IntroState(),
            "discard": DiscardState(),
            "pegging": PeggingState(),
            "counting": CountingState(),
            "end": EndState(),
            "game_over": GameOverState(),
        }
        if self.voice is not None:
            self.engine.voice = self.voice
        self.current.enter(self.engine, None)

    @property
    def current(self) -> BasePhaseState:
        return self.states.get(self.engine.state.phase, self.states["intro"])

    def handle_event(self, event: Any, ctx: dict[str, Any] | None = None) -> None:
        transition = self.current.handle_event(event, self.engine, ctx)
        if transition:
            self.transition(transition, ctx=ctx)

    def update(self) -> None:
        transition = self.current.update(self.engine)
        if transition:
            self.transition(transition)

    def transition(
        self,
        target_phase: str,
        force: bool = False,
        ctx: dict[str, Any] | None = None,
    ) -> bool:
        if target_phase not in self.states:
            return False
        current = self.current
        if (
            not force
            and current.allowed_transitions
            and target_phase not in current.allowed_transitions
        ):
            return False
        current.exit(self.engine, ctx)
        self.engine.state.phase = target_phase
        self.current.enter(self.engine, ctx)
        return True
