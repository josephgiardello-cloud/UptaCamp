from __future__ import annotations

import subprocess
import wave

from voice_manager import VoiceManager


def test_shape_for_voice_style_keeps_robot_text_unchanged():
    vm = VoiceManager(enabled=False)

    text = "Cards are going to your crib."
    assert vm._shape_for_voice_style(text, "robot") == text


def test_shape_for_voice_style_preserves_words_for_natural_tts():
    vm = VoiceManager(enabled=False)

    text = "Cards are going to your crib for points."
    shaped = vm._shape_for_voice_style(text, "downeast")

    assert "cards" in shaped.lower()
    assert "going" in shaped.lower()
    assert "your" in shaped.lower()
    assert "for" in shaped.lower()


def test_configure_backend_updates_runtime_selection():
    vm = VoiceManager(enabled=False, backend="sapi")

    vm.configure_backend(
        "local_ai",
        "models/bert.onnx",
        "models/barnabas.onnx",
        "piper",
        True,
        "rvc_infer",
        "models/bert_rvc.pth",
        "models/bert_rvc.index",
        -2,
    )

    assert vm.backend == "local_ai"
    assert vm.local_ai_model_path == "models/bert.onnx"
    assert vm.barnabas_local_model_path == "models/barnabas.onnx"
    assert vm.local_ai_exe_path == "piper"
    assert vm.rvc_enabled is True


def test_build_cache_key_is_stable_for_same_inputs():
    vm = VoiceManager(enabled=False, backend="local_ai")

    key_a = vm._build_cache_key("Ayuh", 4, "models/bert.onnx")
    key_b = vm._build_cache_key("Ayuh", 4, "models/bert.onnx")

    assert key_a == key_b


def test_maybe_apply_rvc_returns_original_when_disabled(tmp_path):
    vm = VoiceManager(enabled=False, rvc_enabled=False)
    wav_path = tmp_path / "line.wav"
    wav_path.write_bytes(b"RIFF")

    out = vm._maybe_apply_rvc(wav_path)

    assert out == wav_path


def test_prereq_report_contains_rvc_block():
    vm = VoiceManager(enabled=False, rvc_enabled=True)

    report = vm.get_local_prerequisites_report()

    assert "rvc" in report
    assert report["rvc"]["enabled"] is True


def test_speak_bert_skips_when_already_speaking_without_bypass(monkeypatch):
    vm = VoiceManager(enabled=True)

    calls = []

    def _fake_speak_windows(text, dad_ai_level):
        calls.append((text, dad_ai_level))

    monkeypatch.setattr(vm, "_is_windows", True)
    monkeypatch.setattr(vm, "_speak_windows", _fake_speak_windows)
    monkeypatch.setattr(vm, "_is_speaking", lambda now=None: len(calls) > 0)

    vm.speak_bert("First line", dad_ai_level=4, bypass_cooldown=False, voice_style="downeast")
    vm.speak_bert("Second line", dad_ai_level=4, bypass_cooldown=False, voice_style="downeast")

    assert len(calls) == 1


def test_speak_bert_interrupts_when_already_speaking_with_bypass(monkeypatch):
    vm = VoiceManager(enabled=True)

    calls = []
    stop_called = {"count": 0}

    def _fake_speak_windows(text, dad_ai_level):
        calls.append((text, dad_ai_level))

    def _fake_stop():
        stop_called["count"] += 1

    monkeypatch.setattr(vm, "_is_windows", True)
    monkeypatch.setattr(vm, "_speak_windows", _fake_speak_windows)
    monkeypatch.setattr(vm, "_is_speaking", lambda now=None: True)
    monkeypatch.setattr(vm, "stop", _fake_stop)

    vm.speak_bert("Replacement line", dad_ai_level=4, bypass_cooldown=True, voice_style="downeast")

    assert stop_called["count"] == 1
    assert len(calls) == 1


def test_speak_bert_normalizes_legacy_level6_to_level5(monkeypatch):
    vm = VoiceManager(enabled=True)

    calls = []

    def _fake_speak_windows(text, dad_ai_level):
        calls.append((text, dad_ai_level))

    monkeypatch.setattr(vm, "_is_windows", True)
    monkeypatch.setattr(vm, "_speak_windows", _fake_speak_windows)
    monkeypatch.setattr(vm, "_is_speaking", lambda now=None: False)

    vm.speak_bert("Barnabas line", dad_ai_level=6, bypass_cooldown=True, voice_style="downeast")

    assert len(calls) == 1
    assert calls[0][1] == 5


def test_speak_bert_levels_1_to_3_force_sapi_even_when_local_ai_enabled(monkeypatch):
    vm = VoiceManager(enabled=True, backend="local_ai")

    sapi_calls = []
    local_calls = []

    def _fake_speak_windows(text, dad_ai_level):
        sapi_calls.append((text, dad_ai_level))

    def _fake_speak_local_ai_async(text, dad_ai_level):
        local_calls.append((text, dad_ai_level))

    monkeypatch.setattr(vm, "_is_windows", True)
    monkeypatch.setattr(vm, "_speak_windows", _fake_speak_windows)
    monkeypatch.setattr(vm, "_speak_local_ai_async", _fake_speak_local_ai_async)
    monkeypatch.setattr(vm, "_is_speaking", lambda now=None: False)

    vm.speak_bert("Easy mode line", dad_ai_level=2, bypass_cooldown=True, voice_style="downeast")

    assert len(sapi_calls) == 1
    assert sapi_calls[0][1] == 2
    assert local_calls == []


