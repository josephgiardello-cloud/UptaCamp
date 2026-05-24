from __future__ import annotations

# pyright: reportConstantRedefinition=false
import json
import random
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True)
class BertPersonaConfig:
    style: str = "downeast"


_DOWNEAST_LINES: dict[str, list[str]] = {
    "level_selected": [
        "Ayuh. Bert's sittin in now.",
        "Pull up, bub. Bert's at the table.",
        "Bert's in the chair. Let's play a wicked clean hand.",
    ],
    "game_start": [
        "Cards on the wood. Let's have a hand.",
        "Alright then, shuffle up and deal, bub.",
        "Settle in now. We got wicked proper cribbage to play.",
    ],
    "cards_dealt": [
        "Hand's in. Show me what ya got, bub.",
        "Cards are dealt. Keep it tidy now.",
        "There ya go, bub. Pick two wise.",
    ],
    "round_start": [
        "New hand, same old stubborn Bert.",
        "Fresh hand. Eyes up now.",
        "Ayuh, new round. Mind the count.",
    ],
    "go_called": [
        "Go called. My turn now.",
        "Ayuh, I'll take that go.",
        "No play? Then Bert's movin.",
    ],
    "go_point": [
        "Go for Bert. Count it.",
        "That's one for me, bub.",
        "One fer Bert. Mark er down.",
    ],
    "last_card": [
        "Last cahd. I'll pocket that point.",
        "Ayuh, last cahd's mine.",
        "Last cahd to Bert. That's the way.",
    ],
    "pegging_score": [
        "Nice little peg there.",
        "Wicked clean peg.",
        "That's tidy peggin right there.",
    ],
    "pegging_31": [
        "Thirty-one. That's tidy cribbage.",
        "Ayuh, thirty-one right on the nose.",
        "Thirty-one, bub. Right smart play.",
    ],
    "player_won": [
        "You got me this time. Good cahds.",
        "Fair play. You earned that one.",
        "Ayuh, ya beat me square this hand.",
    ],
    "bert_won": [
        "Bert takes the table. Run it again.",
        "That's game for Bert. Shuffle up.",
        "Bert's got it. Nothin fancy, just clean play.",
    ],
    "hand_scored": [
        "Counted the hand. See them points add up?",
        "Ayuh, them cahds tallied up nicely.",
        "Hand's counted. That's the way of it.",
    ],
    "crib_scored": [
        "Crib's in. Bert likes what he sees.",
        "Ayuh, them crib cahds done their job.",
        "Counted the crib. Every point earns.",
    ],
    "round_summary": [
        "Hand's closed. Peg board, hand count, crib done proper.",
        "That's the round: pegs marked, crib counted, on to the next cut.",
        "Round summary's in. Keep the toss tight next hand, bub.",
    ],
}

_ROBOT_LINES: dict[str, list[str]] = {
    "level_selected": ["BERT MODE ENABLED.", "BERT ONLINE."],
    "game_start": ["INITIALIZING CRIBBAGE SESSION.", "GAME START CONFIRMED."],
    "cards_dealt": ["CARD DISTRIBUTION COMPLETE.", "HAND RECEIVED."],
    "round_start": ["NEW ROUND INITIALIZED.", "ROUND STATE RESET."],
    "go_called": ["GO RECEIVED. EXECUTING TURN."],
    "go_point": ["POINT REGISTERED."],
    "last_card": ["LAST CARD BONUS APPLIED."],
    "pegging_score": ["PEGGING EVENT SCORED."],
    "pegging_31": ["THIRTY-ONE REACHED."],
    "player_won": ["RESULT: PLAYER VICTORY."],
    "bert_won": ["RESULT: BERT VICTORY."],
    "hand_scored": ["HAND COUNT FINALIZED.", "SCORING COMPLETE."],
    "crib_scored": ["CRIB EVALUATION COMPLETE.", "CRIB SCORED."],
    "round_summary": ["ROUND SUMMARY GENERATED.", "HAND CLOSED. PREPARE NEXT DEAL."],
}

_BARNABUS_DOWNEAST_LINES: dict[str, list[str]] = {
    "level_selected": [
        "Barnabas sits down and the room gets smaller.",
        "Old House is open. Barnabas is in the chair.",
        "Barnabas is at the table now. Keep your hands clean.",
    ],
    "game_start": [
        "Cards on wood. Barnabas reads every edge.",
        "Game on. Barnabas is already tracking your outs.",
        "Settle in. Barnabas plays this board for keeps.",
    ],
    "cards_dealt": [
        "Hand is in. Barnabas is counting your throw.",
        "Cards dealt. Every discard tells on you.",
        "Pick two. Barnabas already priced the crib.",
    ],
    "round_start": [
        "New hand. Same pressure from Barnabas.",
        "Fresh round. Barnabas keeps the screws tight.",
        "Round starts. Barnabas takes the hard line.",
    ],
    "go_called": [
        "Go called. Barnabas takes the lane.",
        "No play? Barnabas will collect.",
        "Go. Barnabas turns the count.",
    ],
    "go_point": [
        "One for Barnabas. Tiny leaks sink games.",
        "Barnabas pockets the go point.",
        "Go point to Barnabas. Mark it.",
    ],
    "last_card": [
        "Last card to Barnabas.",
        "Barnabas takes last card and keeps moving.",
        "Last card is mine. Barnabas closes clean.",
    ],
    "pegging_score": [
        "Barnabas pegs and keeps pressure on.",
        "Clean peg for Barnabas.",
        "Barnabas finds a point in the noise.",
    ],
    "pegging_31": [
        "Thirty-one. Barnabas times it right.",
        "Barnabas lands on thirty-one.",
        "Thirty-one to Barnabas. Exact work.",
    ],
    "player_won": [
        "You got this hand. Barnabas logs the pattern.",
        "You won this round. Barnabas adjusts.",
        "You took it. Barnabas will answer next deal.",
    ],
    "bert_won": [
        "Barnabas takes the table.",
        "This one is Barnabas.",
        "Barnabas wins the hand and keeps control.",
    ],
    "hand_scored": [
        "Hand counted. Barnabas likes the math.",
        "Barnabas tallies the hand.",
        "Scoring complete. Barnabas keeps the edge.",
    ],
    "crib_scored": [
        "Crib scored. Barnabas reads the value.",
        "Barnabas counts the crib clean.",
        "Crib is in. Barnabas takes what is there.",
    ],
    "round_summary": [
        "Round closed. Peg lane, hand count, and crib all accounted.",
        "That hand is settled: throws punished, pegs harvested, crib counted.",
        "Round summary stands. Cut again if you dare.",
    ],
}

