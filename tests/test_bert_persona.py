from __future__ import annotations

import bert_persona


def setup_function() -> None:
    bert_persona._LEVEL5_LEARNED_CUES.clear()


def test_choose_line_only_for_bert_modes():
    assert bert_persona.choose_line("game_start", "downeast", dad_ai_level=2) == ""


def test_choose_line_downeast_and_robot_banks_have_content():
    downeast = bert_persona.choose_line("game_start", "downeast", dad_ai_level=4)
    robot = bert_persona.choose_line("game_start", "robot", dad_ai_level=4)

    assert isinstance(downeast, str)
    assert isinstance(robot, str)
    assert downeast
    assert robot


def test_choose_line_legacy_level6_routes_to_barnabas_robot_lane():
    line = bert_persona.choose_line("game_start", "robot", dad_ai_level=6)

    assert ("BARNABUS" in line) or ("OLD HOUSE" in line)


def test_choose_line_legacy_level6_routes_to_barnabas_downeast_lane():
    line = bert_persona.choose_line("bert_won", "downeast", dad_ai_level=6)

    assert isinstance(line, str)
    assert line


def test_choose_line_barnabas_level_has_distinct_signature():
    line = bert_persona.choose_line("game_start", "robot", dad_ai_level=5)

    assert ("BARNABUS" in line) or ("OLD HOUSE" in line)


def test_level5_barnabas_lines_never_emit_bert_branding():
    events = [
        "level_selected",
        "game_start",
        "cards_dealt",
        "round_start",
        "go_called",
        "go_point",
        "last_card",
        "pegging_score",
        "pegging_31",
        "player_won",
        "bert_won",
        "hand_scored",
        "crib_scored",
    ]
    context = {"player_score": 90, "bert_score": 70, "crib_points": 6, "bert_is_dealer": False}

    for event in events:
        for style in ("robot", "downeast"):
            line = bert_persona.choose_line(event, style, dad_ai_level=5, context=context)
            assert "bert" not in line.lower()


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


def test_choose_line_crib_scored_uses_context_points_and_dealer_flag():
    line = bert_persona.choose_line(
        "crib_scored",
        "downeast",
        dad_ai_level=4,
        context={"crib_points": 8, "bert_is_dealer": True},
    )

    assert "8" in line
    assert "Bert" in line


def test_choose_line_bert_won_uses_context_scores():
    line = bert_persona.choose_line(
        "bert_won",
        "downeast",
        dad_ai_level=4,
        context={"bert_score": 121, "player_score": 109},
    )

    assert "121" in line
    assert "109" in line


def test_choose_line_bert_won_without_scores_avoids_zero_score_output():
    line = bert_persona.choose_line("bert_won", "downeast", dad_ai_level=4)

    assert "0 to 0" not in line
    assert "0 over 0" not in line


def test_choose_line_pegging_score_reflects_pegging_swing_context():
    line = bert_persona.choose_line(
        "pegging_score",
        "downeast",
        dad_ai_level=4,
        context={"bert_pegging_points": 7, "player_pegging_points": 2, "pegging_total": 12},
    )

    assert line


def test_choose_line_hand_scored_can_call_out_skunk_pressure():
    line = bert_persona.choose_line(
        "hand_scored",
        "downeast",
        dad_ai_level=4,
        context={"player_score": 112, "bert_score": 88},
    )

    lowered = line.lower()
    assert ("finish-rail" in lowered) or ("rough weather" in lowered)


def test_choose_line_cards_dealt_contains_downeast_lingo_when_bert_deals():
    line = bert_persona.choose_line(
        "cards_dealt",
        "downeast",
        dad_ai_level=4,
        context={"bert_is_dealer": True},
    )

    lowered = line.lower()
    assert ("ayuh" in lowered) or ("bub" in lowered)


def test_choose_line_round_start_trailing_uses_frustrated_path():
    line = bert_persona.choose_line(
        "round_start",
        "downeast",
        dad_ai_level=4,
        context={"player_score": 80, "bert_score": 66},
    )

    lowered = line.lower()
    assert (
        ("done driftin" in lowered)
        or ("hold the rail" in lowered)
        or ("tide changes quick" in lowered)
        or ("pushin every edge" in lowered)
    )


def test_choose_line_trailing_path_avoids_open_score_admission():
    line = bert_persona.choose_line(
        "hand_scored",
        "downeast",
        dad_ai_level=4,
        context={"player_score": 84, "bert_score": 67},
    )

    lowered = line.lower()
    assert "still down" not in lowered
    assert "trailin by" not in lowered
    assert "down " not in lowered


def test_choose_line_leading_path_can_reference_score_openly():
    line = bert_persona.choose_line(
        "hand_scored",
        "downeast",
        dad_ai_level=4,
        context={"player_score": 78, "bert_score": 95},
    )

    lowered = line.lower()
    assert ("lead holds" in lowered) or ("up 17" in lowered) or ("stay patient" in lowered)


