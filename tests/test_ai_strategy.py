from __future__ import annotations

import random

import ai_strategy
from game_state import GameState


def test_medium_discard_prefers_strong_run_keep_when_hand_ev_is_flat() -> None:
    hand = [
        "4_of_hearts",
        "5_of_clubs",
        "6_of_spades",
        "7_of_diamonds",
        "queen_of_hearts",
        "king_of_clubs",
    ]

    choice = ai_strategy.choose_discard_indices(
        dad_labels=hand,
        dad_ai_level=2,
        dealer_is_dad=False,
        canonical_deck_labels=list(hand) + ["ace_of_spades", "2_of_hearts"],
        score_labels_hand=lambda kept, starter, is_crib: 0,
    )

    assert sorted(choice) == [4, 5]


def test_hard_pegging_avoids_leading_five_when_safe_option_exists() -> None:
    hand = [
        "5_of_hearts",
        "10_of_clubs",
        "4_of_spades",
        "9_of_diamonds",
    ]

    choice = ai_strategy.choose_pegging_index(
        hand_labels=hand,
        current_total=0,
        dad_ai_level=3,
        value_for_15=lambda rank: (
            1 if rank == "ace" else 10 if rank in {"10", "jack", "queen", "king"} else int(rank)
        ),
        parse_label=lambda label: (label.split("_of_")[0], label.split("_of_")[1]),
        score_pegging_play=lambda pile: 0,
        label_card_factory=lambda label: label,
        current_pegging_labels=[],
        estimate_opponent_reply_risk=None,
    )

    assert choice == 2


def test_analyze_discard_options_returns_ranked_percentiles() -> None:
    hand = [
        "4_of_hearts",
        "5_of_clubs",
        "6_of_spades",
        "7_of_diamonds",
        "queen_of_hearts",
        "king_of_clubs",
    ]
    analysis = ai_strategy.analyze_discard_options(
        hand_labels=hand,
        dealer_is_player=False,
        canonical_deck_labels=list(hand) + ["ace_of_spades", "2_of_hearts", "9_of_clubs"],
        score_labels_hand=lambda kept, starter, is_crib: 0,
    )

    assert analysis
    assert analysis[0].expected_points >= analysis[-1].expected_points
    assert 0 <= analysis[-1].percentile <= 100
    assert 0 <= analysis[0].percentile <= 100


def test_brutal_pegging_uses_endgame_awareness_bias() -> None:
    hand = [
        "10_of_hearts",
        "4_of_clubs",
    ]

    choice = ai_strategy.choose_pegging_index(
        hand_labels=hand,
        current_total=11,
        dad_ai_level=4,
        value_for_15=lambda rank: (
            1 if rank == "ace" else 10 if rank in {"10", "jack", "queen", "king"} else int(rank)
        ),
        parse_label=lambda label: (label.split("_of_")[0], label.split("_of_")[1]),
        score_pegging_play=lambda pile: 2 if pile[-1] == "4_of_clubs" else 0,
        label_card_factory=lambda label: label,
        current_pegging_labels=[],
        estimate_opponent_reply_risk=None,
        own_score=118,
        opp_score=110,
        own_cards_remaining=2,
    )

    assert choice == 1


def test_level5_discard_uses_bert_agent(monkeypatch) -> None:
    class _FakeBert:
        def choose_discard(self, hand_labels, state, posture="balanced"):
            assert len(hand_labels) == 6
            assert isinstance(state, GameState)
            assert posture in {"balanced", "aggressive", "deliberate", "cutthroat"}
            return (2, 5)

        def set_posture(self, posture):
            assert posture in {"balanced", "aggressive", "deliberate", "cutthroat"}

    monkeypatch.setattr(ai_strategy, "get_bert_agent", lambda: _FakeBert())

    choice = ai_strategy.choose_discard_indices(
        dad_labels=[
            "4_of_hearts",
            "5_of_clubs",
            "6_of_spades",
            "7_of_diamonds",
            "queen_of_hearts",
            "king_of_clubs",
        ],
        dad_ai_level=5,
        dealer_is_dad=False,
        canonical_deck_labels=[],
        score_labels_hand=lambda kept, starter, is_crib: 0,
        game_state=GameState(),
    )

    assert choice == [2, 5]


def test_level5_pegging_uses_bert_agent(monkeypatch) -> None:
    class _FakeBert:
        def choose_pegging(self, hand_labels, current_total, state, posture="balanced"):
            assert hand_labels[0] == "10_of_hearts"
            assert current_total == 11
            assert isinstance(state, GameState)
            assert posture in {"balanced", "aggressive", "deliberate", "cutthroat"}
            return 1

        def set_posture(self, posture):
            assert posture in {"balanced", "aggressive", "deliberate", "cutthroat"}

    monkeypatch.setattr(ai_strategy, "get_bert_agent", lambda: _FakeBert())

    choice = ai_strategy.choose_pegging_index(
        hand_labels=["10_of_hearts", "4_of_clubs"],
        current_total=11,
        dad_ai_level=5,
        value_for_15=lambda rank: (
            1 if rank == "ace" else 10 if rank in {"10", "jack", "queen", "king"} else int(rank)
        ),
        parse_label=lambda label: (label.split("_of_")[0], label.split("_of_")[1]),
        score_pegging_play=lambda pile: 0,
        label_card_factory=lambda label: label,
        current_pegging_labels=[],
        game_state=GameState(),
    )

    assert choice == 1


