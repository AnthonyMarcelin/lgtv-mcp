"""Unsigned pairing manifest (comp) and optional extra permissions.

Classic signed manifests are blacklisted on recent LG firmware
("403 Pairing rejected: blacklisted certificate detected").
We ship unsigned manifest_comp.json from bscpylgtv docs instead.

Settings writes use the luna alert trick (createAlert/closeAlert), which
on classic manifests needs WRITE_NOTIFICATION_ALERT; system settings may
need WRITE_SETTINGS. The comp manifest lacks both. Set EXTRA_PERMISSIONS
or LGTV_EXTRA_PERMISSIONS and re-pair with --force to grant them.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Empty by default. Append WRITE_NOTIFICATION_ALERT and/or WRITE_SETTINGS
# when picture/settings writes fail with insufficient permissions.
EXTRA_PERMISSIONS: list[str] = []

PERMISSION_WRITE_HINT = (
    "write refused by TV, permissions missing: "
    "re-pair with LGTV_EXTRA_PERMISSIONS=WRITE_NOTIFICATION_ALERT,WRITE_SETTINGS"
)

# Omit software_info: connect-time fetch often fails with reduced perms.
DEFAULT_CLIENT_STATES: list[str] = [
    "system_info",
    "power",
    "current_app",
    "muted",
    "volume",
    "apps",
    "inputs",
    "sound_output",
    "picture_settings",
]


def packaged_manifest_path() -> Path:
    return Path(__file__).resolve().parent / "manifest_comp.json"


def resolve_manifest_path() -> Path:
    override = os.environ.get("LGTV_MANIFEST_PATH", "").strip()
    if override:
        return Path(override)
    return packaged_manifest_path()


def extra_permissions() -> list[str]:
    """EXTRA_PERMISSIONS plus LGTV_EXTRA_PERMISSIONS (comma-separated)."""
    seen: set[str] = set()
    out: list[str] = []
    raw = os.environ.get("LGTV_EXTRA_PERMISSIONS", "").strip()
    candidates = list(EXTRA_PERMISSIONS)
    if raw:
        candidates.extend(p.strip() for p in raw.split(",") if p.strip())
    for perm in candidates:
        if perm not in seen:
            seen.add(perm)
            out.append(perm)
    return out


def assert_unsigned_manifest(manifest: dict[str, Any]) -> None:
    assert "signed" not in manifest, "manifest must not contain signed payload"
    assert "signatures" not in manifest, "manifest must not contain signatures"


def apply_extra_permissions(manifest: dict[str, Any]) -> dict[str, Any]:
    """Append extra perms in place; assert unsigned. Returns the same dict."""
    assert_unsigned_manifest(manifest)
    perms = list(manifest.get("permissions") or [])
    for perm in extra_permissions():
        if perm not in perms:
            perms.append(perm)
    manifest["permissions"] = perms
    return manifest


def is_permission_denied(exc: BaseException) -> bool:
    text = str(exc).lower()
    return (
        "401" in text
        or "insufficient" in text
        or "permission" in text
        or "unauthorized" in text
        or "not authorized" in text
    )


def write_error_message(exc: BaseException) -> str:
    if is_permission_denied(exc):
        return PERMISSION_WRITE_HINT
    return f"TV command failed: {exc}"
