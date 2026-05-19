from __future__ import annotations

import ai_strategy


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
