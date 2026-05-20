from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class BertPersonaConfig:
    style: str = "downeast"


_DOWNEAST_LINES: dict[str, list[str]] = {
    "level_selected": [
        "Ayuh. Bert's sittin in now.",
        "Pull up, bub. Bert's at the table.",
        "Bert's in the chair. Let's play cahds.",
    ],
    "game_start": [
        "Cahds on the wood. Let's have a hand.",
        "Alright then, shuffle up and deal.",
        "Settle in now. We got cribbage to play.",
    ],
    "cards_dealt": [
        "Hand's in. Show me what ya got.",
        "Cahds are dealt. Keep it tidy now.",
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
}


def choose_line(event: str, style: str, dad_ai_level: int) -> str:
    if dad_ai_level not in (4, 5):
        return ""

    # Keep Bert (4) slightly more grounded and Bert+ (5) a bit sharper.
    if style == "robot":
        bank = _ROBOT_LINES
    else:
        bank = _DOWNEAST_LINES

    lines = bank.get(event)
    if not lines:
        return ""

    choice = random.choice(lines)
    if dad_ai_level == 5 and style == "robot":
        return f"{choice} ADAPTIVE PROFILE ACTIVE."
    if dad_ai_level == 5 and style == "downeast":
        if event in ("bert_won", "pegging_31"):
            return f"{choice} Bert Plus saw that line two plays ago."
        if not choice.endswith("."):
            return choice + "."
    return choice
