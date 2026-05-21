from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

import cards as cribbage_cards
from bert_persona import choose_line
from engine import CribbageEngine
from voice_manager import VoiceManager


class PhaseName(str, Enum):
    INTRO = "intro"
    DISCARD = "discard"
    PEGGING = "pegging"
    COUNTING = "counting"
    END = "end"
    GAME_OVER = "game_over"


class BasePhaseState:
    phase_name: PhaseName = PhaseName.INTRO
    allowed_transitions: set[PhaseName] = set()

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
    phase_name = PhaseName.INTRO
    allowed_transitions = {PhaseName.DISCARD, PhaseName.PEGGING, PhaseName.GAME_OVER}

    def enter(self, engine: CribbageEngine, ctx: dict[str, Any] | None = None) -> None:
        engine.state.message = "Ayuh, welcome to the table, deah."
        self._speak_event(engine, "level_selected", ctx)


class DiscardState(BasePhaseState):
    phase_name = PhaseName.DISCARD
    allowed_transitions = {PhaseName.PEGGING, PhaseName.INTRO, PhaseName.GAME_OVER}

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
        if engine.state.phase != self.phase_name.value:
            return engine.state.phase
        event_dict = cast(dict[str, Any], event)
        if event_dict.get("action") != "discard":
            return None
        selected = cast(list[int], event_dict.get("selected_indices", []))
        if not isinstance(selected, list):
            return None
        if len(selected) != 2:
            return None
        if len({i for i in selected if isinstance(i, int)}) != 2:
            return None
        if any(not isinstance(i, int) or i < 0 or i >= len(engine.state.player_hand) for i in selected):
            return None
        engine.handle_discard(selected)
        return engine.state.phase if engine.state.phase != self.phase_name.value else None


class PeggingState(BasePhaseState):
    phase_name = PhaseName.PEGGING
    allowed_transitions = {PhaseName.COUNTING, PhaseName.DISCARD, PhaseName.GAME_OVER}

    def enter(self, engine: CribbageEngine, ctx: dict[str, Any] | None = None) -> None:
        engine.state.pegging_pile.clear()
        engine.state.message = "Pegging phase."
        self._speak_event(engine, "round_start", ctx)

    def update(self, engine: CribbageEngine) -> str | None:
        if engine.state.phase != self.phase_name.value:
            return engine.state.phase
        # Auto-progress once both hands are exhausted.
        if engine.finalize_pegging_if_complete(
            lambda: engine.get_pegging_total()
        ):
            return engine.state.phase

        # Let AI make pegging plays in this phase when it's AI turn.
        if engine.is_ai_turn() and engine.state.ai_hand:
            current_total = engine.get_pegging_total()
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
            else:
                engine.pass_pegging_turn(1)
            if engine.state.phase != self.phase_name.value:
                return engine.state.phase
        return None

    def handle_event(
        self,
        event: Any,
        engine: CribbageEngine,
        ctx: dict[str, Any] | None = None,
    ) -> str | None:
        if not isinstance(event, dict):
            return None
        if engine.state.phase != self.phase_name.value:
            return engine.state.phase
        event_dict = cast(dict[str, Any], event)
        if event_dict.get("action") in {"peg_go", "go"}:
            if engine.state.player_turn != 0:
                return None
            engine.pass_pegging_turn(0)
            if engine.state.phase != self.phase_name.value:
                return engine.state.phase
            if engine.finalize_pegging_if_complete(
                lambda: engine.get_pegging_total()
            ):
                return engine.state.phase
            return None
        if event_dict.get("action") != "peg_play":
            return None
        if engine.state.player_turn != 0:
            return None

        card_index = cast(int | None, event_dict.get("card_index"))
        if not isinstance(card_index, int):
            return None
        if card_index < 0 or card_index >= len(engine.state.player_hand):
            return None

        if not engine.is_valid_pegging_play(
            player_idx=0,
            card_index=card_index,
            value_for_15=cribbage_cards.value_for_fifteen,
            parse_label=cribbage_cards.parse_card_label,
        ):
            return None

        engine.play_pegging_card(
            player_idx=0,
            card_index=card_index,
            score_pegging_play=cribbage_cards.score_pegging_play,
            value_for_15=cribbage_cards.value_for_fifteen,
            parse_label=cribbage_cards.parse_card_label,
            player_name=engine.state.player_name or "Player",
        )
        if engine.state.phase != self.phase_name.value:
            return engine.state.phase
        if engine.finalize_pegging_if_complete(
            lambda: engine.get_pegging_total()
        ):
            return engine.state.phase
        return None