_BARNABUS_ROBOT_LINES: dict[str, list[str]] = {
    "level_selected": ["BARNABUS MODE ENGAGED.", "OLD HOUSE PROFILE ONLINE."],
    "game_start": ["BARNABUS SESSION START.", "BARNABUS PRESSURE PROFILE INITIALIZED."],
    "cards_dealt": ["DEAL STATE ACQUIRED.", "DISCARD INFERENCE ACTIVE."],
    "round_start": ["ROUND RESET COMPLETE.", "TACTICAL LOOP CONTINUES."],
    "go_called": ["GO ACCEPTED. EXECUTING PRESSURE LINE."],
    "go_point": ["GO POINT SECURED."],
    "last_card": ["LAST CARD BONUS SECURED."],
    "pegging_score": ["PEGGING POINT CAPTURED."],
    "pegging_31": ["THIRTY-ONE CAPTURE CONFIRMED."],
    "player_won": ["RESULT: PLAYER HAND VICTORY. MODEL ADAPTING."],
    "bert_won": ["RESULT: BARNABUS VICTORY."],
    "hand_scored": ["HAND SCORING FINALIZED."],
    "crib_scored": ["CRIB SCORING FINALIZED."],
    "round_summary": ["ROUND SUMMARY COMPLETE."],
}

_BARNABUS_GENTLEMAN_TAILS: tuple[str, ...] = (
    "Compose yourself, my dear. Precision decides this house.",
    "A measured hand, and we shall proceed with decorum.",
    "Family name first. Sentiment can wait.",
)

_BARNABUS_VAMPIRE_TAILS: tuple[str, ...] = (
    "Do not mistake my restraint for mercy.",
    "My patience is not inexhaustible.",
    "When cornered, I do what necessity demands.",
)

_LEVEL5_LEARNED_CUES: set[str] = set()
_RECENT_LINES: deque[str] = deque(maxlen=25)
_EVENT_RECENT: dict[str, deque[str]] = {}
_ACTIVE_EVENT: str | None = None
_ACTIVE_CONTEXT: dict[str, Any] | None = None

_IMMEDIATE_REPEAT_WINDOW = 20
_SAME_EVENT_REPEAT_WINDOW = 25
_SESSION_CALLBACK_SPACING = 9

_EVENT_THEME_CATEGORY: dict[str, str] = {
    "pegging_score": "boat",
    "go_point": "boat",
    "pegging_31": "boat",
    "cards_dealt": "boat",
    "crib_scored": "boat",
    "hand_scored": "weather",
    "round_start": "yankee_wisdom",
    "game_start": "weather",
    "player_won": "yankee_wisdom",
    "bert_won": "boat",
}

_THEMATIC_PHRASES: dict[str, tuple[str, ...]] = {
    "boat": (
        "Like haulin traps at first light.",
        "Bluebird work, one pull at a time.",
        "Keep her straight and she'll answer.",
        "No loose knots on this rail.",
    ),
    "weather": (
        "Lucky tide when it shows up.",
        "Weather turns when it wants, not when asked.",
        "Fog lifts slow but it lifts.",
        "Same wind, different hands.",
    ),
    "woods": (
        "Like a beater truck in mud season roads.",
        "Same as cuttin wood: steady and square.",
        "No need to swing wild in the timber.",
    ),
    "tourist": (
        "From away always wants the short map.",
        "Hard tellin not knowin for folks from away.",
        "Some roads only make sense local.",
    ),
    "yankee_wisdom": (
        "Tide don't care about talk.",
        "Work first, story after.",
        "You mind your hands and the rest comes around.",
        "Well now, we'll see where she settles.",
    ),
}

_EVENT_GOLD_TAILS: dict[str, tuple[str, ...]] = {}
_FORBIDDEN_VERBATIM_FRAGMENTS: tuple[str, ...] = (
    "come down to the dock about six o'clock in the early morning",
    "water come up to our necks before we decided to swim for it",
    "standing invitation to ride on the bluebird ii with bert and i",
)


def _passes_legal_guardrails(line: str) -> bool:
    lowered = line.lower()
    for fragment in _FORBIDDEN_VERBATIM_FRAGMENTS:
        if fragment and fragment in lowered:
            return False
    return True


def _purge_bert_from_barnabas_text(line: str) -> str:
    # Guardrail: Barnabas output should never leak Bert branding.
    text = re.sub(r"\bbert\s*\+\b", "Barnabas", line, flags=re.IGNORECASE)
    text = re.sub(r"\bbert plus\b", "Barnabas", text, flags=re.IGNORECASE)
    text = re.sub(r"\bbert\b", "Barnabas", text, flags=re.IGNORECASE)
    return text


def _load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(parsed, dict):
        return cast(dict[str, Any], parsed)
    return None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return rows
    for line in raw.splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(cast(dict[str, Any], parsed))
    return rows


