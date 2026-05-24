#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ai_strategy
from train_bert import train


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train Barnabas from Bert baseline and specialize level-6 behavior"
    )
    parser.add_argument("--episodes", type=int, default=18000)
    parser.add_argument("--model-path", type=Path, default=Path("barnabas_model.pkl"))
    parser.add_argument("--bert-model", type=Path, default=Path("bert_model.pkl"))
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Copy Bert model into Barnabas model before training",
    )
    parser.add_argument("--overwrite-bootstrap", action="store_true")
    parser.add_argument("--seed", type=int, default=89)
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    random.seed(int(args.seed))

    if args.bootstrap:
        copied = ai_strategy.bootstrap_barnabas_from_bert(
            bert_path=args.bert_model,
            barnabas_path=args.model_path,
            overwrite=bool(args.overwrite_bootstrap),
        )
        if copied:
            print(f"Bootstrapped Barnabas model from {args.bert_model} -> {args.model_path}")
        else:
            print("Bootstrap skipped (source missing or target exists without overwrite).")

    train(
        episodes=max(1, int(args.episodes)),
        model_path=args.model_path,
        learning_rate=0.09,
        discount=0.95,
        epsilon=0.06,
        epsilon_decay=0.99945,
        min_epsilon=0.0,
    )

    ai_strategy.load_barnabas_agent(args.model_path)
    ai_strategy.save_barnabas_agent(args.model_path)
    print(f"Barnabas training complete. Saved specialized model to {args.model_path}")


if __name__ == "__main__":
    main()
