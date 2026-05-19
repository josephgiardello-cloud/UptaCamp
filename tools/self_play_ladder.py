from __future__ import annotations

import argparse
import random
from dataclasses import dataclass

from online_backend import OnlineBackend


@dataclass(frozen=True)
class BotSpec:
    player_id: str
    display_name: str
    level: int
    strength: float


def _win_probability(strength_a: float, strength_b: float) -> float:
    # Logistic mapping gives stable, monotonic win-rate behavior.
    return 1.0 / (1.0 + pow(2.718281828, -(strength_a - strength_b)))


def run_ladder(
    backend: OnlineBackend,
    bots: list[BotSpec],
    rounds_per_pair: int,
    seed: int,
) -> None:
    random.seed(seed)

    for bot in bots:
        backend.upsert_player(bot.player_id, bot.display_name)

    for i in range(len(bots)):
        for j in range(i + 1, len(bots)):
            a = bots[i]
            b = bots[j]
            p_a = _win_probability(a.strength, b.strength)

            for r in range(rounds_per_pair):
                invite = backend.create_invite(a.player_id)
                match_id = backend.accept_invite(invite, b.player_id)

                roll = random.random()
                if roll < p_a:
                    winner = a.player_id
                elif roll < (p_a + (1.0 - p_a) * 0.05):
                    winner = None
                else:
                    winner = b.player_id

                backend.finish_match(match_id, winner)

                backend.record_bot_decision(
                    phase="self_play",
                    ai_level=max(a.level, b.level),
                    state_hash=f"selfplay:{a.player_id}:{b.player_id}:{r}",
                    candidates=[
                        {"bot": a.player_id, "strength": a.strength},
                        {"bot": b.player_id, "strength": b.strength},
                    ],
                    selected_action=winner or "draw",
                    expected_value=p_a,
                    match_id=match_id,
                )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run bot self-play ladder")
    parser.add_argument("--db", default="online_state.db")
    parser.add_argument("--rounds-per-pair", type=int, default=100)
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()

    backend = OnlineBackend(args.db)
    bots = [
        BotSpec("bot_easy", "Bot Easy", level=1, strength=-0.6),
        BotSpec("bot_medium", "Bot Medium", level=2, strength=0.0),
        BotSpec("bot_hard", "Bot Hard", level=3, strength=0.9),
    ]
    run_ladder(backend, bots, rounds_per_pair=args.rounds_per_pair, seed=args.seed)

    for bot in bots:
        profile = backend.get_player_profile(bot.player_id)
        print(
            f"{bot.display_name}: rating={profile['rating']} "
            f"W-L-D={profile['wins']}-{profile['losses']}-{profile['draws']}"
        )


if __name__ == "__main__":
    main()