def _load_external_generator_data() -> None:
    global _IMMEDIATE_REPEAT_WINDOW, _SAME_EVENT_REPEAT_WINDOW, _SESSION_CALLBACK_SPACING
    global _FORBIDDEN_VERBATIM_FRAGMENTS
    global _BARNABUS_DOWNEAST_LINES, _BARNABUS_ROBOT_LINES
    global _BARNABUS_GENTLEMAN_TAILS, _BARNABUS_VAMPIRE_TAILS

    data_dir = Path(__file__).resolve().parent / "data" / "bert_voice"

    cfg = _load_json_file(data_dir / "generator_config.json")
    if cfg:
        event_theme = cfg.get("event_theme_category")
        if isinstance(event_theme, dict):
            for event, category in cast(dict[str, Any], event_theme).items():
                if isinstance(category, str):
                    _EVENT_THEME_CATEGORY[event] = category

        themed = cfg.get("thematic_phrases")
        if isinstance(themed, dict):
            for category, values in cast(dict[str, Any], themed).items():
                if not isinstance(values, list):
                    continue
                cleaned = tuple(
                    v for v in cast(list[Any], values) if isinstance(v, str) and v.strip()
                )
                if cleaned:
                    _THEMATIC_PHRASES[category] = cleaned

        repetition = cfg.get("repetition_policy")
        if isinstance(repetition, dict):
            rep = cast(dict[str, Any], repetition)
            immediate = rep.get("immediate_repeat_window")
            same_event = rep.get("same_event_repeat_window")
            callback_spacing = rep.get("session_callback_spacing")
            if isinstance(immediate, int) and immediate > 0:
                _IMMEDIATE_REPEAT_WINDOW = immediate
            if isinstance(same_event, int) and same_event > 0:
                _SAME_EVENT_REPEAT_WINDOW = same_event
            if isinstance(callback_spacing, int) and callback_spacing > 0:
                _SESSION_CALLBACK_SPACING = callback_spacing

        legal = cfg.get("legal_guardrails")
        if isinstance(legal, dict):
            legal_cfg = cast(dict[str, Any], legal)
            forbidden = legal_cfg.get("forbidden_verbatim_fragments")
            if isinstance(forbidden, list):
                cleaned = tuple(
                    part.strip().lower()
                    for part in cast(list[Any], forbidden)
                    if isinstance(part, str) and part.strip()
                )
                if cleaned:
                    _FORBIDDEN_VERBATIM_FRAGMENTS = cleaned

    rows = _load_jsonl(data_dir / "gold_lines_seed.jsonl")
    event_tails: dict[str, list[str]] = {}
    for row in rows:
        event_key = row.get("event")
        line = row.get("line")
        if isinstance(event_key, str) and isinstance(line, str) and line.strip():
            event_tails.setdefault(event_key, []).append(line.strip())

    _EVENT_GOLD_TAILS.clear()
    for event, values in event_tails.items():
        deduped = tuple(dict.fromkeys(values))
        if deduped:
            _EVENT_GOLD_TAILS[event] = deduped

    barnabas_cfg = _load_json_file(data_dir / "barnabas_lines.json")
    if barnabas_cfg:

        def _extract_line_bank(raw: Any) -> dict[str, list[str]]:
            if not isinstance(raw, dict):
                return {}
            parsed: dict[str, list[str]] = {}
            for event, values in cast(dict[str, Any], raw).items():
                if not isinstance(values, list):
                    continue
                cleaned = [
                    v.strip() for v in cast(list[Any], values) if isinstance(v, str) and v.strip()
                ]
                if cleaned:
                    parsed[event] = cleaned
            return parsed

        def _extract_tails(raw: Any) -> tuple[str, ...]:
            if not isinstance(raw, list):
                return ()
            cleaned = tuple(v.strip() for v in raw if isinstance(v, str) and v.strip())
            return cleaned

        downeast_bank = _extract_line_bank(barnabas_cfg.get("downeast_lines"))
        robot_bank = _extract_line_bank(barnabas_cfg.get("robot_lines"))
        gentleman_tails = _extract_tails(barnabas_cfg.get("gentleman_tails"))
        vampire_tails = _extract_tails(barnabas_cfg.get("vampire_tails"))

        if downeast_bank:
            _BARNABUS_DOWNEAST_LINES = downeast_bank
        if robot_bank:
            _BARNABUS_ROBOT_LINES = robot_bank
        if gentleman_tails:
            _BARNABUS_GENTLEMAN_TAILS = gentleman_tails
        if vampire_tails:
            _BARNABUS_VAMPIRE_TAILS = vampire_tails


_load_external_generator_data()


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


_MOOD_VARIANT_FILLERS: dict[str, tuple[str, ...]] = {
    "neutral": (
        "Ayuh. Keep it tidy and keep it movin.",
        "Steady hands, clean count.",
        "No fuss, just proper cribbage.",
        "We'll let the board do the talkin.",
        "Quiet work, solid pegs.",
    ),
    "hot": (
        "Rough water or not, I still haul clean.",
        "Teeth out now. Count every inch.",
        "No soft tosses in this weather.",
        "I'm workin sharp edges from here.",
        "Keep your hands tight, bub.",
    ),
    "trailing": (
        "No panic. Just tighter knots.",
        "We'll trim this back one peg at a time.",
        "Ayuh. Work first, chatter later.",
        "I'm still in this water, clear enough.",
        "Board's stubborn; so am I.",
    ),
    "leading": (
        "Pace stays steady. No hero throws.",
        "We'll keep this rail clean and quiet.",
        "No rush. Good boards reward patience.",
        "Same current, same discipline.",
        "Measured hands close games.",
    ),
}


