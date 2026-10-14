"""Backup-before-write and preset unknown-key skipping."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lgtv_mcp.backups import list_backups, read_backup, write_backup
from lgtv_mcp.config import Config
from lgtv_mcp.presets import MANUAL_STEPS_PS5, get_preset, resolve_preset_variants
from lgtv_mcp.server import create_mcp


def test_write_and_list_backup(data_dir: Path):
    backups = data_dir / "backups"
    path = write_backup(backups, {"backlight": 50}, name="snap1")
    assert path.name == "snap1.json"
    data = read_backup(backups, "snap1")
    assert data["settings"]["backlight"] == 50
    items = list_backups(backups)
    assert any(i["name"] == "snap1" for i in items)


def test_auto_backup_name(data_dir: Path):
    path = write_backup(data_dir / "backups", {"contrast": 90})
    assert path.name.startswith("auto-")
    assert path.name.endswith(".json")


def test_preset_defaults_and_aliases():
    ps5 = get_preset("ps5")
    assert ps5["tv_input"] == "hdmi3"
    assert ps5["variants"]["sdr"]["pic_mode"] == "game"
    assert ps5["variants"]["hdr"]["pic_mode"] == "hdrGame"
    assert ps5["variants"]["sdr"]["settings"]["dynamicColor"] == "off"
    assert ps5["variants"]["sdr"]["settings"]["contrast"] == 100
    assert "backlight" not in ps5["variants"]["sdr"]["settings"]
    assert ps5["variants"]["hdr"]["settings"]["hdrDynamicToneMapping"] == "HGIG"

    switch2 = get_preset("switch2")
    assert switch2["tv_input"] == "hdmi2"
    assert switch2["variants"]["hdr"]["settings"] == ps5["variants"]["hdr"]["settings"]

    base, preset, variants = resolve_preset_variants("ps5_hdr")
    assert base == "ps5"
    assert variants == ["hdr"]
    assert preset["tv_input"] == "hdmi3"


@pytest.mark.asyncio
async def test_set_picture_settings_backs_up_before_write(config: Config):
    mcp = create_mcp(config)
    tool = mcp._tool_manager._tools["set_picture_settings"]

    client = AsyncMock()
    client.is_registered.return_value = True
    client.get_system_settings = AsyncMock(
        side_effect=[
            {"settings": {"backlight": 40}},  # before
            {"settings": {"backlight": 80}},  # after
        ]
    )
    client.set_settings = AsyncMock()
    client.disconnect = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("lgtv_mcp.server.connected_client", return_value=mock_cm):
        result = await tool.fn(settings={"backlight": 80})

    assert result["ok"] is True
    assert result["before"]["backlight"] == 40
    assert result["after"]["backlight"] == 80
    assert result["backup"].startswith("auto-")
    backup_file = config.backups_dir / result["backup"]
    assert backup_file.is_file()
    client.set_settings.assert_awaited_once_with("picture", {"backlight": 80})


@pytest.mark.asyncio
async def test_apply_preset_skips_rejected_and_missing(config: Config):
    mcp = create_mcp(config)
    tool = mcp._tool_manager._tools["apply_preset"]

    # TV returns only a subset for hdr keys
    returned = {
        "backlight": 100,
        "contrast": 100,
        "brightness": 50,
        "sharpness": 0,
        # missing: hdrDynamicToneMapping, superResolution, dynamicContrast
    }

    client = AsyncMock()
    client.is_registered.return_value = True

    async def fake_get(category: str, keys: list[str], **_kw: Any):
        assert category == "picture$hdmi3.hdrGame.2d.x"
        return {"settings": {k: returned[k] for k in keys if k in returned}}

    client.get_system_settings = AsyncMock(side_effect=fake_get)
    client.set_picture_settings = AsyncMock()
    client.disconnect = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("lgtv_mcp.server.connected_client", return_value=mock_cm):
        result = await tool.fn(name="ps5_hdr", dry_run=False)

    assert result["ok"] is True
    hdr = result["hdr"]
    assert hdr["pic_mode"] == "hdrGame"
    assert hdr["tv_input"] == "hdmi3"
    skipped = hdr["skipped"]
    assert skipped["hdrDynamicToneMapping"] == "missing"
    assert skipped["superResolution"] == "missing"
    assert skipped["dynamicContrast"] == "missing"
    applied = hdr["to_apply"]
    assert "hdrDynamicToneMapping" not in applied
    assert applied["backlight"] == 100
    client.set_picture_settings.assert_awaited()
    args = client.set_picture_settings.await_args.args
    assert "hdrDynamicToneMapping" not in args[0]
    assert args[1] == "hdrGame"
    assert args[2] == "hdmi3"
    assert result["manual_steps"] == MANUAL_STEPS_PS5


@pytest.mark.asyncio
async def test_apply_preset_both_variants_and_isolation(config: Config):
    mcp = create_mcp(config)
    tool = mcp._tool_manager._tools["apply_preset"]

    client = AsyncMock()
    client.is_registered.return_value = True

    async def fake_get(category: str, keys: list[str], **_kw: Any):
        if "hdrGame" in category:
            raise RuntimeError("simulated hdr failure")
        values = {
            "superResolution": "off",
            "sharpness": 0,
            "dynamicContrast": "off",
            "dynamicColor": "off",
            "brightness": 50,
            "contrast": 100,
            "gamma": "medium",
        }
        return {"settings": {k: values[k] for k in keys if k in values}}

    client.get_system_settings = AsyncMock(side_effect=fake_get)
    client.set_picture_settings = AsyncMock()
    client.disconnect = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("lgtv_mcp.server.connected_client", return_value=mock_cm):
        result = await tool.fn(name="ps5", variants=["sdr", "hdr"], dry_run=False)

    assert "error" not in result["sdr"]
    assert result["sdr"]["tv_input"] == "hdmi3"
    assert "error" in result["hdr"]
    assert result["ok"] is False
    # sdr still wrote despite hdr failure
    assert client.set_picture_settings.await_count == 1


@pytest.mark.asyncio
async def test_apply_preset_dry_run(config: Config):
    mcp = create_mcp(config)
    tool = mcp._tool_manager._tools["apply_preset"]

    client = AsyncMock()

    async def fake_get(category: str, keys: list[str], **_kw: Any):
        return {"settings": {k: 0 for k in keys}}

    client.get_system_settings = AsyncMock(side_effect=fake_get)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("lgtv_mcp.server.connected_client", return_value=mock_cm):
        result = await tool.fn(name="ps5_sdr", dry_run=True)

    assert result["dry_run"] is True
    assert "sdr" in result
    assert result["sdr"]["after"] is None
    client.set_picture_settings.assert_not_called()


@pytest.mark.asyncio
async def test_get_settings_per_key_fallback(config: Config):
    mcp = create_mcp(config)
    tool = mcp._tool_manager._tools["get_settings"]

    client = AsyncMock()
    client.is_registered.return_value = True

    calls: list[tuple[str, list[str]]] = []

    async def fake_get(category: str, keys: list[str], **_kw: Any):
        calls.append((category, list(keys)))
        if len(keys) > 1:
            raise RuntimeError("400 not allowed")
        key = keys[0]
        if key == "vrr":
            raise RuntimeError("not allowed")
        if key == "ghost":
            return {"settings": {}}
        return {"settings": {key: "ok"}}

    client.get_system_settings = AsyncMock(side_effect=fake_get)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("lgtv_mcp.server.connected_client", return_value=mock_cm):
        result = await tool.fn(
            keys=["backlight", "vrr", "ghost"],
            pic_mode="game",
            tv_input="hdmi3",
        )

    assert result["found"] == {"backlight": "ok"}
    assert result["missing"] == ["ghost"]
    assert "vrr" in result["rejected"]
    assert result["pic_mode"] == "game"
    assert result["tv_input"] == "hdmi3"
    assert calls[0][0] == "picture$hdmi3.game.2d.x"