def test_choose_line_hand_scored_leading_uses_stoic_path():
    line = bert_persona.choose_line(
        "hand_scored",
        "downeast",
        dad_ai_level=4,
        context={"player_score": 78, "bert_score": 95},
    )

    lowered = line.lower()
    assert ("lead holds" in lowered) or ("stay patient" in lowered) or ("up 17" in lowered)


def test_choose_line_go_point_trailing_is_snappy():
    line = bert_persona.choose_line(
        "go_point",
        "downeast",
        dad_ai_level=4,
        context={"player_score": 102, "bert_score": 86},
    )

    lowered = line.lower()
    assert (
        ("about time" in lowered)
        or ("drag this back" in lowered)
        or ("press this board" in lowered)
        or ("pressure money" in lowered)
        or ("turnin with the tide" in lowered)
        or ("gets weighed true" in lowered)
        or ("dock money" in lowered)
        or ("set the nets proper" in lowered)
        or ("hull straight" in lowered)
    )


def test_level5_learning_acknowledges_new_player_pattern_once():
    context = {"player_hand_points": 12, "player_score": 70, "bert_score": 72}

    first = bert_persona.choose_line("hand_scored", "downeast", dad_ai_level=5, context=context)
    second = bert_persona.choose_line("hand_scored", "downeast", dad_ai_level=5, context=context)

    assert "remember" in first.lower()
    assert "remember" not in second.lower()


def test_level5_learning_ack_uses_downeast_warning_tone():
    line = bert_persona.choose_line(
        "crib_scored",
        "downeast",
        dad_ai_level=5,
        context={"crib_points": 7, "bert_is_dealer": False, "player_score": 80, "bert_score": 82},
    )

    lowered = line.lower()
    assert "remember" in lowered
    assert ("ayuh" in lowered) or ("bub" in lowered) or ("wicked" in lowered)


def test_choose_line_game_start_uses_stoic_path_when_ahead():
    line = bert_persona.choose_line(
        "game_start",
        "downeast",
        dad_ai_level=4,
        context={"bert_score": 40, "player_score": 26},
    )

    lowered = line.lower()
    assert ("measured" in lowered) or ("tidy" in lowered) or ("honest" in lowered)


def test_choose_line_level_selected_uses_frustrated_path_when_behind():
    line = bert_persona.choose_line(
        "level_selected",
        "downeast",
        dad_ai_level=4,
        context={"bert_score": 20, "player_score": 35},
    )

    lowered = line.lower()
    assert ("no patient mood" in lowered) or ("done givin easy pegs" in lowered)


def test_mood_lanes_start_frustration_at_down_five():
    assert bert_persona._bert_mood(-5) == "frustrated"
    assert bert_persona._bert_mood(-11) == "hot"
    assert bert_persona._bert_mood(-18) == "boiling"


def test_level5_play_posture_escalates_with_trailing_gap():
    assert bert_persona.level5_play_posture({"bert_score": 60, "player_score": 65}) == "balanced"
    assert bert_persona.level5_play_posture({"bert_score": 60, "player_score": 75}) == "deliberate"
    assert bert_persona.level5_play_posture({"bert_score": 60, "player_score": 82}) == "cutthroat"


def test_gap_overlay_progresses_at_five_bands() -> None:
    assert bert_persona._gap_progression_overlay(-5)
    assert bert_persona._gap_progression_overlay(-10)
    assert bert_persona._gap_progression_overlay(-15)
    assert bert_persona._gap_progression_overlay(-20)
    assert bert_persona._gap_progression_overlay(5)
    assert bert_persona._gap_progression_overlay(10)
    assert bert_persona._gap_progression_overlay(15)
    assert bert_persona._gap_progression_overlay(20)


def test_round_summary_line_exists_for_bert_downeast() -> None:
    line = bert_persona.choose_line(
        "round_summary",
        "downeast",
        dad_ai_level=4,
        context={
            "player_score": 84,
            "bert_score": 90,
            "player_hand_points": 6,
            "bert_hand_points": 8,
            "crib_points": 4,
            "player_pegging_points": 3,
            "bert_pegging_points": 5,
        },
    )

    lowered = line.lower()
    assert line
    assert ("round" in lowered) or ("hand" in lowered) or ("summary" in lowered)
    assert ("crib" in lowered) or ("pegg" in lowered)


def test_round_summary_line_exists_for_barnabas_downeast() -> None:
    line = bert_persona.choose_line(
        "round_summary",
        "downeast",
        dad_ai_level=5,
        context={
            "player_score": 102,
            "bert_score": 96,
            "player_hand_points": 10,
            "bert_hand_points": 7,
            "crib_points": 2,
            "player_pegging_points": 4,
            "bert_pegging_points": 2,
        },
    )

    lowered = line.lower()
    assert line
    assert ("round" in lowered) or ("hand" in lowered)