def _pick(*lines: str, lane: str = "neutral") -> str:
    options: list[str] = []
    seen: set[str] = set()

    for line in lines:
        if line not in seen:
            options.append(line)
            seen.add(line)

    base_lines = list(options)
    tails = _MOOD_VARIANT_FILLERS.get(lane, _MOOD_VARIANT_FILLERS["neutral"])
    active_event = _ACTIVE_EVENT or ""
    category = _EVENT_THEME_CATEGORY.get(active_event, "yankee_wisdom")
    theme_tails = _THEMATIC_PHRASES.get(category, _THEMATIC_PHRASES["yankee_wisdom"])
    gold_tails = _EVENT_GOLD_TAILS.get(active_event, ())
    combined_tails = tuple(dict.fromkeys((*theme_tails, *gold_tails)))
    if not combined_tails:
        combined_tails = theme_tails
    if not base_lines:
        base_lines = list(_MOOD_VARIANT_FILLERS["neutral"])

    idx = 0
    while len(options) < 5:
        base = base_lines[idx % len(base_lines)]
        mood_tail = tails[idx % len(tails)]
        theme_tail = combined_tails[idx % len(combined_tails)]
        if idx % 2 == 0:
            variant = f"{base} {mood_tail}"
        else:
            variant = f"{base} {theme_tail}"
        idx += 1
        if variant in seen:
            continue
        options.append(variant)
        seen.add(variant)

    # Strong no-repeat window for long sessions.
    blocked = set(list(_RECENT_LINES)[-_IMMEDIATE_REPEAT_WINDOW:])
    event_hist: deque[str] | None = None
    if active_event:
        event_hist = _EVENT_RECENT.setdefault(active_event, deque(maxlen=80))
        blocked.update(list(event_hist)[-_SAME_EVENT_REPEAT_WINDOW:])
    candidates = [line for line in options if line not in blocked]
    if not candidates:
        candidates = options

    randomized = list(candidates)
    random.shuffle(randomized)
    choice = ""
    for candidate in randomized:
        if _passes_legal_guardrails(candidate):
            choice = candidate
            break
    if not choice:
        choice = f"{base_lines[0]} {tails[0]}"

    # Light callback memory if previous game note exists.
    ctx = _ACTIVE_CONTEXT or {}
    previous_note = str(ctx.get("previous_game_note", "")).strip()
    if previous_note and (len(_RECENT_LINES) % _SESSION_CALLBACK_SPACING == 0):
        callback_choice = f"{choice} Last time, {previous_note}."
        if _passes_legal_guardrails(callback_choice):
            choice = callback_choice

    _RECENT_LINES.append(choice)
    if event_hist is not None:
        event_hist.append(choice)
    return choice


def _bert_mood(score_gap: int) -> str:
    # Mood lanes by score gap (bert_score - player_score).
    if score_gap <= -18:
        return "boiling"
    if score_gap <= -11:
        return "hot"
    if score_gap <= -5:
        return "frustrated"
    if score_gap >= 18:
        return "clinical"
    if score_gap >= 11:
        return "stoic"
    if score_gap >= 5:
        return "focused"
    return "neutral"


def _is_trailing_mood(mood: str) -> bool:
    return mood in {"frustrated", "hot", "boiling"}


def _is_leading_mood(mood: str) -> bool:
    return mood in {"focused", "stoic", "clinical"}


def level5_play_posture(context: dict[str, Any] | None = None) -> str:
    ctx = context or {}
    player_score = _to_int(ctx.get("player_score"))
    bert_score = _to_int(ctx.get("bert_score"))
    score_gap = bert_score - player_score
    if score_gap <= -20:
        return "cutthroat"
    if score_gap <= -15:
        return "deliberate"
    if score_gap >= 15:
        return "deliberate"
    return "balanced"


def _gap_progression_overlay(score_gap: int) -> str:
    if score_gap <= -20:
        return _pick(
            "Ayuh, this water's mean now. Hook, line, and sinker time.",
            "No wasted pegs from here, bub. Nets go in tight.",
        )
    if score_gap <= -15:
        return _pick(
            "Time to set the nets proper now.",
            "Ayuh. Every throw and peg gets weighed true.",
        )
    if score_gap <= -10:
        return _pick(
            "Wicked annoyin water, but I'm settlin in tighter.",
            "That's enough to sour a man's coffee, bub.",
        )
    if score_gap <= -5:
        return _pick(
            "I'm annoyed, and I mean to tidy this up.",
            "Ayuh. Don't get cheerful yet.",
        )
    if score_gap >= 20:
        return _pick(
            "Up twenty now. You're rowin against tide, bub.",
            "Twenty up, ayuh. Keep swingin if it helps your spirit.",
        )
    if score_gap >= 15:
        return _pick(
            "Up fifteen. You're chasin fog at this point.",
            "Fifteen clear now, bub. Board's readin one-way traffic.",
        )
    if score_gap >= 10:
        return _pick(
            "Up ten. You're feedin me clean pegs now.",
            "Ten ahead, ayuh. That's a comfortable tide for Bert.",
        )
    if score_gap >= 5:
        return _pick(
            "Up five. You're givin me just enough rope, bub.",
            "Five clear now. Bert likes this current fine.",
        )
    return ""


