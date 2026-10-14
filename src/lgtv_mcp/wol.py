"""Wake-on-LAN magic packet helpers (raw UDP, no third-party deps)."""

from __future__ import annotations

import re
import socket


_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")


def parse_mac(mac: str) -> bytes:
    """Parse a MAC address into 6 bytes. Accepts : or - separators."""
    mac = mac.strip()
    if not _MAC_RE.match(mac):
        raise ValueError(f"Invalid MAC address: {mac!r}")
    parts = re.split(r"[:-]", mac)
    return bytes(int(p, 16) for p in parts)


def build_magic_packet(mac: str) -> bytes:
    """Build a standard WOL magic packet: 6x FF + 16x MAC."""
    mac_bytes = parse_mac(mac)
    return b"\xff" * 6 + mac_bytes * 16


def send_magic_packet(
    mac: str,
    broadcast: str = "255.255.255.255",
    ports: tuple[int, ...] = (9, 7),
) -> dict:
    """Send a WOL magic packet to broadcast on the given UDP ports."""
    packet = build_magic_packet(mac)
    sent: list[dict] = []
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            nbytes = sock.sendto(packet, (broadcast, port))
            sent.append({"broadcast": broadcast, "port": port, "bytes": nbytes})
    return {"sent": True, "mac": mac.upper().replace("-", ":"), "targets": sent}