def test_resolve_local_ai_model_path_prefers_barnabas_for_level5_and_legacy_level6(tmp_path):
    base_model = tmp_path / "joe.onnx"
    barnabas_model = tmp_path / "barnabas.onnx"
    base_model.write_text("base", encoding="utf-8")
    barnabas_model.write_text("barnabas", encoding="utf-8")

    vm = VoiceManager(
        enabled=True,
        backend="local_ai",
        local_ai_model_path=str(base_model),
        barnabas_local_model_path=str(barnabas_model),
    )

    level4_path = vm._resolve_local_ai_model_path(4)
    level5_path = vm._resolve_local_ai_model_path(5)
    level6_path = vm._resolve_local_ai_model_path(6)

    assert level4_path == base_model
    assert level5_path == barnabas_model
    assert level6_path == barnabas_model


def test_is_speaking_true_when_sapi_process_running(monkeypatch):
    vm = VoiceManager(enabled=True)

    class _Proc:
        def poll(self):
            return None

    vm._sapi_proc = _Proc()

    assert vm._is_speaking() is True


def test_dynamic_sapi_rate_slows_for_longer_lines():
    vm = VoiceManager(enabled=True)

    short_line = "Ayuh."
    medium_line = "Ayuh bub, cards on the wood."
    long_line = "Ayuh bub, cards on the wood and we keep this one tidy from first peg to last."

    short_rate = vm._dynamic_sapi_rate(short_line, dad_ai_level=5)
    medium_rate = vm._dynamic_sapi_rate(medium_line, dad_ai_level=5)
    long_rate = vm._dynamic_sapi_rate(long_line, dad_ai_level=5)

    assert short_rate >= medium_rate
    assert medium_rate >= long_rate


def test_dynamic_sapi_rate_barnabas_is_slower_than_level6_for_same_line():
    vm = VoiceManager(enabled=True)

    line = "Cards on the wood and count every inch."
    barnabas_rate = vm._dynamic_sapi_rate(line, dad_ai_level=5)
    level4_rate = vm._dynamic_sapi_rate(line, dad_ai_level=4)

    assert barnabas_rate <= level4_rate


def test_shape_for_ai_level_voice_barnabas_keeps_sentence_timing_natural():
    vm = VoiceManager(enabled=True)

    shaped = vm._shape_for_ai_level_voice("One line. Another line.", dad_ai_level=5)

    assert "..." not in shaped
    assert shaped.endswith(".")


def test_shape_for_ai_level_voice_other_levels_unchanged():
    vm = VoiceManager(enabled=True)

    text = "One line. Another line."
    assert vm._shape_for_ai_level_voice(text, dad_ai_level=4) == text
    assert vm._shape_for_ai_level_voice(text, dad_ai_level=6).endswith(".")


def test_pronunciation_hint_rewrites_barnabas_name():
    vm = VoiceManager(enabled=True)

    shaped = vm._apply_pronunciation_hints("Barnabas counts the hand.")

    assert "Barnahbus" in shaped


def test_speak_windows_uses_ssml_for_barnabas(monkeypatch):
    vm = VoiceManager(enabled=True)
    captured: dict[str, list[str]] = {}

    class _FakeProc:
        def poll(self):
            return None

    def _fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeProc()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0, raising=False)

    vm._speak_windows("Barnabas speaks low, cards stay quiet.", dad_ai_level=5)

    script = " ".join(captured.get("cmd", []))
    assert "SpeakSsml" in script
    assert "pitch=\"-7%\"" in script
    assert "rate=\"-10%\"" in script
    assert "break time=" in script and "170ms" in script
    assert "<sub alias=\"Barnahbus\">Barnabas</sub>" in script
    assert "Gender -eq [System.Speech.Synthesis.VoiceGender]::Male" in script
    assert "catch { $synth.Speak($text) }" in script


def test_speak_windows_uses_plain_speak_for_non_barnabas(monkeypatch):
    vm = VoiceManager(enabled=True)
    captured: dict[str, list[str]] = {}

    class _FakeProc:
        def poll(self):
            return None

    def _fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeProc()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0, raising=False)

    vm._speak_windows("Cards on the wood", dad_ai_level=4)

    script = " ".join(captured.get("cmd", []))
    assert "SpeakSsml" not in script
    assert "Speak($text)" in script


def test_speak_windows_uses_human_ssml_for_levels_1_to_3(monkeypatch):
    vm = VoiceManager(enabled=True)
    captured: dict[str, list[str]] = {}

    class _FakeProc:
        def poll(self):
            return None

    def _fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeProc()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0, raising=False)

    vm._speak_windows("Cards on the table, choose two.", dad_ai_level=2)

    script = " ".join(captured.get("cmd", []))
    assert "SpeakSsml" in script
    assert "pitch=\"+4%\"" in script
    assert "rate=\"-2%\"" in script
    assert "break time=" in script and "110ms" in script
    assert "Gender -eq [System.Speech.Synthesis.VoiceGender]::Female" in script


def test_apply_barnabas_vocal_fx_lowers_sample_rate(tmp_path):
    vm = VoiceManager(enabled=False)

    wav_path = tmp_path / "line.wav"
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * 2205)

    out_path = vm._apply_barnabas_vocal_fx(wav_path)
    assert out_path.exists()

    with wave.open(str(out_path), "rb") as out_w:
        assert out_w.getframerate() < 22050
