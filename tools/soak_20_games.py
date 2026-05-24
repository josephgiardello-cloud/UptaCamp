from __future__ import annotations

import argparse
import random
from dataclasses import dataclass

from cribbage_engine import CribbageEngine


@dataclass
class GameIssue:
    game: int
    round_index: int
    phase: str
    message: str


def run_game(game_idx: int, seed: int) -> tuple[int | None, int, list[GameIssue]]:
    rng = random.Random(seed)
    engine = CribbageEngine(seed=seed)
    engine.start_new_game(player_name="SoakBot", opponent_type="Bert", seed=seed)

    issues: list[GameIssue] = []
    rounds = 0
    max_rounds = 120
    max_steps_per_round = 1200

    while rounds < max_rounds:
        rounds += 1
        steps = 0
        while steps < max_steps_per_round:
            steps += 1
            phase = str(engine.state.phase)

            if len(engine.state.player_hand) > 6 or len(engine.state.ai_hand) > 6:
                issues.append(GameIssue(game_idx, rounds, phase, "Hand length exceeded 6 cards"))
                return None, rounds, issues

            if phase == "discard":
                if len(engine.state.player_hand) != 6 or len(engine.state.ai_hand) != 6:
                    issues.append(
                        GameIssue(
                            game_idx, rounds, phase, "Discard phase started with invalid hand size"
                        )
                    )
                    return None, rounds, issues
                combos = engine.get_valid_moves()
                if not combos:
                    issues.append(GameIssue(game_idx, rounds, phase, "No discard moves available"))
                    return None, rounds, issues
                choice = rng.choice(combos)
                ok = engine.handle_discard(choice)
                if not ok:
                    issues.append(
                        GameIssue(
                            game_idx,
                            rounds,
                            phase,
                            f"handle_discard rejected legal choice {choice}",
                        )
                    )
                    return None, rounds, issues
                continue

            if phase == "pegging":
                turn = int(engine.state.player_turn)
                valid = engine.get_valid_moves()
                if valid:
                    idx = int(rng.choice(valid))
                    _ = engine.play_pegging_card(turn, idx)
                else:
                    result = engine.pass_pegging_turn(turn)
                    if not result.get("ok"):
                        issues.append(
                            GameIssue(
                                game_idx,
                                rounds,
                                phase,
                                f"pass_pegging_turn failed for player {turn}",
                            )
                        )
                        return None, rounds, issues
                continue

            if phase == "counting":
                try:
                    _ = engine.end_hand_counting()
                except Exception as exc:  # pragma: no cover - soak runner guard
                    issues.append(
                        GameIssue(game_idx, rounds, phase, f"end_hand_counting exception: {exc}")
                    )
                    return None, rounds, issues
                continue

            if phase == "end":
                winner = engine.state.winner
                if winner is not None:
                    return int(winner), rounds, issues
                engine.start_next_round()
                break

            issues.append(GameIssue(game_idx, rounds, phase, f"Unknown phase '{phase}'"))
            return None, rounds, issues

        else:
            issues.append(
                GameIssue(
                    game_idx,
                    rounds,
                    str(engine.state.phase),
                    "Round step limit exceeded (potential stall)",
                )
            )
            return None, rounds, issues

    issues.append(
        GameIssue(
            game_idx,
            rounds,
            str(engine.state.phase),
            "Game round limit exceeded (potential endless game)",
        )
    )
    return None, rounds, issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Run automated CribbageEngine soak simulation")
    parser.add_argument("--games", type=int, default=20, help="Number of full games to simulate")
    parser.add_argument("--seed-base", type=int, default=4300, help="Base seed offset")
    args = parser.parse_args()

    total_games = max(1, int(args.games))
    seed_base = int(args.seed_base)
    winners = {0: 0, 1: 0, -1: 0}
    all_issues: list[GameIssue] = []
    rounds_total = 0

    for game_idx in range(1, total_games + 1):
        winner, rounds, issues = run_game(game_idx, seed=seed_base + game_idx)
        rounds_total += rounds
        all_issues.extend(issues)
        if winner is None:
            continue
        winners[winner] = winners.get(winner, 0) + 1

    print(f"Games run: {total_games}")
    print(f"Average rounds/game: {rounds_total / total_games:.2f}")
    print(
        f"Winners -> Player: {winners.get(0, 0)}, Bert: {winners.get(1, 0)}, Tie: {winners.get(-1, 0)}"
    )
    print(f"Issues found: {len(all_issues)}")

    for issue in all_issues[:40]:
        print(f"[game {issue.game} round {issue.round_index} phase={issue.phase}] {issue.message}")


if __name__ == "__main__":
    main()
