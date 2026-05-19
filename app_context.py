from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from online_client import MatchEventStream, OnlineClient


@dataclass
class AppContext:
    online_enabled: bool = False
    server_url: str = "http://127.0.0.1:8787"
    ws_url: str = "ws://127.0.0.1:8790"
    volume: float = 0.6
    animations_enabled: bool = True
    preferred_online_ai_level: int = 2
    player_id: Optional[str] = None
    display_name: Optional[str] = None
    session_token: Optional[str] = None
    current_match_id: Optional[str] = None
    last_error: str = ""
    status_message: str = ""

    def __post_init__(self) -> None:
        self.client = OnlineClient(self.server_url)
        self.stream: Optional[MatchEventStream] = None

    def reset_stream(self) -> None:
        if self.stream is not None:
            self.stream.stop()
        self.stream = None
