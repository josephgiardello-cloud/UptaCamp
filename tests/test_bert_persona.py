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


def test_choose_line_hand_scored_returns_content():
    downeast = bert_persona.choose_line("hand_scored", "downeast", dad_ai_level=4)
    robot = bert_persona.choose_line("hand_scored", "robot", dad_ai_level=4)

    assert downeast
    assert robot


def test_choose_line_crib_scored_returns_content():
    downeast = bert_persona.choose_line("crib_scored", "downeast", dad_ai_level=4)
    robot = bert_persona.choose_line("crib_scored", "robot", dad_ai_level=4)

    assert downeast
    assert robot


def test_choose_line_hand_and_crib_scored_require_bert_level():
    assert bert_persona.choose_line("hand_scored", "downeast", dad_ai_level=3) == ""
    assert bert_persona.choose_line("crib_scored", "robot", dad_ai_level=2) == ""
