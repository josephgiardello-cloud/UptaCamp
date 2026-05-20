from __future__ import annotations

from voice_manager import VoiceManager


def test_shape_for_voice_style_keeps_robot_text_unchanged():
    vm = VoiceManager(enabled=False)

    text = "Cards are going to your crib."
    assert vm._shape_for_voice_style(text, "robot") == text


def test_shape_for_voice_style_applies_downeast_pronunciation():
    vm = VoiceManager(enabled=False)

    text = "Cards are going to your crib for points."
    shaped = vm._shape_for_voice_style(text, "downeast")

    assert "cahds" in shaped.lower()
    assert "goin" in shaped.lower()
    assert "yah" in shaped.lower()
    assert "fer" in shaped.lower()


def test_configure_backend_updates_runtime_selection():
    vm = VoiceManager(enabled=False, backend="sapi")

    vm.configure_backend(
        "local_ai",
        "models/bert.onnx",
        "piper",
        True,
        "rvc_infer",
        "models/bert_rvc.pth",
        "models/bert_rvc.index",
        -2,
    )

    assert vm.backend == "local_ai"
    assert vm.local_ai_model_path == "models/bert.onnx"
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
