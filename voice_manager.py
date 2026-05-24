from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import threading
import time
import wave
from pathlib import Path
from typing import Any

from runtime_paths import resolve_runtime_path

try:
    import piper as piper_package
    from piper import PiperVoice
except ImportError:  # pragma: no cover - optional dependency in dev envs
    PiperVoice = None
    piper_package = None

try:
    import winsound
except ImportError:  # pragma: no cover - non-Windows platforms
    winsound = None


class VoiceManager:
    def __init__(
        self,
        enabled: bool = True,
        min_interval_s: float = 1.1,
        backend: str = "sapi",
        local_ai_model_path: str = "",
        barnabas_local_model_path: str = "",
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
        self.barnabas_local_model_path = str(barnabas_local_model_path or "")
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
        self._piper_lock = threading.Lock()
        self._piper_voices: dict[tuple[str, str], Any] = {}

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    def stop(self) -> None:
        """Stop any in-flight speech playback immediately."""
        with self._speech_guard:
            proc = self._sapi_proc
            self._sapi_proc = None
            self._speaking_until = 0.0

        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.terminate()
            except OSError:
                pass

        if self._is_windows and winsound is not None:
            try:
                winsound.PlaySound(None, 0)
            except RuntimeError:
                pass

    def configure_backend(
        self,
        backend: str,
        local_ai_model_path: str,
        barnabas_local_model_path: str,
        local_ai_exe_path: str,
        rvc_enabled: bool,
        rvc_exe_path: str,
        rvc_model_path: str,
        rvc_index_path: str,
        rvc_pitch_shift: int,
    ) -> None:
        self.backend = backend if backend in ("sapi", "local_ai") else "sapi"
        self.local_ai_model_path = str(local_ai_model_path or "")
        self.barnabas_local_model_path = str(barnabas_local_model_path or "")
        self.local_ai_exe_path = str(local_ai_exe_path or "piper")
        self.rvc_enabled = bool(rvc_enabled)
        self.rvc_exe_path = str(rvc_exe_path or "rvc_infer")
        self.rvc_model_path = str(rvc_model_path or "")
        self.rvc_index_path = str(rvc_index_path or "")
        self.rvc_pitch_shift = int(rvc_pitch_shift)

    @staticmethod
    def _normalized_ai_level(dad_ai_level: int) -> int:
        level = int(dad_ai_level)
        if level < 1:
            return 1
        if level >= 5:
            return 5
        return level

    def speak_bert(
        self,
        text: str,
        dad_ai_level: int,
        bypass_cooldown: bool = False,
        voice_style: str = "downeast",
    ) -> None:
        dad_ai_level = self._normalized_ai_level(dad_ai_level)

        if not self.enabled or dad_ai_level not in (1, 2, 3, 4, 5):
            return

        normalized = str(text).strip()
        if not normalized:
            return

        spoken_text = self._shape_for_voice_style(normalized, voice_style)
        spoken_text = self._shape_for_ai_level_voice(spoken_text, dad_ai_level)
        spoken_text = self._apply_pronunciation_hints(spoken_text)

        now = time.monotonic()
        if self._is_speaking(now):
            # UI-triggered lines should be able to replace currently speaking lines.
            if bypass_cooldown:
                self.stop()
            else:
                return

        if not bypass_cooldown and (
            (now - self._last_spoken_at) < self.min_interval_s or normalized == self._last_text
        ):
            return

        self._last_spoken_at = now
        self._last_text = normalized
        self._set_speaking_window(spoken_text)

        force_sapi_lane = dad_ai_level in (1, 2, 3)

        if self.backend == "local_ai" and not force_sapi_lane:
            self._speak_local_ai_async(spoken_text, dad_ai_level)
            return

        if self._is_windows:
            self._speak_windows(spoken_text, dad_ai_level)

    def _shape_for_voice_style(self, text: str, voice_style: str) -> str:
        # Preserve vocabulary and only normalize spacing. Phonetic rewrites can
        # cause awkward pronunciations in SAPI/Piper voices.
        _ = voice_style
        return re.sub(r"\s+", " ", text).strip()

    def _shape_for_ai_level_voice(self, text: str, dad_ai_level: int) -> str:
        if dad_ai_level != 5:
            return text

        # Barnabas cadence: keep phrasing intact and avoid synthetic ellipsis.
        shaped = re.sub(r"\s+", " ", text).strip()
        if not shaped.endswith((".", "!", "?")):
            shaped += "."
        return shaped

    def _apply_pronunciation_hints(self, text: str) -> str:
        # Stabilize name pronunciation across TTS engines.
        return re.sub(r"\bBarnabas\b", "Barnahbus", text, flags=re.IGNORECASE)

    def _apply_ssml_pronunciation_hints(self, escaped_text: str) -> str:
        # SSML alias keeps displayed text while guiding spoken pronunciation.
        return re.sub(
            r"\b(?:Barnabas|Barnahbus)\b",
            '<sub alias="Barnahbus">Barnabas</sub>',
            escaped_text,
            flags=re.IGNORECASE,
        )

    def _escape_ssml_text(self, text: str) -> str:
        escaped = text.replace("&", "&amp;")
        escaped = escaped.replace("<", "&lt;").replace(">", "&gt;")
        escaped = escaped.replace('"', "&quot;").replace("'", "&apos;")
        return escaped

    def _inject_expressive_ssml_pauses(self, escaped_text: str) -> str:
        # Add subtle phrase and sentence breaks for expressive pacing.
        with_phrase_breaks = re.sub(
            r"([,;:])\s+",
            r"\1 <break time=\"120ms\"/> ",
            escaped_text,
        )
        return re.sub(
            r"([.!?])\s+",
            r"\1 <break time=\"230ms\"/> ",
            with_phrase_breaks,
        )

    def _inject_barnabas_ssml_cadence(self, escaped_text: str) -> str:
        # Barnabas should sound deliberate and aristocratic without over-graveling.
        with_phrase_breaks = re.sub(
            r"([,;:])\s+",
            r"\1 <break time=\"170ms\"/> ",
            escaped_text,
        )
        return re.sub(
            r"([.!?])\s+",
            r"\1 <break time=\"320ms\"/> ",
            with_phrase_breaks,
        )

    def _inject_human_ssml_cadence(self, escaped_text: str) -> str:
        # Smooth conversational pacing for levels 1-3.
        with_phrase_breaks = re.sub(
            r"([,;:])\s+",
            r"\1 <break time=\"110ms\"/> ",
            escaped_text,
        )
        return re.sub(
            r"([.!?])\s+",
            r"\1 <break time=\"210ms\"/> ",
            with_phrase_breaks,
        )

    def _speak_local_ai_async(self, text: str, dad_ai_level: int) -> None:
        worker = threading.Thread(
            target=self._speak_local_ai,
            args=(text, dad_ai_level),
            daemon=True,
        )
        worker.start()

    def _speak_local_ai(self, text: str, dad_ai_level: int) -> None:
        model_path = self._resolve_local_ai_model_path(dad_ai_level)
        if model_path is None or not model_path.exists():
            if self._is_windows:
                self._speak_windows(text, 5)
            return

        cache_key = self._build_cache_key(
            text, dad_ai_level=dad_ai_level, model_path=str(model_path)
        )
        wav_path = self._cache_dir / f"{cache_key}.wav"
        if not wav_path.exists():
            if not self._synthesize_local_ai_wav(text, model_path, wav_path):
                if self._is_windows:
                    self._speak_windows(text, 5)
                return

        playback_path = wav_path
        if dad_ai_level == 5:
            playback_path = self._apply_barnabas_vocal_fx(playback_path)

        playback_path = self._maybe_apply_rvc(playback_path)

        if self._is_windows and winsound is not None:
            try:
                winsound.PlaySound(str(playback_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            except RuntimeError:
                self._speak_windows(text, 5)

    def _synthesize_local_ai_wav(self, text: str, model_path: Path, wav_path: Path) -> bool:
        if self._synthesize_with_piper_python(text, model_path, wav_path):
            return True
        return self._synthesize_with_piper_exe(text, model_path, wav_path)

    def _resolve_piper_espeak_data_dir(self) -> Path | None:
        if piper_package is None:
            return None

        package_dir = Path(piper_package.__file__).resolve().parent
        espeak_dir = package_dir / "espeak-ng-data"
        if espeak_dir.exists():
            return espeak_dir
        return None

    def _load_piper_voice(self, model_path: Path) -> Any | None:
        if PiperVoice is None:
            return None

        config_path = model_path.with_suffix(f"{model_path.suffix}.json")
        espeak_dir = self._resolve_piper_espeak_data_dir()
        cache_key = (str(model_path), str(espeak_dir or ""))

        with self._piper_lock:
            cached = self._piper_voices.get(cache_key)
            if cached is not None:
                return cached

            try:
                voice = PiperVoice.load(
                    str(model_path),
                    config_path=str(config_path) if config_path.exists() else None,
                    espeak_data_dir=str(espeak_dir) if espeak_dir is not None else None,
                )
            except Exception:
                return None

            self._piper_voices[cache_key] = voice
            return voice

    def _synthesize_with_piper_python(self, text: str, model_path: Path, wav_path: Path) -> bool:
        voice = self._load_piper_voice(model_path)
        if voice is None:
            return False

        try:
            with wav_path.open("wb") as wav_file:
                voice.synthesize_wav(text, wav_file)
            return wav_path.exists() and wav_path.stat().st_size > 0
        except Exception:
            try:
                wav_path.unlink(missing_ok=True)
            except OSError:
                pass
            return False

    def _synthesize_with_piper_exe(self, text: str, model_path: Path, wav_path: Path) -> bool:
        exe = self._resolve_runtime_executable(self.local_ai_exe_path or "piper")
        if exe is None:
            return False

        cmd = [str(exe), "--model", str(model_path), "--output_file", str(wav_path)]
        try:
            subprocess.run(
                cmd,
                input=text,
                text=True,
                capture_output=True,
                check=True,
                timeout=20,
            )
            return wav_path.exists() and wav_path.stat().st_size > 0
        except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
            return False

    def _apply_barnabas_vocal_fx(self, wav_path: Path) -> Path:
        out_path = wav_path.with_name(f"{wav_path.stem}_barnabas.wav")
        if out_path.exists():
            return out_path

        try:
            with wave.open(str(wav_path), "rb") as src:
                params = src.getparams()
                frames = src.readframes(params.nframes)

            if params.framerate <= 0:
                return wav_path

            # Keep Barnabas distinct while avoiding an overly demonic tone.
            target_rate = max(8000, int(params.framerate * 0.93))

            with wave.open(str(out_path), "wb") as dst:
                dst.setnchannels(params.nchannels)
                dst.setsampwidth(params.sampwidth)
                dst.setframerate(target_rate)
                dst.writeframes(frames)

            return out_path
        except (OSError, wave.Error):
            return wav_path

    def _estimate_speech_seconds(self, text: str) -> float:
        words = max(1, len(text.split()))
        # Conversational speech pacing with a small startup buffer.
        return min(8.0, 0.35 + words * 0.24)

    def _set_speaking_window(self, text: str) -> None:
        with self._speech_guard:
            self._speaking_until = max(
                self._speaking_until, time.monotonic() + self._estimate_speech_seconds(text)
            )

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

        model_path = resolve_runtime_path(self.rvc_model_path) if self.rvc_model_path else None
        model_ok = model_path is not None and model_path.exists()
        exe = self._resolve_runtime_executable(self.rvc_exe_path or "rvc_infer")
        exe_ok = exe is not None
        if not model_ok or not exe_ok:
            return wav_path

        out_path = wav_path.with_name(f"{wav_path.stem}_rvc.wav")
        if out_path.exists():
            return out_path

        cmd = [
            str(exe),
            "--input",
            str(wav_path),
            "--output",
            str(out_path),
            "--model",
            str(model_path),
            "--pitch",
            str(self.rvc_pitch_shift),
        ]
        if self.rvc_index_path:
            index_path = resolve_runtime_path(self.rvc_index_path)
            if index_path.exists():
                cmd.extend(["--index", str(index_path)])

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=20)
            return out_path if out_path.exists() else wav_path
        except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
            return wav_path

    def _build_cache_key(
        self, text: str, dad_ai_level: int | None = None, model_path: str | None = None
    ) -> str:
        _ = dad_ai_level
        effective_model_path = str(model_path or self.local_ai_model_path)
        raw = f"{text}|{self.backend}|{effective_model_path}|{self.rvc_pitch_shift}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def _resolve_local_ai_model_path(self, dad_ai_level: int) -> Path | None:
        if self._normalized_ai_level(dad_ai_level) == 5 and self.barnabas_local_model_path:
            barnabas_path = resolve_runtime_path(self.barnabas_local_model_path)
            if barnabas_path.exists():
                return barnabas_path
        if self.local_ai_model_path:
            return resolve_runtime_path(self.local_ai_model_path)
        return None

    def _resolve_runtime_executable(self, value: str) -> Path | None:
        resolved = resolve_runtime_path(value)
        if resolved.exists():
            return resolved
        if shutil.which(value) is not None:
            return Path(value)
        return None

    def _dynamic_sapi_rate(self, text: str, dad_ai_level: int) -> int:
        """Choose a speech rate tuned for line length.

        Short lines should feel snappy, while long lines need slower pacing
        so they remain clear and natural.
        """
        dad_ai_level = self._normalized_ai_level(dad_ai_level)
        word_count = max(1, len(str(text).split()))
        if dad_ai_level == 4:
            base_rate = -1
        elif dad_ai_level == 5:
            base_rate = -1
        else:
            base_rate = 0

        if word_count <= 6:
            return min(1, base_rate + 1)
        if word_count <= 12:
            return base_rate
        if word_count <= 18:
            return max(-3, base_rate - 1)
        return max(-4, base_rate - 2)

    def _speak_windows(self, text: str, dad_ai_level: int) -> None:
        dad_ai_level = self._normalized_ai_level(dad_ai_level)

        if dad_ai_level in (1, 2, 3):
            preferred_voices = [
                "Microsoft Zira Desktop",
                "Microsoft Hazel Desktop",
                "Microsoft Aria",
            ]
            volume = 100
        elif dad_ai_level == 4:
            preferred_voices = ["Microsoft David Desktop", "Microsoft Guy"]
            volume = 100
        elif dad_ai_level == 5:
            preferred_voices = ["Microsoft Mark", "Microsoft David Desktop", "Microsoft Guy"]
            volume = 92
        else:
            preferred_voices = ["Microsoft Guy", "Microsoft David Desktop", "Microsoft Mark"]
            volume = 100
        rate = self._dynamic_sapi_rate(text, dad_ai_level)

        escaped_text = text.replace("'", "''").replace("\r", " ").replace("\n", " ")
        escaped_ssml_text = self._escape_ssml_text(text).replace("\r", " ").replace("\n", " ")
        escaped_ssml_text = self._apply_ssml_pronunciation_hints(escaped_ssml_text)
        voices_ps = ", ".join("'" + voice.replace("'", "''") + "'" for voice in preferred_voices)

        if dad_ai_level == 5:
            paused_ssml_text = self._inject_barnabas_ssml_cadence(escaped_ssml_text)
            ssml = (
                '<speak version="1.0" xml:lang="en-US">'
                '<prosody rate="-10%" pitch="-7%" volume="-2dB">'
                f"{paused_ssml_text}"
                "</prosody>"
                "</speak>"
            )
            ssml_ps = ssml.replace("'", "''")
            speak_cmd = (
                f"$text = '{escaped_text}';"
                "$synth.Rate = 0;"
                f"$ssml = '{ssml_ps}';"
                "try { $synth.SpeakSsml($ssml) } catch { $synth.Speak($text) };"
            )
        elif dad_ai_level in (1, 2, 3):
            paused_ssml_text = self._inject_human_ssml_cadence(escaped_ssml_text)
            ssml = (
                '<speak version="1.0" xml:lang="en-US">'
                '<prosody rate="-2%" pitch="+4%" volume="+0dB">'
                f"{paused_ssml_text}"
                "</prosody>"
                "</speak>"
            )
            ssml_ps = ssml.replace("'", "''")
            speak_cmd = (
                f"$text = '{escaped_text}';"
                "$synth.Rate = 0;"
                f"$ssml = '{ssml_ps}';"
                "try { $synth.SpeakSsml($ssml) } catch { $synth.Speak($text) };"
            )
        else:
            speak_cmd = f"$synth.Rate = {rate};" f"$text = '{escaped_text}';" "$synth.Speak($text);"

        if dad_ai_level in (1, 2, 3):
            fallback_clause = (
                "  $fallback = $synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo } | "
                "Where-Object { $_.Gender -eq [System.Speech.Synthesis.VoiceGender]::Female } | "
                "Sort-Object Name | "
                "Select-Object -First 1;"
            )
        elif dad_ai_level == 5:
            fallback_clause = (
                "  $fallback = $synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo } | "
                "Where-Object { $_.Gender -eq [System.Speech.Synthesis.VoiceGender]::Male } | "
                "Sort-Object Name | "
                "Select-Object -First 1;"
            )
        else:
            fallback_clause = (
                "  $fallback = $synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo } | "
                "Where-Object { $_.Gender -eq [System.Speech.Synthesis.VoiceGender]::Male } | "
                "Select-Object -First 1;"
            )

        script = (
            "Add-Type -AssemblyName System.Speech;"
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            f"$preferred = @({voices_ps});"
            "$selected = $false;"
            "foreach ($v in $preferred) {"
            "  try { $synth.SelectVoice($v); $selected = $true; break } catch {}"
            "};"
            "if (-not $selected) {" + fallback_clause + "  if ($fallback) {"
            "    try { $synth.SelectVoice($fallback.Name); $selected = $true } catch {}"
            "  }"
            "};"
            f"$synth.Volume = {volume};"
            f"{speak_cmd}"
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
                "old_house_level5": ["Microsoft Zira Desktop", "Microsoft Mark"],
                "barnabas_level5": ["Microsoft Guy", "Microsoft David Desktop", "Microsoft Mark"],
            },
            "notes": [],
        }

        exe = self.local_ai_exe_path or "piper"
        python_runtime_found = (
            PiperVoice is not None and self._resolve_piper_espeak_data_dir() is not None
        )
        exe_found = shutil.which(exe) is not None or Path(exe).exists() or python_runtime_found
        report["local_ai"]["executable_found"] = exe_found
        model_path = (
            resolve_runtime_path(self.local_ai_model_path) if self.local_ai_model_path else None
        )
        model_found = model_path is not None and model_path.exists()
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
                '$voices -join "`n"'
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
            report["notes"].append(
                "Local AI backend not found: install the Piper package or set bert_local_exe_path."
            )
        if not report["local_ai"]["model_found"]:
            report["notes"].append(
                "Local AI model not found: set bert_local_model_path to a Piper model."
            )
        if report["rvc"]["enabled"] and not report["rvc"]["ready"]:
            report["notes"].append(
                "RVC enabled but not ready: set bert_rvc_exe_path and bert_rvc_model_path."
            )

        return report
