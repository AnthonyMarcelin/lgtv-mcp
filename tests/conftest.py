"""Shared fixtures: env config, temp DATA_DIR, never hit a real TV."""

from __future__ import annotations

from pathlib import Path

import pytest

from lgtv_mcp.config import Config


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    (d / "backups").mkdir(parents=True)
    return d


@pytest.fixture
def config(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("MCP_BEARER_TOKEN", "test-token-secret-value")
    monkeypatch.setenv("LGTV_HOST", "192.168.1.137")
    monkeypatch.setenv("LGTV_MAC", "AA:BB:CC:DD:EE:FF")
    monkeypatch.setenv("LGTV_BROADCAST", "192.168.1.255")
    monkeypatch.setenv("MCP_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "8765")
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    return Config(
        lgtv_host="192.168.1.137",
        lgtv_mac="AA:BB:CC:DD:EE:FF",
        lgtv_broadcast="192.168.1.255",
        mcp_bind_host="127.0.0.1",
        mcp_port=8765,
        mcp_bearer_token="test-token-secret-value",
        data_dir=data_dir,
    )


@pytest.fixture
def auth_header() -> dict[str, str]:
    return {"Authorization": "Bearer test-token-secret-value"}