def test_level5_posture_routing_deliberate_when_behind_by_five(monkeypatch) -> None:
    seen: dict[str, str] = {}

    class _FakeBert:
        def choose_discard(self, hand_labels, state, posture="balanced"):
            seen["posture"] = posture
            return (0, 1)

        def set_posture(self, posture):
            seen["set_posture"] = posture

    monkeypatch.setattr(ai_strategy, "get_bert_agent", lambda: _FakeBert())

    gs = GameState(scores=[66, 61])
    _ = ai_strategy.choose_discard_indices(
        dad_labels=[
            "4_of_hearts",
            "5_of_clubs",
            "6_of_spades",
            "7_of_diamonds",
            "queen_of_hearts",
            "king_of_clubs",
        ],
        dad_ai_level=5,
        dealer_is_dad=False,
        canonical_deck_labels=[],
        score_labels_hand=lambda kept, starter, is_crib: 0,
        game_state=gs,
    )

    assert seen["posture"] == "balanced"
    assert seen["set_posture"] == "balanced"


def test_level5_posture_routing_aggressive_when_trailing_by_fifteen(monkeypatch) -> None:
    seen: dict[str, str] = {}

    class _FakeBert:
        def choose_pegging(self, hand_labels, current_total, state, posture="balanced"):
            seen["posture"] = posture
            return 0

        def set_posture(self, posture):
            seen["set_posture"] = posture

    monkeypatch.setattr(ai_strategy, "get_bert_agent", lambda: _FakeBert())

    gs = GameState(scores=[85, 70])
    _ = ai_strategy.choose_pegging_index(
        hand_labels=["10_of_hearts", "4_of_clubs"],
        current_total=11,
        dad_ai_level=5,
        value_for_15=lambda rank: (
            1 if rank == "ace" else 10 if rank in {"10", "jack", "queen", "king"} else int(rank)
        ),
        parse_label=lambda label: (label.split("_of_")[0], label.split("_of_")[1]),
        score_pegging_play=lambda pile: 0,
        label_card_factory=lambda label: label,
        current_pegging_labels=[],
        game_state=gs,
    )

    assert seen["posture"] == "aggressive"
    assert seen["set_posture"] == "aggressive"


def test_level5_posture_routing_aggressive_when_trailing_by_twenty(monkeypatch) -> None:
    seen: dict[str, str] = {}

    class _FakeBert:
        def choose_pegging(self, hand_labels, current_total, state, posture="balanced"):
            seen["posture"] = posture
            return 0

        def set_posture(self, posture):
            seen["set_posture"] = posture

    monkeypatch.setattr(ai_strategy, "get_bert_agent", lambda: _FakeBert())

    gs = GameState(scores=[90, 70])
    _ = ai_strategy.choose_pegging_index(
        hand_labels=["10_of_hearts", "4_of_clubs"],
        current_total=11,
        dad_ai_level=5,
        value_for_15=lambda rank: (
            1 if rank == "ace" else 10 if rank in {"10", "jack", "queen", "king"} else int(rank)
        ),
        parse_label=lambda label: (label.split("_of_")[0], label.split("_of_")[1]),
        score_pegging_play=lambda pile: 0,
        label_card_factory=lambda label: label,
        current_pegging_labels=[],
        game_state=gs,
    )

    assert seen["posture"] == "aggressive"
    assert seen["set_posture"] == "aggressive"


def test_level5_posture_routing_cutthroat_when_trailing_by_twenty_two_plus(monkeypatch) -> None:
    seen: dict[str, str] = {}

    class _FakeBert:
        def choose_pegging(self, hand_labels, current_total, state, posture="balanced"):
            seen["posture"] = posture
            return 0

        def set_posture(self, posture):
            seen["set_posture"] = posture

    monkeypatch.setattr(ai_strategy, "get_bert_agent", lambda: _FakeBert())

    gs = GameState(scores=[95, 72])
    _ = ai_strategy.choose_pegging_index(
        hand_labels=["10_of_hearts", "4_of_clubs"],
        current_total=11,
        dad_ai_level=5,
        value_for_15=lambda rank: (
            1 if rank == "ace" else 10 if rank in {"10", "jack", "queen", "king"} else int(rank)
        ),
        parse_label=lambda label: (label.split("_of_")[0], label.split("_of_")[1]),
        score_pegging_play=lambda pile: 0,
        label_card_factory=lambda label: label,
        current_pegging_labels=[],
        game_state=gs,
    )

    assert seen["posture"] == "cutthroat"
    assert seen["set_posture"] == "cutthroat"


def test_level3_discard_simulation_uses_weighted_opponent_sampling(monkeypatch) -> None:
    recorded_weights: list[list[float]] = []
    recorded_population: list[list[str]] = []

    def _fake_choices(population, weights=None, k=1):
        # Capture weights passed to weighted sampling path.
        if weights is not None:
            recorded_weights.append(list(weights))
            recorded_population.append(list(population))
        return list(population[:k])

    monkeypatch.setattr(random, "choices", _fake_choices)

    hand = [
        "4_of_hearts",
        "5_of_clubs",
        "6_of_spades",
        "7_of_diamonds",
        "queen_of_hearts",
        "king_of_clubs",
    ]
    unseen = [
        "ace_of_spades",
        "2_of_hearts",
        "3_of_clubs",
        "10_of_diamonds",
        "jack_of_spades",
        "9_of_hearts",
    ]

    _ = ai_strategy.choose_discard_indices(
        dad_labels=hand,
        dad_ai_level=3,
        dealer_is_dad=False,
        canonical_deck_labels=hand + unseen,
        score_labels_hand=lambda kept, starter, is_crib: 0,
    )

    assert recorded_weights, "Expected weighted sampling to be used in level-3 simulation"
    assert recorded_population
    expected = [
        3.0 if ai_strategy._value_for_15(ai_strategy._parse_label(lbl)[0]) >= 10 else 1.0
        for lbl in recorded_population[0]
    ]
    assert recorded_weights[0] == expected
