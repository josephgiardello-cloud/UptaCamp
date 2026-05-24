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
