from __future__ import annotations

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
        def choose_discard(self, hand_labels, state):
            assert len(hand_labels) == 6
            assert isinstance(state, GameState)
            return (2, 5)

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
        def choose_pegging(self, hand_labels, current_total, state):
            assert hand_labels[0] == "10_of_hearts"
            assert current_total == 11
            assert isinstance(state, GameState)
            return 1

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
