"""Wake-on-LAN magic packet byte layout."""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

import pytest

from lgtv_mcp.wol import build_magic_packet, parse_mac, send_magic_packet


def test_parse_mac_colon_and_dash():
    assert parse_mac("AA:BB:CC:DD:EE:FF") == bytes.fromhex("AABBCCDDEEFF")
    assert parse_mac("aa-bb-cc-dd-ee-ff") == bytes.fromhex("AABBCCDDEEFF")


def test_parse_mac_invalid():
    with pytest.raises(ValueError):
        parse_mac("not-a-mac")


def test_magic_packet_bytes():
    mac = "AA:BB:CC:DD:EE:FF"
    packet = build_magic_packet(mac)
    assert len(packet) == 102
    assert packet[:6] == b"\xff" * 6
    mac_bytes = bytes.fromhex("AABBCCDDEEFF")
    assert packet[6:] == mac_bytes * 16


def test_send_magic_packet_ports_9_and_7():
    with patch("lgtv_mcp.wol.socket.socket") as sock_cls:
        sock = MagicMock()
        sock_cls.return_value.__enter__.return_value = sock
        sock.sendto.return_value = 102
        result = send_magic_packet("AA:BB:CC:DD:EE:FF", broadcast="192.168.1.255")
    assert result["sent"] is True
    ports = sorted(t["port"] for t in result["targets"])
    assert ports == [7, 9]
    assert sock.sendto.call_count == 2
    for call in sock.sendto.call_args_list:
        packet, addr = call.args
        assert packet[:6] == b"\xff" * 6
        assert addr[0] == "192.168.1.255"
        assert addr[1] in (7, 9)
    sock.setsockopt.assert_called_with(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
