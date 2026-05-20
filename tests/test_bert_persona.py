from __future__ import annotations

import bert_persona


def test_choose_line_only_for_bert_modes():
    assert bert_persona.choose_line("game_start", "downeast", dad_ai_level=2) == ""


def test_choose_line_downeast_and_robot_banks_have_content():
    downeast = bert_persona.choose_line("game_start", "downeast", dad_ai_level=4)
    robot = bert_persona.choose_line("game_start", "robot", dad_ai_level=4)

    assert isinstance(downeast, str)
    assert isinstance(robot, str)
    assert downeast
    assert robot


def test_choose_line_bert_plus_robot_gets_profile_suffix():
    line = bert_persona.choose_line("game_start", "robot", dad_ai_level=5)

    assert "ADAPTIVE PROFILE ACTIVE" in line


def test_choose_line_bert_plus_downeast_gets_strategy_suffix_for_key_events():
    line = bert_persona.choose_line("bert_won", "downeast", dad_ai_level=5)

    assert "Bert Plus saw that line two plays ago." in line
