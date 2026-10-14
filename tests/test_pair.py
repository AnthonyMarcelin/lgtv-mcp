"""Unit tests for diagnostic pairing flow (fake websocket, no real TV)."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from lgtv_mcp.pair import (
    ERROR_HINT,
    build_register_msg,
    run_pairing_session,
    summarize_tv_message,
)


class FakeWS:
    """Minimal websocket: send is recorded, recv yields queued messages."""

    def __init__(self, messages: list[Any]) -> None:
        self._queue = list(messages)
        self.sent: list[str] = []

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def recv(self) -> str:
        if not self._queue:
            raise asyncio.TimeoutError()
        item = self._queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, dict):
            return json.dumps(item)
        return item

    async def close(self) -> None:
        pass


def _fake_client(*, key: str | None = None) -> MagicMock:
    client = MagicMock()
    client.manifest = {"appVersion": "1.0"}
    client.client_key = key
    client.storage = MagicMock()
    client.storage.set_key = AsyncMock()
    return client


def test_summarize_never_includes_client_key() -> None:
    msg = {
        "type": "registered",
        "id": "register_0",
        "payload": {"client-key": "SECRET_KEY_VALUE", "pairingType": "PROMPT"},
    }
    line = summarize_tv_message(msg)
    assert "SECRET_KEY_VALUE" not in line
    assert "client-key" not in line
    assert "type=registered" in line


def test_build_register_omits_absent_key() -> None:
    client = _fake_client(key=None)
    msg = build_register_msg(client)
    assert "client-key" not in msg["payload"]
    assert msg["payload"]["pairingType"] == "PROMPT"


def test_build_register_includes_present_key() -> None:
    client = _fake_client(key="existing")
    msg = build_register_msg(client)
    assert msg["payload"]["client-key"] == "existing"


@pytest.mark.asyncio
async def test_registered_saves_key_and_does_not_print_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "super-secret-client-key-xyz"
    ws = FakeWS(
        [
            {
                "type": "registered",
                "id": "register_0",
                "payload": {"client-key": secret, "pairingType": "PROMPT"},
            }
        ]
    )
    client = _fake_client()
    host = "192.168.1.10"
    code = await run_pairing_session(ws, client, host, timeout_s=5.0)
    assert code == 0
    client.storage.set_key.assert_awaited_once_with(host, secret)
    assert client.client_key == secret
    out = capsys.readouterr()
    assert "paired" in out.out
    assert secret not in out.out
    assert secret not in out.err


@pytest.mark.asyncio
async def test_error_exits_1_with_hint(capsys: pytest.CaptureFixture[str]) -> None:
    ws = FakeWS(
        [
            {
                "type": "error",
                "id": "register_0",
                "payload": {"error": "403", "pairingType": None},
            }
        ]
    )
    client = _fake_client()
    code = await run_pairing_session(ws, client, "192.168.1.10", timeout_s=5.0)
    assert code == 1
    client.storage.set_key.assert_not_awaited()
    err = capsys.readouterr().err
    assert "403" in err
    assert ERROR_HINT in err


@pytest.mark.asyncio
async def test_prompt_response_then_registered(
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "key-after-prompt"
    ws = FakeWS(
        [
            {
                "type": "response",
                "id": "register_0",
                "payload": {"pairingType": "PROMPT"},
            },
            {
                "type": "registered",
                "id": "register_0",
                "payload": {"client-key": secret},
            },
        ]
    )
    client = _fake_client()
    host = "192.168.1.10"
    code = await run_pairing_session(ws, client, host, timeout_s=5.0)
    assert code == 0
    client.storage.set_key.assert_awaited_once_with(host, secret)
    out = capsys.readouterr()
    assert "pairingType=PROMPT" in out.out
    assert "type=registered" in out.out
    assert "paired" in out.out
    assert secret not in out.out
    assert secret not in out.err
