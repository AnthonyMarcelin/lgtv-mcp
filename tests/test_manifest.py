"""Manifest packaging, extra permissions, get_status tolerance, write hints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lgtv_mcp.config import Config
from lgtv_mcp.manifest import (
    EXTRA_PERMISSIONS,
    PERMISSION_WRITE_HINT,
    apply_extra_permissions,
    assert_unsigned_manifest,
    packaged_manifest_path,
    resolve_manifest_path,
    write_error_message,
)
from lgtv_mcp.pair import build_register_msg
from lgtv_mcp.server import create_mcp
from lgtv_mcp.tv import create_client


def test_packaged_manifest_has_no_signatures() -> None:
    path = packaged_manifest_path()
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "signed" not in data
    assert "signatures" not in data
    assert "permissions" in data
    assert_unsigned_manifest(data)


def test_resolve_manifest_path_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom = tmp_path / "custom.json"
    custom.write_text('{"permissions":[]}', encoding="utf-8")
    monkeypatch.setenv("LGTV_MANIFEST_PATH", str(custom))
    assert resolve_manifest_path() == custom


def test_extra_permissions_appended(monkeypatch: pytest.MonkeyPatch) -> None:
    assert EXTRA_PERMISSIONS == []
    monkeypatch.setenv(
        "LGTV_EXTRA_PERMISSIONS",
        "WRITE_NOTIFICATION_ALERT,WRITE_SETTINGS",
    )
    manifest = {
        "appVersion": "1.1",
        "manifestVersion": 1,
        "permissions": ["LAUNCH", "READ_SETTINGS"],
    }
    apply_extra_permissions(manifest)
    assert "WRITE_NOTIFICATION_ALERT" in manifest["permissions"]
    assert "WRITE_SETTINGS" in manifest["permissions"]
    assert manifest["permissions"].index("LAUNCH") < manifest["permissions"].index(
        "WRITE_NOTIFICATION_ALERT"
    )


def test_build_register_rejects_signed_manifest() -> None:
    client = MagicMock()
    client.manifest = {"permissions": [], "signed": {"key": "x"}, "signatures": []}
    client.client_key = None
    with pytest.raises(AssertionError):
        build_register_msg(client)


@pytest.mark.asyncio
async def test_create_client_passes_manifest_and_states(
    config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LGTV_EXTRA_PERMISSIONS", "WRITE_SETTINGS")
    fake = MagicMock()
    fake.manifest = {
        "appVersion": "1.1",
        "permissions": ["LAUNCH"],
    }

    async def fake_create(*_a: Any, **kwargs: Any) -> MagicMock:
        fake._create_kwargs = kwargs
        return fake

    with patch("lgtv_mcp.tv.WebOsClient.create", side_effect=fake_create):
        client = await create_client(config)

    assert client is fake
    assert "manifest_file_path" in fake._create_kwargs
    assert Path(fake._create_kwargs["manifest_file_path"]).name == "manifest_comp.json"
    assert "software_info" not in fake._create_kwargs["states"]
    assert "WRITE_SETTINGS" in fake.manifest["permissions"]


@pytest.mark.asyncio
async def test_get_status_tolerant_of_failures(config: Config) -> None:
    mcp = create_mcp(config)
    tool = mcp._tool_manager._tools["get_status"]

    client = AsyncMock()
    client.is_registered = MagicMock(return_value=True)
    client.get_power_state = AsyncMock(return_value={"state": "Active"})
    client.get_system_info = AsyncMock(side_effect=RuntimeError("no system_info"))
    client.get_software_info = AsyncMock(side_effect=RuntimeError("no software_info"))
    client.get_current_app = AsyncMock(side_effect=RuntimeError("no app"))
    client.get_inputs = AsyncMock(side_effect=RuntimeError("no inputs"))
    client.disconnect = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("lgtv_mcp.server.is_paired", AsyncMock(return_value=True)),
        patch("lgtv_mcp.server.connected_client", return_value=mock_cm),
    ):
        result = await tool.fn()

    assert result["reachable"] is True
    assert result["power"] == {"state": "Active"}
    assert result["system_info"] is None
    assert result["software_info"] is None
    assert result["current_input_or_app"] is None
    assert result["inputs"] is None
    assert any("system_info" in w for w in result["warnings"])
    assert any("software_info" in w for w in result["warnings"])
    assert any("current_app" in w for w in result["warnings"])
    assert any("inputs" in w for w in result["warnings"])


@pytest.mark.asyncio
async def test_set_picture_settings_permission_hint(config: Config) -> None:
    mcp = create_mcp(config)
    tool = mcp._tool_manager._tools["set_picture_settings"]

    client = AsyncMock()
    client.is_registered.return_value = True
    client.get_system_settings = AsyncMock(return_value={"settings": {"backlight": 40}})
    client.set_settings = AsyncMock(side_effect=RuntimeError("401 insufficient permissions"))
    client.disconnect = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("lgtv_mcp.server.connected_client", return_value=mock_cm):
        result = await tool.fn(settings={"backlight": 80})

    assert result["error"] == PERMISSION_WRITE_HINT


def test_write_error_message_hint() -> None:
    assert write_error_message(RuntimeError("401")) == PERMISSION_WRITE_HINT
    assert "TV command failed" in write_error_message(RuntimeError("timeout"))