def _learning_cue(event: str, context: dict[str, Any]) -> str | None:
    player_hand_points = _to_int(context.get("player_hand_points"))
    crib_points = _to_int(context.get("crib_points"))
    pegging_total = _to_int(context.get("pegging_total"))
    bert_is_dealer = bool(context.get("bert_is_dealer", False))
    player_score = _to_int(context.get("player_score"))
    bert_score = _to_int(context.get("bert_score"))
    score_gap = bert_score - player_score

    if event == "hand_scored" and player_hand_points >= 10:
        return "player_big_hand"
    if event == "crib_scored" and (not bert_is_dealer) and crib_points >= 6:
        return "player_crib_value"
    if event == "go_called" and pegging_total >= 27:
        return "late_count_go_pattern"
    if event == "go_point" and score_gap <= -10:
        return "trailing_go_scrap"
    return None


def _level5_learning_ack(event: str, context: dict[str, Any]) -> str:
    cue = _learning_cue(event, context)
    if cue is None or cue in _LEVEL5_LEARNED_CUES:
        return ""

    _LEVEL5_LEARNED_CUES.add(cue)
    return _pick(
        "Ayuh. That's new data, bub. I'll remember that.",
        "Wicked noted. I seen that now, and I'll remember it next hand.",
        "That's a clean tell right there, bub. Bert'll remember that, sure enough.",
    )


