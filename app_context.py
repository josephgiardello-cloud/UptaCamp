from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
    fps_cap: int = 60
    online_poll_interval_s: float = 2.0
    online_reconnect_delay_s: float = 2.0
    player_id: str | None = None
    display_name: str | None = None
    session_token: str | None = None
    current_match_id: str | None = None
    last_error: str = ""
    status_message: str = ""
    game_state: GameState = field(default_factory=GameState)

    # Direct P2P fields (no central server required)
    p2p_host: Any = None   # p2p.P2PHost when this player is hosting
    p2p_guest: Any = None  # p2p.P2PGuest when this player is joining
    p2p_role: str = ""     # "host" | "guest" | ""
    p2p_name: str = ""     # display name for this player in P2P match

    def __post_init__(self) -> None:
        self.client = OnlineClient(self.server_url)
        self.stream: MatchEventStream | None = None

    def reset_stream(self) -> None:
        if self.stream is not None:
            self.stream.stop()
        self.stream = None

    def reset_p2p(self) -> None:
        """Stop and clear any active P2P connection."""
        if self.p2p_host is not None:
            self.p2p_host.stop()
            self.p2p_host = None
        if self.p2p_guest is not None:
            self.p2p_guest.stop()
            self.p2p_guest = None
        self.p2p_role = ""
        self.p2p_name = ""
