"""P2P lobby state — enter your name, then host or join a direct game.

Host flow:
  Player presses H → P2PHost starts on a free port → displays "Share this
  address: 192.168.1.5:12345" → waits for guest → when guest connects,
  transitions to P2PMatchState.

Join flow:
  Player presses J → types the host's IP:port → connects → transitions to
  P2PMatchState once the welcome handshake completes.
"""

from __future__ import annotations

import pygame

from p2p import (
    DEFAULT_PORT,
    P2PError,
    P2PGuest,
    P2PHost,
    ip_to_join_code,
    join_code_to_ip,
)

from .base import GameStateBase


class P2PLobbyState(GameStateBase):
    """Name entry + host / join selector for direct P2P play."""

    def __init__(self) -> None:
        self.name: str = ""
        self.address_input: str = ""
        self.join_code: str = ""
        self.mode: str | None = None  # None | "hosting" | "joining" | "connecting"
        self.error: str = ""
        self.status: str = ""

    # ------------------------------------------------------------------ events

    def handle_event(self, event: pygame.event.Event, engine, assets, app) -> object:
        if event.type != pygame.KEYDOWN:
            return self

        if event.key == pygame.K_ESCAPE:
            self._cleanup(app)
            from .intro import IntroState

            return IntroState()

        if self.mode is None:
            return self._handle_name_input(event, app)
        if self.mode == "joining":
            return self._handle_address_input(event, app)
        # "hosting" / "connecting": no keyboard needed — just wait
        return self

    def _handle_name_input(self, event: pygame.event.Event, app) -> P2PLobbyState:
        if event.key == pygame.K_BACKSPACE:
            self.name = self.name[:-1]
        elif event.key == pygame.K_h:
            self._start_hosting(app)
        elif event.key == pygame.K_j:
            self.mode = "joining"
            self.status = "Enter host join code or address"
        elif event.unicode and event.unicode.isprintable() and len(self.name) < 24:
            self.name += event.unicode
        return self

    def _handle_address_input(self, event: pygame.event.Event, app) -> P2PLobbyState:
        if event.key == pygame.K_BACKSPACE:
            self.address_input = self.address_input[:-1]
        elif event.key == pygame.K_RETURN:
            self._start_joining(app)
        elif event.unicode and event.unicode.isprintable() and len(self.address_input) < 48:
            self.address_input += event.unicode
        return self

    # ------------------------------------------------------------------ actions

    def _start_hosting(self, app) -> None:
        name = self.name.strip() or "Host"
        try:
            host = P2PHost()
            host.start(name)
            app.p2p_host = host
            app.p2p_guest = None
            app.p2p_role = "host"
            app.p2p_name = name
            self.mode = "hosting"
            self.status = host.address
            self.join_code = ip_to_join_code(host.local_ip)
            self.error = ""
        except P2PError as exc:
            self.error = str(exc)

    def _start_joining(self, app) -> None:
        raw = self.address_input.strip()
        if not raw:
            self.error = f"Enter a join code or address like 192.168.1.5:{DEFAULT_PORT}"
            return
        addr = self._normalize_address(raw)
        if addr is None:
            self.error = "Invalid join code. Ask host to re-check it."
            return
        name = self.name.strip() or "Guest"
        try:
            guest = P2PGuest(addr)
            guest.connect(name)
            app.p2p_guest = guest
            app.p2p_host = None
            app.p2p_role = "guest"
            app.p2p_name = name
            self.mode = "connecting"
            self.status = f"Connecting to {addr}…"
            self.error = ""
        except P2PError as exc:
            self.error = str(exc)

    def _normalize_address(self, raw: str) -> str | None:
        """Accept IP:port, IP, or short join code.

        - If port is omitted, DEFAULT_PORT is assumed.
        - If input has no dots/colon, treat it as join code.
        """
        text = raw.strip()
        if ":" in text:
            return text
        if "." in text:
            return f"{text}:{DEFAULT_PORT}"
        compact = text.replace("-", "").replace(" ", "")
        try:
            ip = join_code_to_ip(compact)
        except ValueError:
            return None
        return f"{ip}:{DEFAULT_PORT}"

    def _cleanup(self, app) -> None:
        if getattr(app, "p2p_host", None):
            app.p2p_host.stop()
            app.p2p_host = None
        if getattr(app, "p2p_guest", None):
            app.p2p_guest.stop()
            app.p2p_guest = None

    # ------------------------------------------------------------------ update

    def update(self, engine, dt: int, app) -> object:
        if self.mode == "hosting":
            host: P2PHost | None = getattr(app, "p2p_host", None)
            if host and host.guest_connected:
                from .p2p_match import P2PMatchState

                return P2PMatchState()

        if self.mode == "connecting":
            guest: P2PGuest | None = getattr(app, "p2p_guest", None)
            if guest:
                if guest.connected:
                    from .p2p_match import P2PMatchState

                    return P2PMatchState()
                if guest.last_error:
                    self.error = guest.last_error
                    self.mode = "joining"
                    app.p2p_guest = None

        return None

    # ------------------------------------------------------------------ draw

    def draw(self, screen: pygame.Surface, engine, assets, app) -> None:
        screen.fill((16, 24, 32))
        W = screen.get_width()
        H = screen.get_height()
        title_font = pygame.font.SysFont(None, 60)
        body_font = pygame.font.SysFont(None, 34)
        small_font = pygame.font.SysFont(None, 26)

        title = title_font.render("Direct P2P Match", True, (245, 245, 245))
        screen.blit(title, title.get_rect(center=(W // 2, 72)))

        if self.mode is None:
            self._draw_name_entry(screen, W, body_font, small_font)
        elif self.mode == "hosting":
            self._draw_hosting(screen, W, body_font, small_font, app)
        elif self.mode in ("joining", "connecting"):
            self._draw_joining(screen, W, body_font, small_font)

        if self.error:
            err = body_font.render(self.error, True, (230, 100, 100))
            screen.blit(err, err.get_rect(center=(W // 2, H - 60)))

    def _draw_name_entry(
        self,
        screen: pygame.Surface,
        W: int,
        body_font: pygame.font.Font,
        small_font: pygame.font.Font,
    ) -> None:
        prompt = body_font.render("Your name:", True, (200, 220, 235))
        screen.blit(prompt, prompt.get_rect(center=(W // 2, 150)))

        box = pygame.Rect(W // 2 - 200, 175, 400, 52)
        pygame.draw.rect(screen, (240, 240, 240), box, border_radius=8)
        pygame.draw.rect(screen, (90, 140, 200), box, width=2, border_radius=8)
        entry = body_font.render(self.name or "Type name…", True, (20, 20, 20))
        screen.blit(entry, (box.x + 12, box.y + 12))

        for i, (key, text) in enumerate([
            ("H", "Host a game  —  others connect to you"),
            ("J", "Join a game  —  enter join code or host address"),
            ("Esc", "Back to main menu"),
        ]):
            col = (160, 220, 160) if key != "Esc" else (180, 180, 180)
            line = body_font.render(f"{key})  {text}", True, col)
            screen.blit(line, line.get_rect(center=(W // 2, 290 + i * 52)))

    def _draw_hosting(
        self,
        screen: pygame.Surface,
        W: int,
        body_font: pygame.font.Font,
        small_font: pygame.font.Font,
        app,
    ) -> None:
        addr = self.status  # set to host.address
        for y, (text, color) in enumerate([
            ("Hosting at:", (210, 210, 210)),
            (addr, (120, 240, 120)),
            (f"Join code: {self.join_code}", (160, 220, 255)),
            ("Share code or address with your opponent.", (200, 200, 200)),
            ("Waiting for them to connect…", (245, 210, 100)),
        ]):
            s = body_font.render(text, True, color)
            screen.blit(s, s.get_rect(center=(W // 2, 160 + y * 56)))

    def _draw_joining(
        self,
        screen: pygame.Surface,
        W: int,
        body_font: pygame.font.Font,
        small_font: pygame.font.Font,
    ) -> None:
        prompt = body_font.render("Host join code or address:", True, (200, 220, 235))
        screen.blit(prompt, prompt.get_rect(center=(W // 2, 150)))

        box = pygame.Rect(W // 2 - 240, 175, 480, 52)
        pygame.draw.rect(screen, (240, 240, 240), box, border_radius=8)
        pygame.draw.rect(screen, (90, 140, 200), box, width=2, border_radius=8)
        display = self.address_input or f"e.g. Q1W2E3 or 192.168.1.5:{DEFAULT_PORT}"
        entry = body_font.render(display, True, (20, 20, 20))
        screen.blit(entry, (box.x + 12, box.y + 12))

        hint = small_font.render(
            f"Enter = connect (port defaults to {DEFAULT_PORT})   Esc = back",
            True,
            (180, 180, 180),
        )
        screen.blit(hint, hint.get_rect(center=(W // 2, 252)))

        if self.mode == "connecting" and self.status:
            msg = body_font.render(self.status, True, (245, 210, 100))
            screen.blit(msg, msg.get_rect(center=(W // 2, 330)))
