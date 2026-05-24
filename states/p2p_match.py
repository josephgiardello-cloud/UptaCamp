"""P2P match state — runs a full cribbage game between two players directly.

The host is the authoritative game controller.  After every state change the
host broadcasts the updated game state to the guest.  The guest renders what
it receives and sends actions (discard / peg / go) back.

Roles
-----
host (app.p2p_role == "host")
  - Runs the real game logic (deck, scoring, phase advancement).
  - Displays own hand; processes own UI events.
  - Processes incoming guest actions via app.p2p_host.get_incoming().
  - Calls app.p2p_host.send(state_dict) after each change.

guest (app.p2p_role == "guest")
  - Renders the latest snapshot received from the host.
  - Displays own hand (received from host).
  - Processes own UI events and sends action dicts to host.

Wire format (host → guest)
--------------------------
{
  "type":        "state",
  "phase":       "discard" | "pegging" | "counting" | "finished",
  "your_hand":   ["label", ...],      # guest's current cards
  "dealer":      0 | 1,               # 0 = host deals, 1 = guest deals
  "scores":      [host_pts, guest_pts],
  "starter":     null | "label",
  "peg_pile":    [{"label": "...", "by": "host"|"guest"}, ...],
  "peg_total":   int,
  "active":      "host" | "guest",
  "message":     "...",
  "host_hand":   null | [...],        # revealed only in counting phase
  "result":      null | { "your_hand": N, "their_hand": N,
                           "crib": N, "crib_owner": "host"|"guest" }
}

Wire format (guest → host)
--------------------------
{"type": "discard", "cards": ["label1", "label2"]}
{"type": "peg",     "card": "label"}
{"type": "go"}
{"type": "next_round"}   # acknowledge end-of-round, ready for next
{"type": "chat",    "text": "..."}
"""

from __future__ import annotations

import random
from typing import Any

import pygame

import cards as cribbage_cards
from engine import CribbageEngine

from .base import GameStateBase

# Win threshold (same as local game).
_WIN_SCORE = 121


def _card_value(label: str) -> int:
    rank, _ = cribbage_cards.parse_card_label(label)
    return cribbage_cards.value_for_fifteen(rank)


def _can_play_any(hand: list[str], total: int) -> bool:
    return any(_card_value(lbl) + total <= 31 for lbl in hand)


def _score_peg_pile(pile_labels: list[str]) -> int:
    pile_objs = [cribbage_cards.label_to_card(lbl) for lbl in pile_labels]
    return cribbage_cards.score_pegging_play(pile_objs)


def _score_hand(hand_labels: list[str], starter_label: str, is_crib: bool = False) -> int:
    hand_objs = [cribbage_cards.label_to_card(lbl) for lbl in hand_labels]
    starter_obj = cribbage_cards.label_to_card(starter_label)
    total, _ = cribbage_cards.score_hand(hand_objs, starter_obj, is_crib=is_crib)
    return total


