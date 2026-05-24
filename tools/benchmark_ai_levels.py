#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
import statistics
import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ai_strategy
import cards as cribbage_cards
from engine import CribbageEngine


@dataclass
class MatchResult:
    level: int
    winner: int | None
    rounds: int
    player_score: int
    ai_score: int


@dataclass
class _LabeledCard:
    label: str


def _choose_player_pegging_move(
    engine: CribbageEngine,
    rng: random.Random,
    player_level: int,
) -> int | None:
    picked = ai_strategy.choose_pegging_index(
        hand_labels=[cribbage_cards.card_label(card) for card in engine.state.player_hand],
        current_total=int(engine.get_pegging_total()),
        dad_ai_level=int(player_level),
        value_for_15=cribbage_cards.value_for_fifteen,
        parse_label=cribbage_cards.parse_card_label,
        score_pegging_play=cribbage_cards.score_pegging_play,
        label_card_factory=cribbage_cards.label_to_card,
        current_pegging_labels=[
            cribbage_cards.card_label(card) for card in engine.state.pegging_pile
        ],
        game_state=engine.state,
    )
    if picked is None:
        return None
    picked_idx = int(picked)
    if engine.is_valid_pegging_play(
        player_idx=0,
        card_index=picked_idx,
        value_for_15=cribbage_cards.value_for_fifteen,
        parse_label=cribbage_cards.parse_card_label,
    ):
        return picked_idx
    legal = [
        idx
        for idx in range(len(engine.state.player_hand))
        if engine.is_valid_pegging_play(
            player_idx=0,
            card_index=idx,
            value_for_15=cribbage_cards.value_for_fifteen,
            parse_label=cribbage_cards.parse_card_label,
        )
    ]
    if not legal:
        return None
    return int(rng.choice(legal))


def _choose_player_discard_indices(
    engine: CribbageEngine, player_level: int, rng: random.Random
) -> list[int]:
    hand_labels = [cribbage_cards.card_label(card) for card in engine.state.player_hand]
    if len(hand_labels) != 6:
        moves = [list(pair) for pair in combinations(range(len(engine.state.player_hand)), 2)]
        return rng.choice(moves) if moves else [0, 1]
    picked = ai_strategy.choose_discard_indices(
        dad_labels=hand_labels,
        dad_ai_level=int(player_level),
        dealer_is_dad=bool(engine.state.dealer == 0),
        canonical_deck_labels=engine._canonical_deck_labels(),
        score_labels_hand=engine._score_labels_hand,
        game_state=engine.state,
    )
    if len(picked) != 2:
        return rng.sample(range(len(engine.state.player_hand)), 2)
    i1, i2 = int(picked[0]), int(picked[1])
    if (
        i1 == i2
        or i1 < 0
        or i2 < 0
        or i1 >= len(engine.state.player_hand)
        or i2 >= len(engine.state.player_hand)
    ):
        return rng.sample(range(len(engine.state.player_hand)), 2)
    return [i1, i2]


def _deal_round(rng: random.Random) -> tuple[list[_LabeledCard], list[_LabeledCard], list[str]]:
    labels = CribbageEngine._canonical_deck_labels()
    rng.shuffle(labels)
    player_labels = labels[:6]
    ai_labels = labels[6:12]
    stock_labels = labels[12:]
    player_hand = [_LabeledCard(lbl) for lbl in player_labels]
    ai_hand = [_LabeledCard(lbl) for lbl in ai_labels]
    return player_hand, ai_hand, stock_labels


