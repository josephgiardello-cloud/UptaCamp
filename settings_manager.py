from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

SETTINGS_PATH = Path(__file__).resolve().parent / "uptacamp_settings.json"


@dataclass
class GameSettings:
    volume: float = 0.6
    animations_enabled: bool = True
    online_ai_level: int = 2

    def clamp(self) -> GameSettings:
        self.volume = max(0.0, min(1.0, float(self.volume)))
        if self.online_ai_level not in (1, 2, 3):
            self.online_ai_level = 2
        self.animations_enabled = bool(self.animations_enabled)
        return self


def load_settings(path: Path | None = None) -> GameSettings:
    file_path = path or SETTINGS_PATH
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return GameSettings()
    except (OSError, json.JSONDecodeError):
        return GameSettings()

    settings = GameSettings(
        volume=raw.get("volume", 0.6),
        animations_enabled=raw.get("animations_enabled", True),
        online_ai_level=raw.get("online_ai_level", 2),
    )
    return settings.clamp()


def save_settings(settings: GameSettings, path: Path | None = None) -> None:
    file_path = path or SETTINGS_PATH
    file_path.write_text(json.dumps(asdict(settings.clamp()), indent=2), encoding="utf-8")
