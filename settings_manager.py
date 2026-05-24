from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from runtime_paths import resource_path, writable_path

SETTINGS_PATH = writable_path("uptacamp_settings.json")
BUNDLED_SETTINGS_PATH = resource_path("uptacamp_settings.json")


@dataclass
class GameSettings:
    volume: float = 0.6
    animations_enabled: bool = True
    online_ai_level: int = 2
    ui_style: str = "classic"
    background_theme: str = "auto"
    dark_shadows_unlocked: bool = False
    bert_voice_enabled: bool = True
    bert_voice_style: str = "downeast"
    bert_voice_backend: str = "local_ai"
    bert_local_model_path: str = "bert_voice_models/en_US-joe-medium.onnx"
    barnabas_local_model_path: str = ""
    bert_local_exe_path: str = "piper"
    bert_rvc_enabled: bool = False
    bert_rvc_exe_path: str = "rvc_infer"
    bert_rvc_model_path: str = ""
    bert_rvc_index_path: str = ""
    bert_rvc_pitch_shift: int = 0
    player_name: str = "Player"

    def clamp(self) -> GameSettings:
        self.volume = max(0.0, min(1.0, float(self.volume)))
        if self.online_ai_level not in (1, 2, 3):
            self.online_ai_level = 2
        self.animations_enabled = bool(self.animations_enabled)
        if self.ui_style not in (
            "classic",
            "competitive_minimal",
            "broadcast_table",
            "premium_tabletop",
        ):
            self.ui_style = "classic"
        if self.background_theme not in ("classic", "auto", "wharf", "dark_shadows"):
            self.background_theme = "auto"
        self.dark_shadows_unlocked = bool(self.dark_shadows_unlocked)
        if self.background_theme == "dark_shadows" and not self.dark_shadows_unlocked:
            self.background_theme = "auto"
        self.bert_voice_enabled = bool(self.bert_voice_enabled)
        if self.bert_voice_style not in ("robot", "downeast"):
            self.bert_voice_style = "downeast"
        if self.bert_voice_backend not in ("sapi", "local_ai"):
            self.bert_voice_backend = "sapi"
        self.bert_local_model_path = str(self.bert_local_model_path or "").strip()
        self.barnabas_local_model_path = str(self.barnabas_local_model_path or "").strip()
        self.bert_local_exe_path = str(self.bert_local_exe_path or "piper").strip() or "piper"
        self.bert_rvc_enabled = bool(self.bert_rvc_enabled)
        self.bert_rvc_exe_path = str(self.bert_rvc_exe_path or "rvc_infer").strip() or "rvc_infer"
        self.bert_rvc_model_path = str(self.bert_rvc_model_path or "").strip()
        self.bert_rvc_index_path = str(self.bert_rvc_index_path or "").strip()
        self.bert_rvc_pitch_shift = int(max(-24, min(24, int(self.bert_rvc_pitch_shift))))
        self.player_name = (str(self.player_name or "").strip() or "Player")[:24]
        return self


def load_settings(path: Path | None = None) -> GameSettings:
    file_path = path or SETTINGS_PATH
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if path is None and BUNDLED_SETTINGS_PATH.exists():
            try:
                raw = json.loads(BUNDLED_SETTINGS_PATH.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return GameSettings()
        else:
            return GameSettings()
    except (OSError, json.JSONDecodeError):
        return GameSettings()

    settings = GameSettings(
        volume=raw.get("volume", 0.6),
        animations_enabled=raw.get("animations_enabled", True),
        online_ai_level=raw.get("online_ai_level", 2),
        ui_style=raw.get("ui_style", "classic"),
        background_theme=raw.get("background_theme", "auto"),
        dark_shadows_unlocked=raw.get("dark_shadows_unlocked", False),
        bert_voice_enabled=raw.get("bert_voice_enabled", True),
        bert_voice_style=raw.get("bert_voice_style", "downeast"),
        bert_voice_backend=raw.get("bert_voice_backend", "local_ai"),
        bert_local_model_path=raw.get("bert_local_model_path", "bert_voice_models/en_US-joe-medium.onnx"),
        barnabas_local_model_path=raw.get("barnabas_local_model_path", ""),
        bert_local_exe_path=raw.get("bert_local_exe_path", "piper"),
        bert_rvc_enabled=raw.get("bert_rvc_enabled", False),
        bert_rvc_exe_path=raw.get("bert_rvc_exe_path", "rvc_infer"),
        bert_rvc_model_path=raw.get("bert_rvc_model_path", ""),
        bert_rvc_index_path=raw.get("bert_rvc_index_path", ""),
        bert_rvc_pitch_shift=raw.get("bert_rvc_pitch_shift", 0),
        player_name=raw.get("player_name", "Player"),
    )
    return settings.clamp()


def save_settings(settings: GameSettings, path: Path | None = None) -> None:
    file_path = path or SETTINGS_PATH
    file_path.write_text(json.dumps(asdict(settings.clamp()), indent=2), encoding="utf-8")
