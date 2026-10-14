"""JSON backups of picture settings under DATA_DIR/backups/."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class BackupError(ValueError):
    pass


def _safe(name: str) -> str:
    if not _SAFE_NAME.match(name):
        raise BackupError(
            f"invalid backup name {name!r}; use 1-64 chars [A-Za-z0-9._-]"
        )
    return name


def auto_backup_path(backups_dir: Path, ts: datetime | None = None) -> Path:
    when = ts or datetime.now(timezone.utc)
    stamp = when.strftime("%Y%m%dT%H%M%SZ")
    return backups_dir / f"auto-{stamp}.json"


def write_backup(
    backups_dir: Path,
    settings: dict[str, Any],
    *,
    name: str | None = None,
    category: str = "picture",
    meta: dict[str, Any] | None = None,
) -> Path:
    backups_dir.mkdir(parents=True, exist_ok=True)
    if name is None:
        path = auto_backup_path(backups_dir)
        label = path.stem
    else:
        label = _safe(name)
        path = backups_dir / f"{label}.json"

    payload = {
        "name": label,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "settings": settings,
    }
    if meta:
        payload["meta"] = meta

    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_backup(backups_dir: Path, name: str) -> dict[str, Any]:
    label = _safe(name)
    path = backups_dir / f"{label}.json"
    if not path.is_file():
        # also allow passing stem that already includes auto- prefix without .json
        alt = backups_dir / name
        if alt.suffix != ".json":
            alt = backups_dir / f"{name}.json"
        if not alt.is_file():
            raise BackupError(f"backup not found: {name}")
        path = alt
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "settings" not in data:
        raise BackupError(f"invalid backup file: {path.name}")
    return data


def list_backups(backups_dir: Path) -> list[dict[str, Any]]:
    if not backups_dir.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(backups_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items.append(
                {
                    "name": data.get("name", path.stem),
                    "file": path.name,
                    "timestamp": data.get("timestamp"),
                    "category": data.get("category"),
                    "keys": sorted((data.get("settings") or {}).keys()),
                }
            )
        except (OSError, json.JSONDecodeError):
            items.append({"name": path.stem, "file": path.name, "error": "unreadable"})
    return items
