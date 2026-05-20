from __future__ import annotations

import socket
import time

from p2p import P2PGuest, P2PHost


def _get_free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    _, port = sock.getsockname()
    sock.close()
    return int(port)


def _wait_until(predicate, timeout: float = 5.0, step: float = 0.02) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if predicate():
            return True
        time.sleep(step)
    return False


def _wait_for_message(receiver, timeout: float = 5.0, step: float = 0.02):
    start = time.time()
    while time.time() - start < timeout:
        msg = receiver.get_incoming()
        if msg is not None:
            return msg
        time.sleep(step)
    return None


def test_p2p_host_guest_roundtrip_localhost() -> None:
    """Smoke-test a real direct connection (no central server).

    This test runs an actual host WebSocket server and guest client in
    background threads, then validates handshake + two-way message flow.
    """

    port = _get_free_port()
    host = P2PHost(port=port)
    guest = P2PGuest(f"127.0.0.1:{port}")

    try:
        host.start("Alice")
        guest.connect("Bob")

        assert _wait_until(lambda: host.guest_connected), "guest did not connect to host"
        assert _wait_until(lambda: guest.connected), "guest connection flag was not set"
        assert _wait_until(lambda: guest.host_name == "Alice"), "welcome handshake missing"

        # Host -> guest
        host.send({"type": "state", "phase": "discard", "message": "hello from host"})
        to_guest = _wait_for_message(guest)
        assert to_guest is not None, "guest did not receive host message"
        assert to_guest.get("type") == "state"
        assert to_guest.get("message") == "hello from host"

        # Guest -> host
        guest.send({"type": "discard", "cards": ["5_of_hearts", "7_of_spades"]})
        to_host = _wait_for_message(host)
        assert to_host is not None, "host did not receive guest message"
        assert to_host == {"type": "discard", "cards": ["5_of_hearts", "7_of_spades"]}
    finally:
        guest.stop()
        host.stop()
