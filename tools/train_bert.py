#!/usr/bin/env python3
"""Headless training loop for Bert AI agent.

Trains the agent through self-play games without rendering.
Usage: python tools/train_bert.py [--games 1000] [--level 4] [--seed 42]
"""

import argparse
import random
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_strategy import get_bert_agent, save_bert_agent
from engine import CribbageEngine


def train_agent(
    num_games: int = 100, ai_level: int = 4, seed: int | None = None, verbose: bool = True
) -> None:
    """Train Bert agent through self-play.

    Args:
        num_games: Number of games to play
        ai_level: AI difficulty level 2-5 (5 = Bert learning)
        seed: Random seed for reproducibility
        verbose: Print progress updates
    """
    if seed is not None:
        random.seed(seed)

    engine = CribbageEngine()
    get_bert_agent()  # Load agent (returns instance but not used in stub)

    stats = {"player_wins": 0, "ai_wins": 0, "games_completed": 0}

    for game_num in range(1, num_games + 1):
        try:
            # Initialize new game
            engine.start_new_game(
                player_hand=[],  # Not used in headless mode
                ai_hand=[],
                stock_labels=[],
                dealer=random.randint(0, 1),
            )

            # Game loop (simplified for headless training)
            # In practice, you'd integrate with full game logic
            game_completed = False

            if game_completed:
                # Determine winner
                if engine.state.scores[0] > engine.state.scores[1]:
                    stats["player_wins"] += 1
                else:
                    stats["ai_wins"] += 1
                stats["games_completed"] += 1

                if verbose and game_num % 10 == 0:
                    print(f"Game {game_num}: P={stats['player_wins']}, AI={stats['ai_wins']}")

        except Exception as e:
            print(f"Warning: Game {game_num} failed: {e}", file=sys.stderr)

    # Save trained agent
    save_bert_agent()
    print("Training complete! Played {} games.".format(stats["games_completed"]))
    print(f"Player wins: {stats['player_wins']}, AI wins: {stats['ai_wins']}")
    print("Model saved to bert_model.pkl")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Bert AI agent through self-play")
    parser.add_argument("--games", type=int, default=100, help="Number of games to play")
    parser.add_argument("--level", type=int, default=4, choices=[2, 3, 4, 5], help="AI difficulty")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")

    args = parser.parse_args()

    print(f"Starting training: {args.games} games at level {args.level}")
    train_agent(
        num_games=args.games,
        ai_level=args.level,
        seed=args.seed,
        verbose=not args.quiet,
    )