class P2PMatchState(GameStateBase):
    """Handles a live P2P cribbage match for both host and guest."""

    def __init__(self) -> None:
        # Shared display state (kept in sync for both roles)
        self.phase: str = "init"  # init|discard|pegging|counting|finished
        self.my_hand: list[str] = []
        self.selected: set[int] = set()
        self.scores: list[int] = [0, 0]  # [host, guest]
        self.dealer: int = 0  # 0=host, 1=guest
        self.starter: str | None = None
        self.peg_pile: list[dict[str, str]] = []
        self.peg_total: int = 0
        self.active_player: str = "host"
        self.message: str = "Setting up…"
        self.host_hand_revealed: list[str] | None = None  # for counting reveal
        self.result: dict[str, Any] | None = None
        self.round_num: int = 1

        # Host-only authoritative state
        self._host_hand: list[str] = []
        self._guest_hand: list[str] = []
        self._stock: list[str] = []
        self._crib: list[str] = []
        self._host_kept: list[str] = []
        self._guest_kept: list[str] = []
        self._host_peg_hand: list[str] = []
        self._guest_peg_hand: list[str] = []
        self._host_discard: list[str] = []
        self._guest_discard: list[str] = []
        self._host_discard_done: bool = False
        self._guest_discard_done: bool = False
        self._peg_last_player: str | None = None
        self._initialized: bool = False

        # Guest-only: acknowledgement tracking
        self._sent_discard: bool = False
        self._sent_next_round: bool = False
        self._guest_waiting_next_round: bool = False

    # ================================================================== SHARED

    def handle_event(self, event: pygame.event.Event, engine, assets, app) -> object:
        if event.type != pygame.KEYDOWN:
            return self

        if event.key == pygame.K_ESCAPE:
            self._teardown(app)
            from .p2p_lobby import P2PLobbyState

            return P2PLobbyState()

        role: str = getattr(app, "p2p_role", "guest")

        if role == "host":
            self._handle_host_input(event, app)
        else:
            self._handle_guest_input(event, app)

        if self.phase == "_go_lobby":
            from .p2p_lobby import P2PLobbyState

            return P2PLobbyState()

        return self

    def update(self, engine, dt: int, app) -> object:
        role: str = getattr(app, "p2p_role", "guest")

        if role == "host":
            if not self._initialized:
                self._start_round(app)
                self._initialized = True
            self._host_update(app)
        else:
            self._guest_update(app)

        return None

    def _teardown(self, app) -> None:
        if getattr(app, "p2p_host", None):
            app.p2p_host.stop()
            app.p2p_host = None
        if getattr(app, "p2p_guest", None):
            app.p2p_guest.stop()
            app.p2p_guest = None

    # ================================================================== HOST

    def _start_round(self, app) -> None:
        """Deal cards and broadcast initial discard state to guest."""
        deck = list(CribbageEngine._canonical_deck_labels())
        random.shuffle(deck)
        self._host_hand = deck[:6]
        self._guest_hand = deck[6:12]
        self._stock = deck[12:]
        self._crib = []
        self._host_discard_done = False
        self._guest_discard_done = False
        self._host_discard = []
        self._guest_discard = []
        self.selected = set()
        self.my_hand = list(self._host_hand)
        self.phase = "discard"
        self.starter = None
        self.peg_pile = []
        self.peg_total = 0
        self.result = None
        self.host_hand_revealed = None
        self._peg_last_player = None

        dealer_label = "you" if self.dealer == 0 else "opponent"
        self.message = (
            f"Round {self.round_num}. Discard 2 cards to the crib. Dealer: {dealer_label}"
        )

        app.p2p_host.send(
            {
                "type": "state",
                "phase": "discard",
                "your_hand": list(self._guest_hand),
                "dealer": self.dealer,
                "scores": list(self.scores),
                "starter": None,
                "peg_pile": [],
                "peg_total": 0,
                "active": "",
                "message": f"Round {self.round_num}. Discard 2 cards to the crib. Dealer: {'opponent' if self.dealer == 0 else 'you'}",
                "host_hand": None,
                "result": None,
            }
        )

    def _handle_host_input(self, event: pygame.event.Event, app) -> None:
        if self.phase == "discard":
            # Number keys 1-6 toggle card selection
            digit = event.unicode
            if digit in "123456":
                idx = int(digit) - 1
                if idx < len(self.my_hand):
                    if idx in self.selected:
                        self.selected.discard(idx)
                    else:
                        self.selected.add(idx)
            elif event.key == pygame.K_RETURN and len(self.selected) == 2:
                self._host_submit_discard(app)

        elif self.phase == "pegging" and self.active_player == "host":
            digit = event.unicode
            if digit.isdigit():
                idx = int(digit) - 1
                if 0 <= idx < len(self.my_hand):
                    self._host_play_peg(idx, app)
            elif event.key == pygame.K_g:
                self._host_go(app)

        elif self.phase == "counting":
            if event.key == pygame.K_n:
                self._host_next_round(app)

        elif self.phase == "finished":
            if event.key == pygame.K_r:
                self._teardown(app)
                self.phase = "_go_lobby"

    def _host_submit_discard(self, app) -> None:
        cards = [self.my_hand[i] for i in sorted(self.selected)]
        self._host_discard = cards
        self._host_discard_done = True
        self.selected = set()
        self.message = "Waiting for opponent to discard…"

    def _host_update(self, app) -> None:
        """Process incoming guest messages and advance game state."""
        # Drain all pending messages
        while True:
            msg = app.p2p_host.get_incoming()
            if msg is None:
                break
            self._host_process_msg(msg, app)

        # Advance phases once preconditions are met
        if self.phase == "discard" and self._host_discard_done and self._guest_discard_done:
            self._host_advance_to_pegging(app)

        elif self.phase == "pegging":
            self._host_auto_advance_peg(app)

    def _host_process_msg(self, msg: dict[str, Any], app) -> None:
        mtype = msg.get("type", "")
        if mtype == "discard":
            cards = msg.get("cards", [])
            if len(cards) == 2 and all(c in self._guest_hand for c in cards):
                self._guest_discard = cards
                self._guest_discard_done = True
        elif mtype == "peg":
            if self.phase == "pegging" and self.active_player == "guest":
                card = msg.get("card", "")
                if card in self._guest_peg_hand:
                    self._host_play_peg_for(card, "guest", app)
        elif mtype == "go":
            if self.phase == "pegging" and self.active_player == "guest":
                self._do_go("guest", app)
        elif mtype == "next_round":
            if self.phase == "counting":
                self._host_next_round(app)
        elif mtype == "chat":
            text = str(msg.get("text", ""))[:200]
            guest_name = app.p2p_host.guest_name or "Guest"
            self.message = f"{guest_name}: {text}"
            app.p2p_host.send({"type": "chat", "from": "guest", "text": text})

    def _host_advance_to_pegging(self, app) -> None:
        # Apply discards
        for lbl in self._host_discard:
            self._host_hand.remove(lbl)
            self._crib.append(lbl)
        for lbl in self._guest_discard:
            self._guest_hand.remove(lbl)
            self._crib.append(lbl)

        self._host_kept = list(self._host_hand)
        self._guest_kept = list(self._guest_hand)
        self._host_peg_hand = list(self._host_hand)
        self._guest_peg_hand = list(self._guest_hand)

        # Cut starter from stock
        self.starter = self._stock.pop(0) if self._stock else "5_of_clubs"

        # Check jack nobs (2 pts if starter is a Jack, for the dealer)
        starter_rank, _ = cribbage_cards.parse_card_label(self.starter)
        if starter_rank.lower() in ("jack", "j"):
            self.scores[self.dealer] += 2

        # Non-dealer leads pegging
        self.active_player = "guest" if self.dealer == 0 else "host"
        self.peg_pile = []
        self.peg_total = 0
        self._peg_last_player = None
        self.my_hand = list(self._host_peg_hand)
        self.selected = set()
        self.phase = "pegging"

        your_turn = "your turn" if self.active_player == "host" else "opponent leads"
        self.message = f"Pegging! Starter: {self.starter}. {your_turn.capitalize()}."

        app.p2p_host.send(
            self._build_state_msg(
                your_hand=list(self._guest_peg_hand),
                message=f"Pegging! Starter: {self.starter}. {'your turn' if self.active_player == 'guest' else 'opponent leads'}.".capitalize(),
            )
        )

    def _host_play_peg(self, hand_idx: int, app) -> None:
        """Host plays a card from their peg hand by index into my_hand."""
        if hand_idx >= len(self.my_hand):
            return
        label = self.my_hand[hand_idx]
        if label not in self._host_peg_hand:
            return
        if _card_value(label) + self.peg_total > 31:
            self.message = f"Can't play {label} — would exceed 31."
            return
        self._host_play_peg_for(label, "host", app)

    def _host_play_peg_for(self, label: str, player: str, app) -> None:
        """Authoritative peg a card for player ('host' or 'guest')."""
        hand = self._host_peg_hand if player == "host" else self._guest_peg_hand
        if label not in hand:
            return
        v = _card_value(label)
        if v + self.peg_total > 31:
            return

        hand.remove(label)
        self.peg_pile.append({"label": label, "by": player})
        self.peg_total += v
        self._peg_last_player = player

        pile_labels = [e["label"] for e in self.peg_pile]
        pts = _score_peg_pile(pile_labels)
        pi = 0 if player == "host" else 1
        self.scores[pi] += pts

        pt_note = f" (+{pts})" if pts else ""
        name = app.p2p_host.host_name if player == "host" else (app.p2p_host.guest_name or "Guest")
        self.message = f"{name} plays {label}{pt_note}. Total: {self.peg_total}."

        if self.peg_total == 31:
            self.message += " — 31!"
            self.peg_pile.clear()
            self.peg_total = 0
            self._peg_last_player = None
            # Other player leads new count
            self.active_player = "guest" if player == "host" else "host"
        else:
            self.active_player = "guest" if player == "host" else "host"

        # Update my_hand to reflect host's remaining cards
        self.my_hand = list(self._host_peg_hand)
        self._broadcast_peg_state(app)

    def _do_go(self, player: str, app) -> None:
        """Process a 'go' from player; advance state accordingly."""
        other = "guest" if player == "host" else "host"
        other_hand = self._guest_peg_hand if player == "host" else self._host_peg_hand

        if _can_play_any(other_hand, self.peg_total):
            # Other player can still play
            self.active_player = other
            name = (
                app.p2p_host.host_name if player == "host" else (app.p2p_host.guest_name or "Guest")
            )
            self.message = f"{name} says go. {other.capitalize()}'s turn."
        else:
            # Both can't play — last card point and reset
            if self._peg_last_player:
                lcp_pi = 0 if self._peg_last_player == "host" else 1
                self.scores[lcp_pi] += 1
                lcp_name = (
                    app.p2p_host.host_name
                    if self._peg_last_player == "host"
                    else (app.p2p_host.guest_name or "Guest")
                )
                self.message = f"Both go. {lcp_name} scores 1 for last card."
            else:
                self.message = "Both go. Pile reset."
            self.peg_pile.clear()
            self.peg_total = 0
            self._peg_last_player = None
            # Non-dealer leads new sub-pile
            self.active_player = "guest" if self.dealer == 0 else "host"

        self.my_hand = list(self._host_peg_hand)
        self._broadcast_peg_state(app)

    def _host_auto_advance_peg(self, app) -> None:
        """Auto-go when the active player has no legal card. End pegging when
        all hands are empty."""
        if not self._host_peg_hand and not self._guest_peg_hand:
            self._end_pegging(app)
            return

        active_hand = self._host_peg_hand if self.active_player == "host" else self._guest_peg_hand
        if not active_hand:
            # Active player is out of cards — switch
            self.active_player = "guest" if self.active_player == "host" else "host"
            self._broadcast_peg_state(app)
            return

        if not _can_play_any(active_hand, self.peg_total):
            self._do_go(self.active_player, app)

    def _broadcast_peg_state(self, app) -> None:
        """Send current pegging state to guest."""
        your_turn = self.active_player == "guest"
        msg_txt = self.message + (" Your turn." if your_turn else "")
        app.p2p_host.send(
            self._build_state_msg(
                your_hand=list(self._guest_peg_hand),
                message=msg_txt,
            )
        )

    def _end_pegging(self, app) -> None:
        """Finalize pegging: award last-card point, move to counting."""
        if self._peg_last_player and self.peg_total != 31:
            pi = 0 if self._peg_last_player == "host" else 1
            self.scores[pi] += 1
            lcp_name = (
                app.p2p_host.host_name
                if self._peg_last_player == "host"
                else (app.p2p_host.guest_name or "Guest")
            )
            self.message = f"{lcp_name} scores 1 for last card. Counting hands…"
        else:
            self.message = "Pegging complete. Counting hands…"

        self.phase = "counting"
        self._do_counting(app)

    def _do_counting(self, app) -> None:
        """Score all hands, update scores, broadcast result."""
        starter = self.starter or "5_of_clubs"
        host_pts = _score_hand(self._host_kept, starter, is_crib=False)
        guest_pts = _score_hand(self._guest_kept, starter, is_crib=False)
        crib_pts = _score_hand(self._crib, starter, is_crib=True) if len(self._crib) == 4 else 0

        self.scores[0] += host_pts
        self.scores[1] += guest_pts
        self.scores[self.dealer] += crib_pts  # crib goes to dealer

        host_name = app.p2p_host.host_name
        guest_name = app.p2p_host.guest_name or "Guest"
        crib_owner_label = host_name if self.dealer == 0 else guest_name

        self.result = {
            "your_hand": guest_pts,
            "their_hand": host_pts,
            "crib": crib_pts,
            "crib_owner": "guest" if self.dealer == 1 else "host",
        }
        self.host_hand_revealed = list(self._host_kept)
        self.my_hand = list(self._host_kept)
        self.message = (
            f"Count: {host_name} {host_pts}pts, {guest_name} {guest_pts}pts, "
            f"Crib ({crib_owner_label}) {crib_pts}pts. "
            f"Scores: {self.scores[0]} – {self.scores[1]}. "
            f"Press N for next round."
        )

        # Check for winner
        winner_idx = next((i for i, s in enumerate(self.scores) if s >= _WIN_SCORE), None)
        if winner_idx is not None:
            winner = host_name if winner_idx == 0 else guest_name
            self.message = f"{winner} wins with {self.scores[winner_idx]} points! Press R to exit."
            self.phase = "finished"

        guest_result = {
            "your_hand": guest_pts,
            "their_hand": host_pts,
            "crib": crib_pts,
            "crib_owner": "guest" if self.dealer == 1 else "host",
        }
        guest_msg = (
            (
                f"Count: You {guest_pts}pts, {host_name} {host_pts}pts, "
                f"Crib ({crib_owner_label}) {crib_pts}pts. "
                f"Scores: {self.scores[0]} – {self.scores[1]}. "
                f"Press N for next round."
            )
            if self.phase != "finished"
            else f"{'You win' if winner_idx == 1 else host_name + ' wins'} with {self.scores[winner_idx]} pts!"
        )

        app.p2p_host.send(
            self._build_state_msg(
                your_hand=list(self._guest_kept),
                message=guest_msg,
                host_hand=list(self._host_kept),
                result=guest_result,
            )
        )

    def _host_next_round(self, app) -> None:
        if self.phase not in ("counting",):
            return
        self.dealer = 1 - self.dealer
        self.round_num += 1
        self._start_round(app)

    def _build_state_msg(
        self,
        your_hand: list[str],
        message: str,
        host_hand: list[str] | None = None,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "type": "state",
            "phase": self.phase,
            "your_hand": your_hand,
            "dealer": self.dealer,
            "scores": list(self.scores),
            "starter": self.starter,
            "peg_pile": list(self.peg_pile),
            "peg_total": self.peg_total,
            "active": self.active_player,
            "message": message,
            "host_hand": host_hand,
            "result": result,
        }

    # ================================================================== GUEST

    def _handle_guest_input(self, event: pygame.event.Event, app) -> None:
        if self.phase == "discard" and not self._sent_discard:
            if event.unicode in "123456":
                idx = int(event.unicode) - 1
                if idx < len(self.my_hand):
                    if idx in self.selected:
                        self.selected.discard(idx)
                    else:
                        self.selected.add(idx)
            elif event.key == pygame.K_RETURN and len(self.selected) == 2:
                cards = [self.my_hand[i] for i in sorted(self.selected)]
                app.p2p_guest.send({"type": "discard", "cards": cards})
                self._sent_discard = True
                self.selected = set()
                self.message = "Discard sent. Waiting for host…"

        elif self.phase == "pegging" and self.active_player == "guest":
            if event.unicode.isdigit():
                idx = int(event.unicode) - 1
                if 0 <= idx < len(self.my_hand):
                    card = self.my_hand[idx]
                    if _card_value(card) + self.peg_total <= 31:
                        app.p2p_guest.send({"type": "peg", "card": card})
                        self.message = f"Played {card}. Waiting…"
                    else:
                        self.message = f"Can't play {card} — would exceed 31."
            elif event.key == pygame.K_g:
                app.p2p_guest.send({"type": "go"})
                self.message = "Said go. Waiting…"

        elif self.phase == "counting" and not self._sent_next_round:
            if event.key == pygame.K_n:
                app.p2p_guest.send({"type": "next_round"})
                self._sent_next_round = True
                self._guest_waiting_next_round = True
                self.message = "Ready for next round. Waiting for host…"

    def _guest_update(self, app) -> None:
        """Process state messages received from the host."""
        while True:
            msg = app.p2p_guest.get_incoming()
            if msg is None:
                break
            if msg.get("type") == "state":
                self._apply_state(msg)
            elif msg.get("type") == "chat":
                self.message = f"Host: {msg.get('text', '')}"

        if not app.p2p_guest.connected and app.p2p_guest.last_error:
            self.message = f"Disconnected: {app.p2p_guest.last_error}"

    def _apply_state(self, state: dict[str, Any]) -> None:
        """Update local display from a host broadcast."""
        prev_phase = self.phase
        self.phase = str(state.get("phase", self.phase))
        self.my_hand = list(state.get("your_hand", self.my_hand))
        self.dealer = int(state.get("dealer", self.dealer))
        self.scores = list(state.get("scores", self.scores))
        self.starter = state.get("starter")
        self.peg_pile = list(state.get("peg_pile", self.peg_pile))
        self.peg_total = int(state.get("peg_total", self.peg_total))
        self.active_player = str(state.get("active", self.active_player))
        self.message = str(state.get("message", self.message))
        self.host_hand_revealed = state.get("host_hand")
        self.result = state.get("result")

        # Reset sent flags when host moves to a new round
        if self.phase == "discard" and prev_phase in ("counting", "finished", "init"):
            self.selected = set()
            self._sent_discard = False
            self._sent_next_round = False
            self._guest_waiting_next_round = False

    # ================================================================== DRAW

    def draw(self, screen: pygame.Surface, engine, assets, app) -> None:
        screen.fill((14, 36, 22))
        W, H = screen.get_width(), screen.get_height()
        title_font = pygame.font.SysFont(None, 42)
        body_font = pygame.font.SysFont(None, 30)
        small_font = pygame.font.SysFont(None, 24)
        card_font = pygame.font.SysFont(None, 26)

        role: str = getattr(app, "p2p_role", "guest")
        my_name = getattr(app, "p2p_name", role.capitalize())

        # Header
        header = title_font.render(
            f"P2P Cribbage — Round {self.round_num}  |  {my_name}  ({role.capitalize()})",
            True,
            (220, 240, 220),
        )
        screen.blit(header, header.get_rect(center=(W // 2, 28)))

        # Scores
        host_label = (
            app.p2p_host.host_name
            if role == "host" and getattr(app, "p2p_host", None)
            else (app.p2p_guest.host_name if getattr(app, "p2p_guest", None) else "Host")
        )
        guest_label = (
            app.p2p_host.guest_name
            if role == "host" and getattr(app, "p2p_host", None)
            else (app.p2p_guest.guest_name if getattr(app, "p2p_guest", None) else "Guest")
        ) or "Guest"
        score_txt = f"{host_label}: {self.scores[0]}   |   {guest_label}: {self.scores[1]}"
        score_s = body_font.render(score_txt, True, (180, 220, 180))
        screen.blit(score_s, score_s.get_rect(center=(W // 2, 60)))

        # Phase label
        phase_s = body_font.render(
            f"Phase: {self.phase.upper()}  |  Dealer: {'you' if self.dealer == (0 if role == 'host' else 1) else 'opponent'}",
            True,
            (160, 200, 255),
        )
        screen.blit(phase_s, phase_s.get_rect(center=(W // 2, 90)))

        # Starter card
        if self.starter:
            st_s = body_font.render(f"Starter: {self.starter}", True, (255, 220, 100))
            screen.blit(st_s, st_s.get_rect(center=(W // 2, 118)))

        # My hand
        hand_y = 160
        hand_label_s = body_font.render("Your hand:", True, (230, 230, 230))
        screen.blit(hand_label_s, (40, hand_y))

        for i, lbl in enumerate(self.my_hand):
            selected = i in self.selected
            card_rect = pygame.Rect(40 + i * 110, hand_y + 28, 100, 52)
            bg_col = (240, 220, 140) if selected else (240, 240, 240)
            border_col = (200, 160, 0) if selected else (80, 80, 80)
            pygame.draw.rect(screen, bg_col, card_rect, border_radius=6)
            pygame.draw.rect(screen, border_col, card_rect, width=2, border_radius=6)
            idx_s = small_font.render(str(i + 1), True, (100, 100, 100))
            screen.blit(idx_s, (card_rect.x + 4, card_rect.y + 4))
            card_s = card_font.render(lbl.replace("_of_", "\n"), True, (20, 20, 20))
            screen.blit(card_s, (card_rect.x + 8, card_rect.y + 16))

        # Host's revealed hand (during counting)
        if self.host_hand_revealed and role == "guest":
            reveal_y = hand_y + 110
            rl = body_font.render("Host's hand:", True, (200, 200, 200))
            screen.blit(rl, (40, reveal_y))
            for i, lbl in enumerate(self.host_hand_revealed):
                card_rect = pygame.Rect(40 + i * 110, reveal_y + 28, 100, 52)
                pygame.draw.rect(screen, (210, 210, 210), card_rect, border_radius=6)
                pygame.draw.rect(screen, (60, 60, 60), card_rect, width=2, border_radius=6)
                card_s = card_font.render(lbl.replace("_of_", "\n"), True, (30, 30, 30))
                screen.blit(card_s, (card_rect.x + 8, card_rect.y + 16))

        # Pegging pile
        if self.phase == "pegging" and self.peg_pile:
            peg_y = H - 200
            pl = body_font.render(f"Peg pile (total {self.peg_total}):", True, (200, 230, 200))
            screen.blit(pl, (40, peg_y))
            for i, entry in enumerate(self.peg_pile[-8:]):
                by_col = (180, 230, 180) if entry["by"] == role else (230, 180, 180)
                ps = small_font.render(f"{entry['label']} ({entry['by'][0].upper()})", True, by_col)
                screen.blit(ps, (40 + i * 140, peg_y + 28))

        # Message / controls
        msg_y = H - 120
        lines = self._wrap_text(self.message, body_font, W - 80)
        for li, line in enumerate(lines[:3]):
            ms = body_font.render(line, True, (245, 235, 200))
            screen.blit(ms, ms.get_rect(center=(W // 2, msg_y + li * 32)))

        # Controls hint
        hints = self._controls_hint()
        hs = small_font.render(hints, True, (140, 170, 140))
        screen.blit(hs, hs.get_rect(center=(W // 2, H - 26)))

    def _controls_hint(self) -> str:
        if self.phase == "discard":
            return "1-6) toggle select   Enter) confirm 2 cards   Esc) quit"
        if self.phase == "pegging":
            return "1-N) play card   G) go (pass)   Esc) quit"
        if self.phase == "counting":
            return "N) next round   Esc) quit"
        if self.phase == "finished":
            return "R) exit to lobby   Esc) quit"
        return "Esc) quit"

    @staticmethod
    def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            test = (current + " " + word).strip()
            if font.size(test)[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines
