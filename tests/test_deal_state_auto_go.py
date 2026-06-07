from __future__ import annotations

from types import SimpleNamespace

from states.deal import DealState


class _EngineStub:
    def __init__(self) -> None:
        self.state = SimpleNamespace(
            phase="pegging",
            player_turn=0,
            player_hand=[],
            ai_hand=["ace_of_spades"],
            pegging_pile=[],
            message="Pegging: no valid card, press Go.",
            winner=None,
            scores=[0, 0],
        )
        self.passed: list[int] = []

    def get_valid_moves(self):
        return []

    def pass_pegging_turn(self, player_idx: int):
        self.passed.append(int(player_idx))
        self.state.player_turn = 1
        self.state.message = "Go. Barnabas's turn."
        return {"ok": True, "points": 0, "go_completed": False}


class _AppStub:
    settings = SimpleNamespace(player_name="Player", bert_voice_style="downeast")
    voice = None
    audio = None


def test_update_auto_passes_go_when_player_hand_empty() -> None:
    state = DealState(dad_ai_level=5)
    state.dealt = True
    state.phase = "pegging"

    engine = _EngineStub()
    app = _AppStub()

    state.update(engine, dt=16, app=app)

    assert engine.passed == [0]
    assert int(engine.state.player_turn) == 1


def test_skunk_note_for_player_win() -> None:
    note = DealState._skunk_note([121, 88], winner=0)

    assert "Skunk" in note
    assert "Bert" in note


def test_double_skunk_note_for_bert_win() -> None:
    note = DealState._skunk_note([59, 121], winner=1)

    assert "Double skunk" in note
    assert "you" in note


def test_skunk_note_empty_when_not_skunk() -> None:
    note = DealState._skunk_note([121, 91], winner=0)

    assert note == ""
