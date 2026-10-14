"""Backup-before-write and preset unknown-key skipping."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lgtv_mcp.backups import list_backups, read_backup, write_backup
from lgtv_mcp.config import Config
from lgtv_mcp.presets import MANUAL_STEPS, get_preset
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
    # backup written before set_settings
    client.set_settings.assert_awaited_once_with("picture", {"backlight": 80})


@pytest.mark.asyncio
async def test_apply_preset_skips_unknown_keys(config: Config):
    mcp = create_mcp(config)
    tool = mcp._tool_manager._tools["apply_preset"]
    preset = get_preset("ps5_hdr")

    # TV only returns a subset
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
        return {"settings": {k: returned[k] for k in keys if k in returned}}

    client.get_system_settings = AsyncMock(side_effect=fake_get)
    client.set_picture_mode = AsyncMock()
    client.set_picture_settings = AsyncMock()
    client.disconnect = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("lgtv_mcp.server.connected_client", return_value=mock_cm):
        result = await tool.fn(name="ps5_hdr", tv_input="hdmi1", dry_run=False)

    assert result["ok"] is True
    skipped = set(result["skipped_unknown_keys"])
    assert "hdrDynamicToneMapping" in skipped
    assert "superResolution" in skipped
    assert "dynamicContrast" in skipped
    applied = result["to_apply"]
    assert "hdrDynamicToneMapping" not in applied
    assert applied["backlight"] == 100
    client.set_picture_settings.assert_awaited()
    args = client.set_picture_settings.await_args.args
    assert "hdrDynamicToneMapping" not in args[0]
    assert result["manual_steps"] == MANUAL_STEPS
    assert preset["pic_mode"] == "hdrGame"


@pytest.mark.asyncio
async def test_apply_preset_dry_run(config: Config):
    mcp = create_mcp(config)
    tool = mcp._tool_manager._tools["apply_preset"]

    client = AsyncMock()
    client.get_system_settings = AsyncMock(
        return_value={"settings": {"backlight": 80, "contrast": 85, "brightness": 50,
                                   "superResolution": "off", "sharpness": 0,
                                   "dynamicContrast": "off", "gamma": "medium"}}
    )
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("lgtv_mcp.server.connected_client", return_value=mock_cm):
        result = await tool.fn(name="ps5_sdr", dry_run=True)

    assert result["dry_run"] is True
    client.set_picture_settings.assert_not_called()
    client.set_picture_mode.assert_not_called()
