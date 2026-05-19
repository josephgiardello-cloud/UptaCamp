from __future__ import annotations

from dataclasses import dataclass, field

from game_state import GameState
from online_client import MatchEventStream, OnlineClient


@dataclass
class AppContext:
    online_enabled: bool = False
    server_url: str = "http://127.0.0.1:8787"
    ws_url: str = "ws://127.0.0.1:8790"
    volume: float = 0.6
    animations_enabled: bool = True
    preferred_online_ai_level: int = 2
    player_id: str | None = None
    display_name: str | None = None
    session_token: str | None = None
    current_match_id: str | None = None
    last_error: str = ""
    status_message: str = ""
    game_state: GameState = field(default_factory=GameState)

    def __post_init__(self) -> None:
        self.client = OnlineClient(self.server_url)
        self.stream: MatchEventStream | None = None

    def reset_stream(self) -> None:
        if self.stream is not None:
            self.stream.stop()
        self.stream = None
