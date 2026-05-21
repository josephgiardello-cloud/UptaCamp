from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import threading
import time
import winsound
from pathlib import Path
from typing import Any


class VoiceManager:
    def __init__(
        self,
        enabled: bool = True,
        min_interval_s: float = 1.1,
        backend: str = "sapi",
        local_ai_model_path: str = "",
        local_ai_exe_path: str = "piper",
        rvc_enabled: bool = False,
        rvc_exe_path: str = "rvc_infer",
        rvc_model_path: str = "",
        rvc_index_path: str = "",
        rvc_pitch_shift: int = -2,
    ):
        self.enabled = bool(enabled)
        self.min_interval_s = max(0.0, float(min_interval_s))
        self._last_spoken_at = 0.0
        self._last_text = ""
        self._is_windows = os.name == "nt"
        self.backend = backend if backend in ("sapi", "local_ai") else "sapi"
        self.local_ai_model_path = str(local_ai_model_path or "")
        self.local_ai_exe_path = str(local_ai_exe_path or "piper")
        self.rvc_enabled = bool(rvc_enabled)
        self.rvc_exe_path = str(rvc_exe_path or "rvc_infer")
        self.rvc_model_path = str(rvc_model_path or "")
        self.rvc_index_path = str(rvc_index_path or "")
        self.rvc_pitch_shift = int(rvc_pitch_shift)
        self._cache_dir = Path(__file__).resolve().parent / ".bert_voice_cache"
        self._cache_dir.mkdir(exist_ok=True)
        self._sapi_proc: subprocess.Popen[Any] | None = None
        self._speaking_until = 0.0
        self._speech_guard = threading.Lock()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    def configure_backend(
        self,
        backend: str,
        local_ai_model_path: str,
        local_ai_exe_path: str,
        rvc_enabled: bool,
        rvc_exe_path: str,
        rvc_model_path: str,
        rvc_index_path: str,
        rvc_pitch_shift: int,
    ) -> None:
        self.backend = backend if backend in ("sapi", "local_ai") else "sapi"
        self.local_ai_model_path = str(local_ai_model_path or "")
        self.local_ai_exe_path = str(local_ai_exe_path or "piper")
        self.rvc_enabled = bool(rvc_enabled)
        self.rvc_exe_path = str(rvc_exe_path or "rvc_infer")
        self.rvc_model_path = str(rvc_model_path or "")
        self.rvc_index_path = str(rvc_index_path or "")
        self.rvc_pitch_shift = int(rvc_pitch_shift)

    def speak_bert(
        self,
        text: str,
        dad_ai_level: int,
        bypass_cooldown: bool = False,
        voice_style: str = "downeast",
    ) -> None:
        if not self.enabled or dad_ai_level not in (4, 5):
            return

        normalized = str(text).strip()
        if not normalized:
            return

        spoken_text = self._shape_for_voice_style(normalized, voice_style)

        now = time.monotonic()
        if self._is_speaking(now) or (
            not bypass_cooldown
            and ((now - self._last_spoken_at) < self.min_interval_s or normalized == self._last_text)
        ):
                return

        self._last_spoken_at = now
        self._last_text = normalized
        self._set_speaking_window(spoken_text)

        if self.backend == "local_ai":
            self._speak_local_ai_async(spoken_text)
            return

        if self._is_windows:
            self._speak_windows(spoken_text, dad_ai_level)

    def _shape_for_voice_style(self, text: str, voice_style: str) -> str:
        if voice_style != "downeast":
            return text

        # Keep lexical content intact for clearer TTS pronunciation.
        # Persona authenticity should come from Bert's generated lines,
        # not phonetic respelling that speech engines can garble.
        shaped = re.sub(r"\s+", " ", text).strip()
        shaped = re.sub(r"\bgoing\b", "goin'", shaped, flags=re.IGNORECASE)
        return shaped

    def _speak_local_ai_async(self, text: str) -> None:
        worker = threading.Thread(
            target=self._speak_local_ai,
            args=(text,),
            daemon=True,
        )
        worker.start()

    def _speak_local_ai(self, text: str) -> None:
        model_path = Path(self.local_ai_model_path) if self.local_ai_model_path else None
        if model_path is None or not model_path.exists():
            if self._is_windows:
                self._speak_windows(text, 5)
            return

        exe = self.local_ai_exe_path or "piper"
        if shutil.which(exe) is None and not Path(exe).exists():
            if self._is_windows:
                self._speak_windows(text, 5)
            return

        cache_key = self._build_cache_key(text)
        wav_path = self._cache_dir / f"{cache_key}.wav"
        if not wav_path.exists():
            cmd = [exe, "--model", str(model_path), "--output_file", str(wav_path)]
            try:
                subprocess.run(
                    cmd,
                    input=text,
                    text=True,
                    capture_output=True,
                    check=True,
                    timeout=20,
                )
            except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
                if self._is_windows:
                    self._speak_windows(text, 5)
                return

        playback_path = self._maybe_apply_rvc(wav_path)

        if self._is_windows:
            try:
                winsound.PlaySound(str(playback_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            except RuntimeError:
                self._speak_windows(text, 5)

    def _estimate_speech_seconds(self, text: str) -> float:
        words = max(1, len(text.split()))
        # Conversational speech pacing with a small startup buffer.
        return min(8.0, 0.35 + words * 0.24)

    def _set_speaking_window(self, text: str) -> None:
        with self._speech_guard:
            self._speaking_until = max(self._speaking_until, time.monotonic() + self._estimate_speech_seconds(text))

    def _is_speaking(self, now: float | None = None) -> bool:
        check_at = now if now is not None else time.monotonic()
        with self._speech_guard:
            proc = self._sapi_proc
            if proc is not None and proc.poll() is None:
                return True
            return check_at < self._speaking_until

    def _maybe_apply_rvc(self, wav_path: Path) -> Path:
        if not self.rvc_enabled:
            return wav_path

        model_ok = bool(self.rvc_model_path) and Path(self.rvc_model_path).exists()
        exe = self.rvc_exe_path or "rvc_infer"
        exe_ok = shutil.which(exe) is not None or Path(exe).exists()
        if not model_ok or not exe_ok:
            return wav_path

        out_path = wav_path.with_name(f"{wav_path.stem}_rvc.wav")
        if out_path.exists():
            return out_path

        cmd = [
            exe,
            "--input",
            str(wav_path),
            "--output",
            str(out_path),
            "--model",
            str(self.rvc_model_path),
            "--pitch",
            str(self.rvc_pitch_shift),
        ]
        if self.rvc_index_path and Path(self.rvc_index_path).exists():
            cmd.extend(["--index", str(self.rvc_index_path)])

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=20)
            return out_path if out_path.exists() else wav_path
        except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
            return wav_path

    def _build_cache_key(
        self, text: str, dad_ai_level: int | None = None, model_path: str | None = None
    ) -> str:
        # Keep backward-compatible parameters for existing tests/callers.
        _ = dad_ai_level
        _ = model_path
        raw = f"{text}|{self.backend}|{self.local_ai_model_path}|{self.rvc_pitch_shift}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def _dynamic_sapi_rate(self, text: str, dad_ai_level: int) -> int:
        """Choose a speech rate tuned for line length.

        Short lines should feel snappy, while long lines need slower pacing
        so they remain clear and natural.
        """
        word_count = max(1, len(str(text).split()))
        base_rate = -2 if dad_ai_level == 4 else -1

        if word_count <= 6:
            return min(2, base_rate + 1)
        if word_count <= 12:
            return base_rate
        if word_count <= 18:
            return max(-6, base_rate - 1)
        return max(-6, base_rate - 2)

    def _speak_windows(self, text: str, dad_ai_level: int) -> None:
        if dad_ai_level == 4:
            preferred_voices = ["Microsoft David Desktop", "Microsoft Guy"]
        else:
            preferred_voices = ["Microsoft Guy", "Microsoft David Desktop", "Microsoft Mark"]
        rate = self._dynamic_sapi_rate(text, dad_ai_level)

        escaped_text = text.replace("'", "''").replace("\r", " ").replace("\n", " ")
        voices_ps = ", ".join("'" + voice.replace("'", "''") + "'" for voice in preferred_voices)

        script = (
            "Add-Type -AssemblyName System.Speech;"
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            f"$preferred = @({voices_ps});"
            "$selected = $false;"
            "foreach ($v in $preferred) {"
            "  try { $synth.SelectVoice($v); $selected = $true; break } catch {}"
            "};"
            "if (-not $selected) {"
            "  $male = $synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo } | "
            "Where-Object { $_.Gender -eq [System.Speech.Synthesis.VoiceGender]::Male } | "
            "Select-Object -First 1;"
            "  if ($male) {"
            "    try { $synth.SelectVoice($male.Name); $selected = $true } catch {}"
            "  }"
            "};"
            f"$synth.Rate = {rate};"
            "$synth.Volume = 100;"
            f"$text = '{escaped_text}';"
            "$synth.Speak($text);"
            "$synth.Dispose();"
        )

        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            with self._speech_guard:
                self._sapi_proc = proc
        except OSError:
            pass

    def get_local_prerequisites_report(self) -> dict[str, Any]:
        report: dict[str, Any] = {
            "platform": "windows" if self._is_windows else os.name,
            "offline_ready": False,
            "powershell_available": False,
            "system_speech_available": False,
            "backend": self.backend,
            "local_ai": {
                "executable": self.local_ai_exe_path,
                "executable_found": False,
                "model_path": self.local_ai_model_path,
                "model_found": False,
                "ready": False,
            },
            "rvc": {
                "enabled": self.rvc_enabled,
                "executable": self.rvc_exe_path,
                "executable_found": False,
                "model_path": self.rvc_model_path,
                "model_found": False,
                "index_path": self.rvc_index_path,
                "index_found": False,
                "ready": False,
                "pitch_shift": self.rvc_pitch_shift,
            },
            "voices": [],
            "recommended": {
                "bert_level4": ["Microsoft David Desktop", "Microsoft Guy"],
                "bert_plus_level5": ["Microsoft Guy", "Microsoft David Desktop", "Microsoft Mark"],
            },
            "notes": [],
        }

        exe = self.local_ai_exe_path or "piper"
        exe_found = shutil.which(exe) is not None or Path(exe).exists()
        report["local_ai"]["executable_found"] = exe_found
        model_found = bool(self.local_ai_model_path) and Path(self.local_ai_model_path).exists()
        report["local_ai"]["model_found"] = model_found
        report["local_ai"]["ready"] = bool(exe_found and model_found)

        rvc_exe = self.rvc_exe_path or "rvc_infer"
        rvc_exe_found = shutil.which(rvc_exe) is not None or Path(rvc_exe).exists()
        rvc_model_found = bool(self.rvc_model_path) and Path(self.rvc_model_path).exists()
        rvc_index_found = bool(self.rvc_index_path) and Path(self.rvc_index_path).exists()
        report["rvc"]["executable_found"] = rvc_exe_found
        report["rvc"]["model_found"] = rvc_model_found
        report["rvc"]["index_found"] = rvc_index_found
        report["rvc"]["ready"] = bool(rvc_exe_found and rvc_model_found)

        if not self._is_windows:
            report["offline_ready"] = bool(report["local_ai"]["ready"])
            report["notes"].append("Windows SAPI is unavailable; use local_ai backend.")
            return report

        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "Add-Type -AssemblyName System.Speech;"
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                "$voices = $s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name };"
                "$s.Dispose();"
                "$voices -join \"`n\""
            ),
        ]
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
            report["powershell_available"] = True
            report["system_speech_available"] = True
            voices = [v.strip() for v in completed.stdout.splitlines() if v.strip()]
            report["voices"] = voices
            report["offline_ready"] = len(voices) > 0 or bool(report["local_ai"]["ready"])
            if not voices:
                report["notes"].append("No installed SAPI voices were found.")
        except (subprocess.CalledProcessError, OSError):
            report["notes"].append("Could not query local SAPI voices via PowerShell.")
            report["offline_ready"] = bool(report["local_ai"]["ready"])

        if not report["local_ai"]["executable_found"]:
            report["notes"].append("Local AI backend not found: install Piper and set bert_local_exe_path.")
        if not report["local_ai"]["model_found"]:
            report["notes"].append("Local AI model not found: set bert_local_model_path to a Piper model.")
        if report["rvc"]["enabled"] and not report["rvc"]["ready"]:
            report["notes"].append(
                "RVC enabled but not ready: set bert_rvc_exe_path and bert_rvc_model_path."
            )

        return report