def _choose_downeast_line(event: str, context: dict[str, Any]) -> str:
    player_score = _to_int(context.get("player_score"))
    bert_score = _to_int(context.get("bert_score"))
    score_gap = bert_score - player_score
    pegging_total = _to_int(context.get("pegging_total"))
    bert_pegging_points = _to_int(context.get("bert_pegging_points"))
    player_pegging_points = _to_int(context.get("player_pegging_points"))
    bert_hand_points = _to_int(context.get("bert_hand_points"))
    player_hand_points = _to_int(context.get("player_hand_points"))
    crib_points = _to_int(context.get("crib_points"))
    bert_is_dealer = bool(context.get("bert_is_dealer", False))
    score_known = bert_score > 0 or player_score > 0
    mood = _bert_mood(score_gap)
    trailing_mood = _is_trailing_mood(mood)
    leading_mood = _is_leading_mood(mood)
    _ = level5_play_posture(context)

    def _pegging_lane(swing: int, total: int) -> str:
        if swing <= -4:
            return "against"
        if swing <= -2:
            return "down"
        if swing >= 4:
            return "ahead"
        if swing >= 2:
            return "up"
        if total >= 22:
            return "late"
        return "even"

    if event == "level_selected":
        if trailing_mood:
            return _pick(
                "Ayuh. Bert's in, and I'm in no patient mood today, bub.",
                "Bert takes the chair. Keep sharp, I'm done givin easy pegs.",
                lane="trailing",
            )
        if leading_mood:
            return _pick(
                "Ayuh. Bert's in. We'll keep this one clean and quiet.",
                "Bert at the table. No chatter, just tidy cribbage.",
                lane="leading",
            )
        return _pick(
            "Ayuh. Bert's sittin in now.",
            "Pull up, bub. Bert's at the table.",
            "Bert's in the chair. Let's play a wicked clean hand.",
        )

    if event == "game_start":
        if mood in {"hot", "boiling"}:
            return _pick(
                "Game on. Nets are out and I ain't haulin empty today, ayuh.",
                "Cards down, bub. Tide's rough, so mind your fingers.",
                lane="hot",
            )
        if trailing_mood:
            return _pick(
                "Cards on the wood. Mean water today, ayuh.",
                "Game on, bub. Keep your guard up; I brought sharp hooks.",
                lane="trailing",
            )
        if leading_mood:
            return _pick(
                "Cards on the wood. We play this one measured.",
                "Game start. Keep the board tidy and the count honest.",
                lane="leading",
            )
        return _pick(
            "Cards on the wood. Let's have a hand.",
            "Alright then, shuffle up and deal, bub.",
            "Settle in now. We got wicked proper cribbage to play.",
        )

    if event == "round_start":
        if bert_score >= 110 or player_score >= 110:
            return _pick(
                "Final stretch now. Every peg's got teeth, ayuh.",
                "We're in the last bend now. No soft plays from here, bub.",
            )
        if mood in {"hot", "boiling"}:
            return _pick(
                "New hand. Done driftin, bub.",
                "Ayuh, no more driftin. Bert's pushin every edge now.",
                lane="hot",
            )
        if trailing_mood:
            return _pick(
                "New hand. Let's see if you can hold the rail.",
                "Ayuh, keep smug and I'll make you pay for it.",
                lane="trailing",
            )
        if leading_mood:
            return _pick(
                "New hand. Keep it clean and count every peg.",
                "Fresh deal. No rush. We'll keep to deep water.",
                lane="leading",
            )
        if score_gap >= 12:
            return _pick(
                "New hand. I'll keep the pressure on ya.",
                "Fresh deal and Bert's still drivin the truck, wicked steady.",
            )
        if score_gap <= -12:
            return _pick(
                "New hand. Don't get comfy, bub.",
                "Tide changes quick Downeast.",
            )
        return _pick(
            "Fresh hand. Keep the count clean now, bub.",
            "New hand on the table. Play it straight and tight.",
        )

    if event == "cards_dealt":
        if mood in {"hot", "boiling"}:
            if bert_is_dealer:
                return _pick(
                    "Bert's deal. I'm settin traps now, so toss careful.",
                    "Deal's mine, bub. Loose tosses get salted quick.",
                    lane="hot",
                )
            return _pick(
                "Your deal. I'm readin every throw like bait marks.",
                "Fine, your crib. I'll answer in peggin with interest.",
                lane="hot",
            )
        if trailing_mood:
            if bert_is_dealer:
                return _pick(
                    "Bert's deal. Don't you dare fatten this crib, bub.",
                    "I'm dealin in rough water. Keep your tosses honest, ayuh.",
                    lane="trailing",
                )
            return _pick(
                "Your deal. I want hard points, not pretty stories.",
                "Your crib hand. Go on, make one loose toss for me.",
                lane="trailing",
            )
        if leading_mood:
            if bert_is_dealer:
                return _pick(
                    "Bert's deal. Lean discards, steady board.",
                    "I'm dealin. We keep this hand tidy and quiet.",
                    lane="leading",
                )
            return _pick(
                "Your deal. Keep the throw measured.",
                "Your crib hand. I'll read the toss and keep movin.",
                lane="leading",
            )
        if bert_is_dealer:
            return _pick(
                "Bert's deal. Toss light and don't feed my crib, ayuh.",
                "I'm dealin. Keep the throw lean and deny the crib lane, bub.",
            )
        return _pick(
            "Your deal. Keep your two-card throw honest now.",
            "Your crib this hand. Don't leak me fifteens on the toss, bub.",
        )

    if event == "go_called":
        if mood in {"hot", "boiling"}:
            return _pick(
                "Go? Ayuh. I'll turn this count with a hard edge.",
                "No play from you. Good. Time to press, bub.",
                lane="hot",
            )
        if trailing_mood:
            return _pick(
                "Go? Ayuh, finally. I'll take any crack at points right now.",
                "No play from you? Good. I need this count to turn.",
                lane="trailing",
            )
        if leading_mood:
            return _pick(
                "Go called. I'll take the lane and keep it calm.",
                "No play there. I continue the count.",
                lane="leading",
            )
        if pegging_total >= 27:
            return _pick(
                "Go? Ayuh, this close to thirty-one is where hands turn.",
                "Go at twenty-somethin? That's invitin a clean thirty-one, bub.",
            )
        return _pick(
            "Go called. Bert'll steer this count.",
            "No play from you? Then wheel comes to me, ayuh.",
        )

    if event == "go_point":
        if mood in {"hot", "boiling"}:
            return _pick(
                "Go for Bert. That's dock money right there.",
                "Marked one. Board's turnin with the tide now, bub.",
                lane="hot",
            )
        if trailing_mood:
            return _pick(
                "I'll take that go point. About time the board listened.",
                "One for Bert. Chip by chip, I'll keep the keel straight.",
                lane="trailing",
            )
        if leading_mood:
            return _pick(
                "Go for Bert. Quiet point, proper pace.",
                "Marked one for Bert. We keep walkin forward.",
                lane="leading",
            )
        if score_gap < 0:
            return _pick(
                "I'll take that go point and keep the hull straight.",
                "One at a time and I'm steerin true in your wake, bub.",
            )
        return _pick(
            "Go for Bert. Little points win long games, bub.",
            "There's your leak right there: gave away a go point, ayuh.",
        )

    if event == "last_card":
        if mood in {"hot", "boiling"}:
            return _pick(
                "Last card to Bert. I'll squeeze every peg left in this hand.",
                "Last card's mine. That's how a chase gets ugly, bub.",
                lane="hot",
            )
        if trailing_mood:
            return _pick(
                "Last card to Bert. Needed that like rain in August.",
                "I'll take last card, ayuh. Keep stackin what's there.",
                lane="trailing",
            )
        if leading_mood:
            return _pick(
                "Last card for Bert. Quiet point, proper finish.",
                "Last card's mine. Keep the pace steady.",
                lane="leading",
            )
        if bert_score >= 110:
            return _pick(
                "Last card and inches from the line. That's cold work.",
                "Last card near the finish rail. That's how games close, bub.",
            )
        return _pick(
            "Last card to Bert. That's one more nail in the board.",
            "Last card's mine. Quiet points, heavy result, ayuh.",
        )

    if event == "pegging_score":
        swing = bert_pegging_points - player_pegging_points
        peg_lane = _pegging_lane(swing, pegging_total)
        if mood in {"hot", "boiling"}:
            if swing <= -3:
                return _pick(
                    "Another peg leaks away. Not happenin again this hand.",
                    "Peg board's still sour, but I'm comin straight at it now.",
                    lane="hot",
                )
            if peg_lane == "late":
                return _pick(
                    "Late count and Bert finds one. That's harbor work.",
                    "There's a late peg. You don't leave those floatin, bub.",
                    lane="hot",
                )
            return _pick(
                "There's one. Keep stackin clean pegs.",
                "Point back to Bert. Keep your hands inside the rail, bub.",
                lane="hot",
            )
        if trailing_mood:
            if swing <= -3:
                return _pick(
                    "Another peg against me. Wicked irritating, ayuh.",
                    "Peg board's runnin sour. I'm not fond of it, bub.",
                    lane="trailing",
                )
            return _pick(
                "That's one back. Keep breathin, Bert.",
                "Fine. There's a peg I needed.",
                lane="trailing",
            )
        if leading_mood:
            if peg_lane in {"ahead", "up"}:
                return _pick(
                    "Clean peg. Board's favorin me and I'm keepin it tidy.",
                    "Point taken. Same current, same result.",
                    lane="leading",
                )
            return _pick(
                "Clean peg. No fuss.",
                "Point taken. Board stays under control.",
                lane="leading",
            )
        if pegging_total >= 20:
            return _pick(
                "That's a sharp peg late in the count.",
                "Late-count peg. That's where steady cribbage gets won, bub.",
            )
        if swing >= 4:
            return _pick(
                "Peg lane's leanin my way now, wicked hard.",
                "Peg board's runnin favorable for Bert this hand, ayuh.",
            )
        if peg_lane == "against":
            return _pick(
                "Peg board's runnin cross-current. I'll trim it back.",
                "You got the peg wind now, but not for long, bub.",
            )
        return _pick(
            "Wicked tidy peggin. Pairs and runs don't miss by accident.",
            "Clean peg. Nothing flashy, just proper cribbage work.",
        )

    if event == "pegging_31":
        if mood in {"hot", "boiling"}:
            return _pick(
                "Thirty-one. Ayuh, that's how you set a hook.",
                "Pinned thirty-one. That's one clean haul, bub.",
                lane="hot",
            )
        if trailing_mood:
            return _pick(
                "Thirty-one. Ayuh, that's the turn I needed.",
                "Pinned thirty-one. Finally somethin breaks my way, bub.",
                lane="trailing",
            )
        if leading_mood:
            return _pick(
                "Thirty-one on the nose. Efficient.",
                "Thirty-one. Board stays under control.",
                lane="leading",
            )
        if score_gap < 0:
            return _pick(
                "Thirty-one. That's how you swing a hand on clean steel.",
                "Thirty-one exact. That's a pull on the tiller right there, bub.",
            )
        return _pick(
            "Thirty-one on the nose. Keep up if you can.",
            "Pinned at thirty-one. Textbook, bub.",
        )

    if event == "hand_scored":
        if bert_score <= 90 and player_score >= 110:
            return _pick(
                "Ayuh, finish-rail weather now. Time to tie knots tighter.",
                "I can smell rough weather off this board, bub.",
            )
        if player_score <= 90 and bert_score >= 110:
            return _pick(
                "You're near skunk shoals now. Better find points quick.",
                "Scoreboard's lookin skunkish, ayuh.",
            )
        if mood in {"hot", "boiling"} and score_known:
            return _pick(
                "Hand's counted. Time to fish cleaner water.",
                "Count's in. No loose knots next hand, bub.",
                lane="hot",
            )
        if trailing_mood and score_known:
            return _pick(
                "Hand's counted. Ayuh, that's a grind.",
                "Count's in. Wicked aggravatin water.",
                lane="trailing",
            )
        if leading_mood and score_known:
            return _pick(
                f"Hand counted. Lead holds at {score_gap}.",
                f"Count complete. Up {score_gap}. Stay patient.",
                lane="leading",
            )
        if bert_hand_points >= 10:
            return _pick(
                f"Count it up: Bert pulled {bert_hand_points} in the hand.",
                f"Bert hand paid {bert_hand_points}. That'll move pegs, ayuh.",
            )
        if player_hand_points >= 10:
            return _pick(
                f"You found {player_hand_points} there. I saw it, ayuh.",
                f"Your hand paid {player_hand_points}. Fair count, no argument.",
            )
        return _pick(
            "Hand's counted. Small edges still cut deep.",
            "Lean hand, but every peg still counts in this game.",
        )

    if event == "crib_scored":
        if mood in {"hot", "boiling"}:
            if bert_is_dealer:
                return _pick(
                    f"Bert crib paid {crib_points}. Good haul from that set.",
                    f"Crib gives {crib_points}. That's fish in the box, ayuh.",
                    lane="hot",
                )
            return _pick(
                f"Your crib got {crib_points}. Enjoy it while the tide's with ya.",
                f"You hauled {crib_points} in crib. I seen enough now, bub.",
                lane="hot",
            )
        if trailing_mood:
            if bert_is_dealer:
                return _pick(
                    f"Bert crib paid {crib_points}. Needed every bit of that, ayuh.",
                    f"Crib gave me {crib_points}. Finally some wind in the sail.",
                    lane="trailing",
                )
            return _pick(
                f"Your crib got {crib_points}. That's not helpin my mood, bub.",
                f"You hauled {crib_points} from crib. Wicked rough for me.",
                lane="trailing",
            )
        if leading_mood:
            if bert_is_dealer:
                return _pick(
                    f"Bert crib pays {crib_points}. Efficient work.",
                    f"Dealer crib adds {crib_points}. Keep the pace.",
                    lane="leading",
                )
            return _pick(
                f"Your crib paid {crib_points}. Noted.",
                f"You took {crib_points} from crib. We continue.",
                lane="leading",
            )
        if crib_points <= 0:
            return _pick(
                "Crib came up lean. Happens to the best of us.",
                "Crib was all bones and no chowder this time.",
            )
        if bert_is_dealer:
            return _pick(
                f"Bert's crib pays {crib_points}. That's proper Maine math.",
                f"Dealer crib paid {crib_points} for Bert. That's harbor money, ayuh.",
            )
        return _pick(
            f"Your crib got {crib_points}. I'll allow it, bub.",
            f"Your crib paid {crib_points}. Decent haul for one toss.",
        )

    if event == "round_summary":
        hand_player = _to_int(context.get("player_hand_points"))
        hand_bert = _to_int(context.get("bert_hand_points"))
        crib = _to_int(context.get("crib_points"))
        pegging_player = _to_int(context.get("player_pegging_points"))
        pegging_bert = _to_int(context.get("bert_pegging_points"))
        if score_known:
            if mood in {"hot", "boiling"}:
                return _pick(
                    f"Round recap: pegs {pegging_bert} to {pegging_player}, hand {hand_bert} to {hand_player}, crib {crib}. I'm still pressin, bub.",
                    f"That's the book: peggin {pegging_bert}-{pegging_player}, hand count {hand_bert}-{hand_player}, crib {crib}. No soft next deal.",
                    lane="hot",
                )
            if trailing_mood:
                return _pick(
                    f"Round recap: pegs {pegging_bert}-{pegging_player}, hand {hand_bert}-{hand_player}, crib {crib}. Chip away, keep count clean.",
                    f"Hand closed: peggin {pegging_bert} to {pegging_player}, hand {hand_bert} to {hand_player}, crib {crib}. Still in it, ayuh.",
                    lane="trailing",
                )
            if leading_mood:
                return _pick(
                    f"Round recap: pegs {pegging_bert}-{pegging_player}, hand {hand_bert}-{hand_player}, crib {crib}. Keep the rail steady.",
                    f"Book for the hand: peggin {pegging_bert}-{pegging_player}, hand count {hand_bert}-{hand_player}, crib {crib}. Stay measured.",
                    lane="leading",
                )
        return _pick(
            f"Round summary: peggin {pegging_bert}-{pegging_player}, hand {hand_bert}-{hand_player}, crib {crib}.",
            "Hand's in the books. Cut card, throw two, and do it cleaner next deal.",
        )

    if event == "bert_won":
        if mood in {"hot", "boiling"}:
            if score_known:
                return _pick(
                    f"Bert got there {bert_score} to {player_score}. Hard tide, clean landing.",
                    f"Game to Bert, {bert_score} over {player_score}. Hauled that one in proper, ayuh.",
                    lane="hot",
                )
            return _pick(
                "Bert takes it. Hard water, clean boat.",
                "That's game for Bert. No drift, no gifts.",
                lane="hot",
            )
        if trailing_mood:
            if score_known:
                return _pick(
                    f"Bert got there {bert_score} to {player_score}. Ugly road, but we crossed first.",
                    f"Game to Bert, {bert_score} over {player_score}. Had to scrap for every peg, ayuh.",
                    lane="trailing",
                )
            return _pick(
                "Bert takes it. Wasn't pretty, but pretty don't move pegs.",
                "That's game for Bert. Hard grind, clean result.",
                lane="trailing",
            )
        if leading_mood:
            if score_known:
                return _pick(
                    f"Bert takes it {bert_score} to {player_score}. Clean board, clean finish.",
                    f"Game to Bert, {bert_score} over {player_score}. Proper pace all the way.",
                    lane="leading",
                )
            return _pick(
                "Bert takes the table. Quiet work done right.",
                "That's game for Bert. No drama needed.",
                lane="leading",
            )
        if score_known:
            return _pick(
                f"Bert takes it {bert_score} to {player_score}. Shuffle if ya want another lesson.",
                f"Game to Bert, {bert_score} over {player_score}. Tie up and run it again.",
            )
        return _pick(
            "Bert takes the table. Rerack if you've got the grit.",
            "That's game for Bert. Shuffle up and we'll settle it again.",
        )

    if event == "player_won":
        if mood in {"hot", "boiling"}:
            if score_known:
                return _pick(
                    "You got this one. I overpressed a touch. Won't repeat.",
                    "You took this one. Next round I tie tighter knots, bub.",
                    lane="hot",
                )
            return _pick(
                "You got this one. File it while it lasts.",
                "Fair enough. Bert recalibrates and answers back.",
                lane="hot",
            )
        if trailing_mood:
            if score_known:
                return _pick(
                    "You got this one. Ayuh, that's logged.",
                    "You took this one. Don't expect the same map next time, bub.",
                    lane="trailing",
                )
            return _pick(
                "You got this one. Enjoy it; I'll file it away.",
                "Fair enough, you won. Bert'll answer back next hand.",
                lane="trailing",
            )
        if leading_mood:
            if score_known:
                return _pick(
                    "You got this one. Well played.",
                    "You took this one. Noted and logged.",
                    lane="leading",
                )
            return _pick(
                "You won this one. We continue.",
                "Fair win. Reset and deal again.",
                lane="leading",
            )
        if score_known:
            return _pick(
                "You got this one. Don't get smug about it.",
                "You took this one. I'll remember that one.",
            )
        return _pick(
            "You got me this one. Enjoy it while it lasts.",
            "Fair win. Bert'll be back with sharper pegs.",
        )

    lines = _DOWNEAST_LINES.get(event)
    if not lines:
        return ""
    return random.choice(lines)


