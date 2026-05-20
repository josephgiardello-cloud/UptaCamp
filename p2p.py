"""Direct peer-to-peer networking for cribbage.

One player hosts (P2PHost) and the other connects (P2PGuest).
No central server is required — traffic is a direct WebSocket connection
between the two machines.

Usage — host::

    host = P2PHost()
    host.start("Alice")           # starts server in background thread
    print("Share:", host.address) # e.g. "192.168.1.5:12345"
    # game loop:
    msg = host.get_incoming()     # non-blocking; returns dict or None
    host.send({"type": "state", ...})
    host.stop()

Usage — guest::

    guest = P2PGuest("192.168.1.5:12345")
    guest.connect("Bob")
    # wait until guest.connected is True
    msg = guest.get_incoming()    # non-blocking; returns dict or None
    guest.send({"type": "action", "kind": "discard", ...})
    guest.stop()
"""

from __future__ import annotations

import asyncio
import json
import queue
import socket
import threading
from typing import Any

try:
    import websockets  # type: ignore[import-untyped]

    _HAS_WEBSOCKETS = True
except ImportError:
    _HAS_WEBSOCKETS = False

DEFAULT_PORT = 12345
_BASE36_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def get_local_ip() -> str:
    """Best-effort LAN IP address; falls back to 127.0.0.1."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def _to_base36(value: int) -> str:
    if value < 0:
        raise ValueError("base36 value must be non-negative")
    if value == 0:
        return "0"
    out: list[str] = []
    while value:
        value, rem = divmod(value, 36)
        out.append(_BASE36_ALPHABET[rem])
    return "".join(reversed(out))


def _from_base36(text: str) -> int:
    t = text.strip().upper()
    if not t:
        raise ValueError("join code is empty")
    value = 0
    for ch in t:
        idx = _BASE36_ALPHABET.find(ch)
        if idx < 0:
            raise ValueError("join code contains invalid characters")
        value = value * 36 + idx
    return value


def ip_to_join_code(ip: str) -> str:
    """Encode an IPv4 address as a short base36 join code.

    The code contains only letters/numbers and is easier to share than
    dotted-decimal notation.
    """
    packed = socket.inet_aton(ip)
    value = int.from_bytes(packed, byteorder="big", signed=False)
    return _to_base36(value)


def join_code_to_ip(code: str) -> str:
    """Decode a base36 join code back into an IPv4 address."""
    value = _from_base36(code)
    if value < 0 or value > 0xFFFFFFFF:
        raise ValueError("join code is out of range")
    packed = value.to_bytes(4, byteorder="big", signed=False)
    return socket.inet_ntoa(packed)


class P2PError(RuntimeError):
    pass


class _P2PBase:
    """Shared machinery: background asyncio loop + thread-safe in/out queues."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._in: queue.Queue[dict[str, Any]] = queue.Queue()
        self._out: queue.Queue[dict[str, Any]] = queue.Queue()
        self.last_error: str | None = None

    def send(self, msg: dict[str, Any]) -> None:
        """Queue a message to deliver to the remote peer."""
        self._out.put(msg)

    def get_incoming(self) -> dict[str, Any] | None:
        """Return the next message received from the peer, or None if the
        queue is empty."""
        try:
            return self._in.get_nowait()
        except queue.Empty:
            return None

    def stop(self) -> None:
        """Signal the background loop to stop."""
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.5)

    def _run_in_thread(self, coro_fn) -> None:  # type: ignore[type-arg]
        def _target() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(coro_fn())
            except Exception as exc:
                self.last_error = str(exc)
            finally:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
                self._loop.close()
                self._loop = None

        self._thread = threading.Thread(target=_target, daemon=True)
        self._thread.start()


