#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cribbage_engine import CribbageEngine


@dataclass
class MatchResult:
    level: int
    winner: int | None
    rounds: int
    player_score: int
    ai_score: int


def _play_single(level: int, seed: int) -> MatchResult:
    rng = random.Random(seed)
    engine = CribbageEngine(seed=seed)
    engine.start_new_game(player_name="BenchBot", opponent_type="Bert", seed=seed)
    engine.state.dad_ai_level = int(level)

    rounds = 0
    max_rounds = 120
    max_steps = 1400

    while rounds < max_rounds:
        rounds += 1
        steps = 0
        while steps < max_steps:
            steps += 1
            phase = str(engine.state.phase)

            if phase == "discard":
                moves = engine.get_valid_moves()
                if not moves:
                    return MatchResult(level, None, rounds, int(engine.state.scores[0]), int(engine.state.scores[1]))
                choice = rng.choice(moves)
                if not engine.handle_discard(choice):
                    return MatchResult(level, None, rounds, int(engine.state.scores[0]), int(engine.state.scores[1]))
                continue

            if phase == "pegging":
                turn = int(engine.state.player_turn)
                valid = engine.get_valid_moves()
                if valid:
                    idx = int(rng.choice(valid))
                    _ = engine.play_pegging_card(turn, idx)
                else:
                    result = engine.pass_pegging_turn(turn)
                    if not bool(result.get("ok", False)):
                        return MatchResult(level, None, rounds, int(engine.state.scores[0]), int(engine.state.scores[1]))
                continue

            if phase == "counting":
                try:
                    _ = engine.end_hand_counting()
                except Exception:
                    return MatchResult(level, None, rounds, int(engine.state.scores[0]), int(engine.state.scores[1]))
                continue

            if phase == "end":
                winner = engine.state.winner
                if winner is not None:
                    return MatchResult(level, int(winner), rounds, int(engine.state.scores[0]), int(engine.state.scores[1]))
                engine.start_next_round()
                engine.state.dad_ai_level = int(level)
                break

            return MatchResult(level, None, rounds, int(engine.state.scores[0]), int(engine.state.scores[1]))

    return MatchResult(level, None, rounds, int(engine.state.scores[0]), int(engine.state.scores[1]))


def run_benchmark(levels: list[int], games_per_level: int, seed_base: int) -> list[MatchResult]:
    results: list[MatchResult] = []
    offset = 0
    for level in levels:
        for g in range(games_per_level):
            seed = seed_base + offset + g
            results.append(_play_single(level, seed))
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
    parser = argparse.ArgumentParser(description="Benchmark AI levels with randomized legal player actions")
    parser.add_argument("--levels", nargs="+", type=int, default=[3, 5, 6])
    parser.add_argument("--games", type=int, default=60, help="Games per level")
    parser.add_argument("--seed-base", type=int, default=9000)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    levels = [int(x) for x in args.levels]
    games = max(1, int(args.games))

    results = run_benchmark(levels=levels, games_per_level=games, seed_base=int(args.seed_base))
    print(f"Benchmark complete: levels={levels}, games_per_level={games}, total={len(results)}")
    for level in levels:
        print(_summarize(results, level))


if __name__ == "__main__":
    main()
