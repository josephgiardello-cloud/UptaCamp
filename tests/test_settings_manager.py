from __future__ import annotations

from settings_manager import GameSettings, load_settings, save_settings


def test_settings_round_trip_includes_bert_voice_flag(tmp_path):
    path = tmp_path / "settings.json"
    settings = GameSettings(
        volume=0.5,
        animations_enabled=True,
        online_ai_level=2,
        ui_style="classic",
        bert_voice_enabled=False,
        bert_voice_style="robot",
        bert_voice_backend="local_ai",
        bert_local_model_path="models/bert.onnx",
        bert_local_exe_path="piper",
        bert_rvc_enabled=True,
        bert_rvc_exe_path="rvc_infer",
        bert_rvc_model_path="models/bert_rvc.pth",
        bert_rvc_index_path="models/bert_rvc.index",
        bert_rvc_pitch_shift=-2,
    )

    save_settings(settings, path=path)
    loaded = load_settings(path=path)

    assert loaded.bert_voice_enabled is False
    assert loaded.bert_voice_style == "robot"
    assert loaded.bert_voice_backend == "local_ai"
    assert loaded.bert_local_model_path == "models/bert.onnx"
    assert loaded.bert_local_exe_path == "piper"
    assert loaded.bert_rvc_enabled is True
    assert loaded.bert_rvc_exe_path == "rvc_infer"
    assert loaded.bert_rvc_model_path == "models/bert_rvc.pth"
    assert loaded.bert_rvc_index_path == "models/bert_rvc.index"
    assert loaded.bert_rvc_pitch_shift == -2


def test_settings_clamp_coerces_bert_voice_to_bool():
    settings = GameSettings(bert_voice_enabled=1)

    clamped = settings.clamp()

    assert clamped.bert_voice_enabled is True


def test_settings_clamp_normalizes_bert_voice_style():
    settings = GameSettings(bert_voice_style="invalid-style")

    clamped = settings.clamp()

    assert clamped.bert_voice_style == "downeast"


def test_settings_clamp_normalizes_bert_voice_backend():
    settings = GameSettings(bert_voice_backend="unsupported")

    clamped = settings.clamp()

    assert clamped.bert_voice_backend == "sapi"


def test_settings_clamp_clips_rvc_pitch_shift():
    settings = GameSettings(bert_rvc_pitch_shift=100)

    clamped = settings.clamp()

    assert clamped.bert_rvc_pitch_shift == 24