class P2PHost(_P2PBase):
    """
    Run a WebSocket server so a remote guest can connect directly.

    The server listens on ``0.0.0.0:<port>`` and accepts exactly one guest.
    All subsequent connection attempts are rejected with an "room is full"
    error until the guest disconnects.
    """

    def __init__(self, port: int = DEFAULT_PORT) -> None:
        super().__init__()
        self.port = port
        self.local_ip = get_local_ip()
        self.host_name: str = "Host"
        self.guest_name: str | None = None
        self._guest_ws: Any = None
        self._ready = threading.Event()

    @property
    def address(self) -> str:
        """Human-readable IP:port string to share with the guest."""
        return f"{self.local_ip}:{self.port}"

    @property
    def guest_connected(self) -> bool:
        return self._guest_ws is not None

    def start(self, host_name: str = "Host") -> None:
        """Start the WebSocket server in a background thread."""
        if not _HAS_WEBSOCKETS:
            raise P2PError("The 'websockets' package is required for direct P2P play")
        self.host_name = host_name
        self._run_in_thread(self._serve)
        if not self._ready.wait(timeout=6.0):
            raise P2PError(f"Could not bind WebSocket server on port {self.port}")

    async def _serve(self) -> None:
        async with websockets.serve(self._handler, "0.0.0.0", self.port):
            self._ready.set()
            while not self._stop.is_set():
                await asyncio.sleep(0.05)
                if self._guest_ws is not None:
                    await self._flush_outbound()

    async def _flush_outbound(self) -> None:
        """Drain the outbound queue and send to the connected guest."""
        while True:
            try:
                msg = self._out.get_nowait()
            except queue.Empty:
                break
            if self._guest_ws is None:
                break
            try:
                await self._guest_ws.send(json.dumps(msg))
            except Exception:
                self._guest_ws = None
                self.guest_name = None
                break

    async def _handler(self, websocket: Any) -> None:
        if self._guest_ws is not None:
            await websocket.send(json.dumps({"type": "error", "msg": "Room is full"}))
            await websocket.close()
            return

        self._guest_ws = websocket
        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if msg.get("type") == "hello":
                    self.guest_name = str(msg.get("name", "Guest"))
                    await websocket.send(
                        json.dumps({"type": "welcome", "host_name": self.host_name})
                    )
                else:
                    self._in.put(msg)
        except Exception:
            pass
        finally:
            self._guest_ws = None
            self.guest_name = None


class P2PGuest(_P2PBase):
    """
    Connect directly to a P2PHost by IP:port.

    ``host_address`` may be ``"192.168.1.5:12345"`` or just ``"192.168.1.5"``
    (uses DEFAULT_PORT in that case).
    """

    def __init__(self, host_address: str) -> None:
        super().__init__()
        if ":" in host_address:
            host, port_str = host_address.rsplit(":", 1)
            self.host = host.strip()
            self.port = int(port_str)
        else:
            self.host = host_address.strip()
            self.port = DEFAULT_PORT
        self.guest_name: str = "Guest"
        self.host_name: str | None = None
        self._connected = threading.Event()

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def connect(self, guest_name: str = "Guest") -> None:
        """Begin connecting to the host in a background thread."""
        if not _HAS_WEBSOCKETS:
            raise P2PError("The 'websockets' package is required for direct P2P play")
        self.guest_name = guest_name
        self._run_in_thread(self._connect_loop)

    async def _connect_loop(self) -> None:
        uri = f"ws://{self.host}:{self.port}"
        try:
            async with websockets.connect(uri, open_timeout=8) as ws:
                await ws.send(json.dumps({"type": "hello", "name": self.guest_name}))
                self._connected.set()
                while not self._stop.is_set():
                    # Drain outbound queue first
                    while True:
                        try:
                            msg = self._out.get_nowait()
                            await ws.send(json.dumps(msg))
                        except queue.Empty:
                            break
                    # Non-blocking receive
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=0.05)
                        msg = json.loads(raw)
                        if msg.get("type") == "welcome":
                            self.host_name = str(msg.get("host_name", "Host"))
                        else:
                            self._in.put(msg)
                    except asyncio.TimeoutError:
                        pass
        except Exception as exc:
            self.last_error = str(exc)
        finally:
            self._connected.clear()