def choose_line(
    event: str,
    style: str,
    dad_ai_level: int,
    context: dict[str, Any] | None = None,
) -> str:
    if dad_ai_level >= 5:
        dad_ai_level = 5

    if dad_ai_level not in (4, 5):
        return ""

    context = context or {}
    player_score = _to_int(context.get("player_score"))
    bert_score = _to_int(context.get("bert_score"))
    score_gap = bert_score - player_score

    if dad_ai_level == 5:
        if style == "robot":
            barnabas_lines = _BARNABUS_ROBOT_LINES.get(event)
            if not barnabas_lines:
                return ""
            return _purge_bert_from_barnabas_text(random.choice(barnabas_lines))
        barnabas_lines = _BARNABUS_DOWNEAST_LINES.get(event)
        if not barnabas_lines:
            return ""
        line = random.choice(barnabas_lines)
        learning_ack = _level5_learning_ack(event, context)
        if learning_ack:
            line = f"{line} {learning_ack}"
        if score_gap <= -8:
            line = f"{line} {random.choice(_BARNABUS_VAMPIRE_TAILS)}"
        elif score_gap >= 8:
            line = f"{line} {random.choice(_BARNABUS_GENTLEMAN_TAILS)}"
        return _purge_bert_from_barnabas_text(line)

    # Keep Bert grounded and keep Barnabas distinct as the final lane.
    if style == "robot":
        bank = _ROBOT_LINES
        lines = bank.get(event)
        if not lines:
            return ""
        choice = random.choice(lines)
    else:
        global _ACTIVE_EVENT, _ACTIVE_CONTEXT
        _ACTIVE_EVENT = event
        _ACTIVE_CONTEXT = context
        try:
            choice = _choose_downeast_line(event, context)
        finally:
            _ACTIVE_EVENT = None
            _ACTIVE_CONTEXT = None
        if not choice:
            return ""
        overlay = _gap_progression_overlay(score_gap)
        if overlay:
            choice = f"{choice} {overlay}"

    return choice
