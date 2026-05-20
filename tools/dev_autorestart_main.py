from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

WATCH_EXTENSIONS = {".py", ".toml"}
EXCLUDE_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "screenshots",
    "assets",
    "node_modules",
}

# Avoid rapid repeat restarts when many files are saved in quick succession.
RESTART_DEBOUNCE_SECONDS = 1.5


def should_watch(path: Path) -> bool:
    if any(part in EXCLUDE_PARTS for part in path.parts):
        return False
    return path.suffix.lower() in WATCH_EXTENSIONS


def snapshot() -> dict[str, float]:
    files: dict[str, float] = {}
    for path in ROOT.rglob("*"):
        if not path.is_file() or not should_watch(path):
            continue
        try:
            files[str(path)] = path.stat().st_mtime_ns
        except OSError:
            continue
    return files


def start_game(game_args: list[str]) -> subprocess.Popen[bytes]:
    cmd = [sys.executable, "main.py", *game_args]
    return subprocess.Popen(cmd, cwd=str(ROOT))


def stop_game(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--game-args",
        nargs=argparse.REMAINDER,
        default=[],
        help="Optional args forwarded to main.py (e.g. --ui-style competitive_minimal).",
    )
    args, _ = parser.parse_known_args()
    game_args = list(args.game_args)
    if game_args[:1] == ["--"]:
        game_args = game_args[1:]

    print("[watch] Starting Upta auto-restart watcher")
    print(f"[watch] Root: {ROOT}")
    if game_args:
        print(f"[watch] Forwarding game args: {' '.join(game_args)}")

    proc = start_game(game_args)
    print(f"[watch] Game PID: {proc.pid}")

    last = snapshot()
    last_restart = 0.0
    try:
        while True:
            time.sleep(1.0)

            if proc.poll() is not None:
                proc = start_game(game_args)
                print(f"[watch] Game restarted (exited). New PID: {proc.pid}")
                last = snapshot()
                continue

            current = snapshot()
            if current != last:
                now = time.time()
                if now - last_restart < RESTART_DEBOUNCE_SECONDS:
                    last = current
                    continue
                print("[watch] Source change detected, restarting game...")
                stop_game(proc)
                proc = start_game(game_args)
                print(f"[watch] Game PID: {proc.pid}")
                last_restart = now
                last = current
    except KeyboardInterrupt:
        print("[watch] Stopping watcher and game...")
        stop_game(proc)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
