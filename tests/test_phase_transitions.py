from types import SimpleNamespace

import pygame

import cribbage_pygame as game


class _DummyRect:
    def __init__(self, token):
        self._token = token

    def collidepoint(self, pos):
        return pos == self._token


class _DummyCard:
    def __init__(self, label, token):
        self.label = label
        self.rect = _DummyRect(token)
        self.image = None


def _make_hand(labels, prefix):
    return [_DummyCard(label, (prefix, idx)) for idx, label in enumerate(labels)]


def test_discard_phase_transitions_to_pegging(monkeypatch):
    # Arrange a deterministic discard flow.
    game.game_phase = "discard"
    game.dealer = 0
    game.crib.clear()
    game.selected_cards.clear()
    game.player1_kept.clear()
    game.player2_kept.clear()
    game.pegging_passes[:] = [False, False]
    game.last_pegging_player = 1

    p1_labels = [
        "ace_of_spades", "2_of_spades", "3_of_spades", "4_of_spades", "5_of_spades", "6_of_spades"
    ]
    p2_labels = [
        "ace_of_hearts", "2_of_hearts", "3_of_hearts", "4_of_hearts", "5_of_hearts", "6_of_hearts"
    ]

    game.player1_hand[:] = _make_hand(p1_labels, "p1")
    game.player2_hand[:] = _make_hand(p2_labels, "p2")
    game._stock_labels[:] = ["7_of_clubs"]
    game.starter_card = None

    monkeypatch.setattr(game, "_choose_dad_discards", lambda: [0, 1])

    # Act: click two player cards.
    event1 = SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, pos=("p1", 0))
    event2 = SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, pos=("p1", 1))
    game.handle_discard(event1)
    game.handle_discard(event2)

    # Assert transition and resulting hand/crib state.
    assert game.game_phase == "pegging"
    assert len(game.player1_hand) == 4
    assert len(game.player2_hand) == 4
    assert len(game.crib) == 4
    assert game.starter_card == "7_of_clubs"
    assert game.player_turn == 1  # non-dealer leads pegging
    assert game.pegging_passes == [False, False]
    assert game.last_pegging_player is None


def test_finalize_pegging_moves_to_counting_with_last_card_point():
    game.game_phase = "pegging"
    game.player1_hand[:] = []
    game.player2_hand[:] = []
    game.pegging_pile[:] = [SimpleNamespace(label="10_of_clubs"), SimpleNamespace(label="9_of_hearts")]
    game.player_scores[:] = [0, 0]
    game.last_pegging_player = 0

    changed = game._finalize_pegging_if_complete()

    assert changed is True
    assert game.game_phase == "counting"
    assert game.player_scores[0] == 1
    assert "Counting hands" in game.message


def test_handle_counting_moves_to_end_when_no_winner():
    game.game_phase = "counting"
    game.player_scores[:] = [10, 12]
    game.dealer = 1

    # Set 4-card kept hands and crib with known labels.
    game.player1_kept[:] = _make_hand(["2_of_clubs", "3_of_diamonds", "4_of_hearts", "5_of_spades"], "k1")
    game.player2_kept[:] = _make_hand(["6_of_clubs", "7_of_diamonds", "8_of_hearts", "9_of_spades"], "k2")
    game.crib[:] = _make_hand(["ace_of_clubs", "2_of_hearts", "3_of_spades", "4_of_diamonds"], "cr")
    game.starter_card = "5_of_clubs"

    game.handle_counting()

    assert game.game_phase == "end"
    assert "Counted:" in game.message