class CountingState(BasePhaseState):
    phase_name = PhaseName.COUNTING
    allowed_transitions = {PhaseName.END, PhaseName.GAME_OVER}

    def enter(self, engine: CribbageEngine, ctx: dict[str, Any] | None = None) -> None:
        if not engine.state.counting_resolved:
            result = engine.count_hands(cribbage_cards.label_to_card)
            engine.state.last_counting_result = dict(result)
            engine.state.last_counting_breakdown = {
                "player": result.get("player_breakdown", []),
                "ai": result.get("ai_breakdown", []),
                "crib": result.get("crib_breakdown", []),
            }
        engine.state.message = "Counting hands and crib."
        self._speak_event(engine, "hand_scored", ctx)

    def update(self, engine: CribbageEngine) -> str | None:
        if engine.state.phase != self.phase_name.value:
            return engine.state.phase
        if not engine.state.counting_resolved:
            self.enter(engine)
        next_phase = engine.state.counting_next_phase
        result = engine.state.last_counting_result
        engine.state.phase = next_phase
        if next_phase == "game_over":
            return "game_over"
        if result:
            engine.state.message = (
                f"Round counted: You +{result['player']}, "
                f"{engine.state.ai_name} +{result['ai']}, crib +{result['crib']}."
            )
        return next_phase


class EndState(BasePhaseState):
    phase_name = PhaseName.END
    allowed_transitions = {PhaseName.DISCARD, PhaseName.INTRO, PhaseName.GAME_OVER}

    def enter(self, engine: CribbageEngine, ctx: dict[str, Any] | None = None) -> None:
        engine.state.message = "Round complete. Ready for the next hand?"
        self._speak_event(engine, "round_start", ctx)


class GameOverState(BasePhaseState):
    phase_name = PhaseName.GAME_OVER
    allowed_transitions = {PhaseName.INTRO, PhaseName.DISCARD}

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
        self.states: dict[PhaseName, BasePhaseState] = {
            PhaseName.INTRO: IntroState(),
            PhaseName.DISCARD: DiscardState(),
            PhaseName.PEGGING: PeggingState(),
            PhaseName.COUNTING: CountingState(),
            PhaseName.END: EndState(),
            PhaseName.GAME_OVER: GameOverState(),
        }
        for state in self.states.values():
            if not callable(getattr(state, "enter", None)):
                raise TypeError(f"Phase {state.__class__.__name__} must define enter()")
            if not callable(getattr(state, "handle_event", None)):
                raise TypeError(f"Phase {state.__class__.__name__} must define handle_event()")
            if not callable(getattr(state, "update", None)):
                raise TypeError(f"Phase {state.__class__.__name__} must define update()")
        if self.voice is not None:
            self.engine.voice = self.voice
        self.current.enter(self.engine, None)

    @property
    def current(self) -> BasePhaseState:
        try:
            key = PhaseName(str(self.engine.state.phase))
        except ValueError:
            key = PhaseName.INTRO
        return self.states.get(key, self.states[PhaseName.INTRO])

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
        try:
            target = PhaseName(target_phase)
        except ValueError:
            return False
        current = self.current
        if (
            not force
            and current.allowed_transitions
            and target not in current.allowed_transitions
        ):
            return False
        current.exit(self.engine, ctx)
        self.engine.state.phase = target.value
        self.current.enter(self.engine, ctx)
        return True