def _play_single(level: int, seed: int, player_level: int) -> MatchResult:
    rng = random.Random(seed)
    engine = CribbageEngine()
    player_hand, ai_hand, stock_labels = _deal_round(rng)
    engine.start_new_game(
        player_hand=player_hand, ai_hand=ai_hand, stock_labels=stock_labels, dealer=0
    )
    engine.state.dad_ai_level = int(level)

    rounds = 0
    max_rounds = 260
    max_steps = 2200

    while rounds < max_rounds:
        rounds += 1
        steps = 0
        while steps < max_steps:
            steps += 1
            phase = str(engine.state.phase)

            if phase == "discard":
                if len(engine.state.player_hand) < 2:
                    return MatchResult(
                        level,
                        None,
                        rounds,
                        int(engine.state.scores[0]),
                        int(engine.state.scores[1]),
                    )
                choice = _choose_player_discard_indices(engine, player_level, rng)
                engine.handle_discard(choice)
                continue

            if phase == "pegging":
                turn = int(engine.state.player_turn)
                if turn == 0:
                    idx = _choose_player_pegging_move(engine, rng, player_level)
                    if idx is not None:
                        _ = engine.play_pegging_card(
                            player_idx=0,
                            card_index=idx,
                            score_pegging_play=cribbage_cards.score_pegging_play,
                            value_for_15=cribbage_cards.value_for_fifteen,
                            parse_label=cribbage_cards.parse_card_label,
                            player_name="BenchBot",
                        )
                    else:
                        _ = engine.pass_pegging_turn(0)
                else:
                    ai_valid = [
                        idx
                        for idx in range(len(engine.state.ai_hand))
                        if engine.is_valid_pegging_play(
                            player_idx=1,
                            card_index=idx,
                            value_for_15=cribbage_cards.value_for_fifteen,
                            parse_label=cribbage_cards.parse_card_label,
                        )
                    ]
                    total = int(engine.get_pegging_total())
                    if not ai_valid:
                        _ = engine.pass_pegging_turn(1)
                    else:
                        idx = engine.ai_pegging_move(
                            current_total=total,
                            value_for_15=cribbage_cards.value_for_fifteen,
                            parse_label=cribbage_cards.parse_card_label,
                            score_pegging_play=cribbage_cards.score_pegging_play,
                            label_card_factory=cribbage_cards.label_to_card,
                        )
                        if idx is None or int(idx) not in ai_valid:
                            idx = int(rng.choice(ai_valid))
                        _ = engine.play_pegging_card(
                            player_idx=1,
                            card_index=int(idx),
                            score_pegging_play=cribbage_cards.score_pegging_play,
                            value_for_15=cribbage_cards.value_for_fifteen,
                            parse_label=cribbage_cards.parse_card_label,
                            player_name="BenchBot",
                        )
                if engine.finalize_pegging_if_complete(engine.get_pegging_total):
                    continue
                continue

            if phase == "counting":
                try:
                    if not bool(engine.state.counting_resolved):
                        _ = engine.count_hands(cribbage_cards.label_to_card)
                    next_phase = str(getattr(engine.state, "counting_next_phase", "end") or "end")
                    if next_phase == "game_over":
                        engine.set_phase("game_over")
                    else:
                        engine.set_phase("end")
                except Exception:
                    return MatchResult(
                        level,
                        None,
                        rounds,
                        int(engine.state.scores[0]),
                        int(engine.state.scores[1]),
                    )
                continue

            if phase == "end":
                winner = engine.state.winner
                if winner is not None:
                    return MatchResult(
                        level,
                        int(winner),
                        rounds,
                        int(engine.state.scores[0]),
                        int(engine.state.scores[1]),
                    )
                player_hand, ai_hand, stock_labels = _deal_round(rng)
                engine.start_next_round(
                    player_hand=player_hand, ai_hand=ai_hand, stock_labels=stock_labels
                )
                engine.state.dad_ai_level = int(level)
                break

            if phase in {"game_over", "finished"}:
                winner = engine.state.winner
                if winner is not None:
                    return MatchResult(
                        level,
                        int(winner),
                        rounds,
                        int(engine.state.scores[0]),
                        int(engine.state.scores[1]),
                    )
                return MatchResult(
                    level, None, rounds, int(engine.state.scores[0]), int(engine.state.scores[1])
                )

            return MatchResult(
                level, None, rounds, int(engine.state.scores[0]), int(engine.state.scores[1])
            )

    winner = engine.state.winner
    if winner is not None:
        return MatchResult(
            level, int(winner), rounds, int(engine.state.scores[0]), int(engine.state.scores[1])
        )
    if engine.state.scores[0] != engine.state.scores[1]:
        return MatchResult(
            level,
            1 if engine.state.scores[1] > engine.state.scores[0] else 0,
            rounds,
            int(engine.state.scores[0]),
            int(engine.state.scores[1]),
        )
    return MatchResult(
        level, None, rounds, int(engine.state.scores[0]), int(engine.state.scores[1])
    )


def run_benchmark(
    levels: list[int], games_per_level: int, seed_base: int, player_level: int
) -> list[MatchResult]:
    results: list[MatchResult] = []
    offset = 0
    for level in levels:
        for g in range(games_per_level):
            seed = seed_base + offset + g
            results.append(_play_single(level, seed, player_level))
        offset += 10000
    return results


def _summarize(results: list[MatchResult], level: int) -> str:
    lane = [r for r in results if r.level == level]
    if not lane:
        return f"L{level}: no data"

    ai_wins = sum(1 for r in lane if r.winner == 1)
    player_wins = sum(1 for r in lane if r.winner == 0)
    ties_or_stalls = len(lane) - ai_wins - player_wins
    score_diffs = [r.ai_score - r.player_score for r in lane]
    avg_rounds = statistics.mean(r.rounds for r in lane)
    avg_diff = statistics.mean(score_diffs)

    return (
        f"L{level}: games={len(lane)} ai_wins={ai_wins} player_wins={player_wins} "
        f"other={ties_or_stalls} avg_rounds={avg_rounds:.2f} avg_score_diff={avg_diff:.2f}"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark AI levels with a configurable strategic player baseline"
    )
    parser.add_argument("--levels", nargs="+", type=int, default=[3, 5, 6])
    parser.add_argument("--games", type=int, default=60, help="Games per level")
    parser.add_argument("--seed-base", type=int, default=9000)
    parser.add_argument(
        "--player-level", type=int, default=3, help="Strategic baseline level for player actions"
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    levels = [int(x) for x in args.levels]
    games = max(1, int(args.games))

    results = run_benchmark(
        levels=levels,
        games_per_level=games,
        seed_base=int(args.seed_base),
        player_level=max(1, int(args.player_level)),
    )
    print(f"Benchmark complete: levels={levels}, games_per_level={games}, total={len(results)}")
    for level in levels:
        print(_summarize(results, level))


if __name__ == "__main__":
    main()
