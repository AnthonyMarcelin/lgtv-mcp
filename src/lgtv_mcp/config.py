"""Environment-based configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    lgtv_host: str
    lgtv_mac: str | None
    lgtv_broadcast: str
    mcp_bind_host: str
    mcp_port: int
    mcp_bearer_token: str
    data_dir: Path

    @property
    def key_file_path(self) -> Path:
        return self.data_dir / ".aiopylgtv.sqlite"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)


def load_config() -> Config:
    token = os.environ.get("MCP_BEARER_TOKEN", "").strip()
    if not token:
        raise RuntimeError("MCP_BEARER_TOKEN is required")

    data_dir = Path(os.environ.get("DATA_DIR", "/data"))
    return Config(
        lgtv_host=os.environ.get("LGTV_HOST", "192.168.1.137").strip(),
        lgtv_mac=(os.environ.get("LGTV_MAC") or "").strip() or None,
        lgtv_broadcast=os.environ.get("LGTV_BROADCAST", "192.168.1.255").strip(),
        mcp_bind_host=os.environ.get("MCP_BIND_HOST", "0.0.0.0").strip(),
        mcp_port=int(os.environ.get("MCP_PORT", "8765")),
        mcp_bearer_token=token,
        data_dir=data_dir,
    )
