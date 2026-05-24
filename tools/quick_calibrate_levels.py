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

import cards as cribbage_cards
from cribbage_engine import CribbageEngine


@dataclass
class MatchResult:
    level: int
    winner: int | None
    rounds: int
    player_score: int
    ai_score: int


def _pick_player_discard(engine: CribbageEngine, rng: random.Random) -> list[int]:
    moves = engine.get_valid_moves()
    if not moves:
        return [0, 1]
    return list(rng.choice(moves))


def _pick_player_pegging(engine: CribbageEngine, valid: list[int], rng: random.Random) -> int | str:
    if not valid:
        return "go"

    hand = engine.state.player_hand
    pile = list(engine.state.pegging_pile)
    best_idx = int(valid[0])
    best_score = float("-inf")

    for idx in valid:
        card = hand[int(idx)]
        trial = pile + [card]
        now_pts = float(cribbage_cards.score_pegging_play(trial))
        total_after = cribbage_cards.pegging_total(trial)

        score = now_pts * 3.0
        if total_after in {15, 31}:
            score += 2.0
        if total_after in {11, 16, 21, 24}:
            score += 0.6
        if total_after in {5, 10, 20, 26}:
            score -= 0.6
        score -= abs(15 - total_after) * 0.03

        if score > best_score or (score == best_score and int(idx) < best_idx):
            best_score = score
            best_idx = int(idx)

    return best_idx


def _play_single(level: int, seed: int, max_rounds: int) -> MatchResult:
    rng = random.Random(seed)
    engine = CribbageEngine(seed=seed)
    engine.start_new_game(player_name="BenchPlayer", opponent_type="BenchAI")
    engine.state.dad_ai_level = int(level)

    rounds = 0
    while rounds < max_rounds and engine.state.phase != "game_over":
        rounds += 1

        if not engine.process_discard(_pick_player_discard(engine, rng)):
            break

        pegging_steps = 0
        while engine.state.phase == "pegging" and pegging_steps < 200:
            pegging_steps += 1
            if int(engine.state.player_turn) == 0:
                valid = engine.get_valid_moves()
                action = _pick_player_pegging(engine, valid, rng)
                engine.process_pegging_play(action)
            else:
                idx = engine.ai_pegging_move()
                if idx is None:
                    engine.process_pegging_play("go")
                else:
                    result = engine.process_pegging_play(int(idx))
                    if not bool(result.get("ok", False)):
                        valid = engine.get_valid_moves()
                        engine.process_pegging_play(valid[0] if valid else "go")

        if engine.state.phase == "counting":
            engine.end_hand_counting()

        if engine.state.phase == "end":
            engine.start_next_round()
            engine.state.dad_ai_level = int(level)

    return MatchResult(
        level=int(level),
        winner=engine.state.winner,
        rounds=int(rounds),
        player_score=int(engine.state.scores[0]),
        ai_score=int(engine.state.scores[1]),
    )


def run_benchmark(
    levels: list[int], games_per_level: int, seed_base: int, max_rounds: int, progress_every: int
) -> list[MatchResult]:
    results: list[MatchResult] = []
    done = 0
    total = max(1, len(levels) * max(1, games_per_level))

    for lane, level in enumerate(levels):
        for g in range(games_per_level):
            seed = seed_base + lane * 100000 + g
            results.append(_play_single(level=int(level), seed=seed, max_rounds=max_rounds))
            done += 1
            if progress_every > 0 and done % progress_every == 0:
                print(f"progress {done}/{total}")

    return results


def _summarize(results: list[MatchResult], level: int) -> str:
    lane = [r for r in results if r.level == int(level)]
    if not lane:
        return f"L{level}: no data"

    ai_wins = sum(1 for r in lane if r.winner == 1)
    player_wins = sum(1 for r in lane if r.winner == 0)
    unresolved = len(lane) - ai_wins - player_wins
    avg_rounds = statistics.mean(r.rounds for r in lane)
    avg_diff = statistics.mean(r.ai_score - r.player_score for r in lane)

    return (
        f"L{level}: games={len(lane)} ai_wins={ai_wins} player_wins={player_wins} "
        f"other={unresolved} avg_rounds={avg_rounds:.2f} avg_score_diff={avg_diff:.2f}"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fast level calibration benchmark on runtime engine"
    )
    parser.add_argument("--levels", nargs="+", type=int, default=[1, 2, 3, 4, 5])
    parser.add_argument("--games", type=int, default=120, help="Games per level")
    parser.add_argument("--seed-base", type=int, default=25000)
    parser.add_argument("--max-rounds", type=int, default=18, help="Round cap per game")
    parser.add_argument("--progress-every", type=int, default=20)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    levels = [int(v) for v in args.levels]
    games = max(1, int(args.games))

    results = run_benchmark(
        levels=levels,
        games_per_level=games,
        seed_base=int(args.seed_base),
        max_rounds=max(1, int(args.max_rounds)),
        progress_every=max(0, int(args.progress_every)),
    )

    print(
        f"Quick calibration complete: levels={levels}, games_per_level={games}, total={len(results)}"
    )
    for level in levels:
        print(_summarize(results, level))


if __name__ == "__main__":
    main()
