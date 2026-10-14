"""Lazy WebOsClient connection helpers."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from bscpylgtv import WebOsClient
from bscpylgtv.exceptions import PyLGTVPairException

from lgtv_mcp.config import Config
from lgtv_mcp.manifest import (
    DEFAULT_CLIENT_STATES,
    apply_extra_permissions,
    resolve_manifest_path,
)

CONNECT_TIMEOUT_S = 10.0


class TVError(RuntimeError):
    """User-facing TV connection / command error."""


def _map_connect_error(exc: BaseException) -> TVError:
    text = str(exc).lower()
    if isinstance(exc, PyLGTVPairException) or "pair" in text:
        return TVError("not paired, run pairing")
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, OSError, ConnectionError)):
        return TVError("TV unreachable or off")
    if "timeout" in text or "connect" in text or "refused" in text:
        return TVError("TV unreachable or off")
    return TVError(f"TV error: {exc}")


def picture_category(
    category: str = "picture",
    *,
    pic_mode: str | None = None,
    tv_input: str | None = None,
) -> str:
    """Build getSystemSettings category; input/mode uses bscpylgtv set_picture_settings form."""
    if pic_mode is not None and tv_input is not None:
        return f"{category}${tv_input}.{pic_mode}.2d.x"
    return category


async def create_client(config: Config) -> WebOsClient:
    config.ensure_dirs()
    client = await WebOsClient.create(
        config.lgtv_host,
        key_file_path=str(config.key_file_path),
        manifest_file_path=str(resolve_manifest_path()),
        states=list(DEFAULT_CLIENT_STATES),
    )
    apply_extra_permissions(client.manifest)
    return client


async def is_paired(config: Config) -> bool:
    try:
        client = await create_client(config)
        return bool(client.is_registered())
    except Exception:
        return False


@asynccontextmanager
async def connected_client(config: Config) -> AsyncIterator[WebOsClient]:
    """Yield a connected WebOsClient; disconnect on exit.

    Raises TVError with clear messages on failure.
    """
    try:
        client = await create_client(config)
    except Exception as exc:
        raise _map_connect_error(exc) from exc

    if not client.is_registered():
        # First connect can still pair interactively; for MCP tools require prior pair.
        # Still attempt connect so pair CLI works; tools check separately if needed.
        pass

    try:
        await asyncio.wait_for(client.connect(), timeout=CONNECT_TIMEOUT_S)
    except Exception as exc:
        if not client.is_registered():
            raise TVError("not paired, run pairing") from exc
        raise _map_connect_error(exc) from exc

    try:
        yield client
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


def extract_settings(raw: Any) -> dict[str, Any]:
    """Normalize get_system_settings response into a flat settings dict."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        if isinstance(raw.get("settings"), dict):
            return dict(raw["settings"])
        # Some paths return settings directly
        return {k: v for k, v in raw.items() if k not in {"category", "returnValue"}}
    return {}


def _is_batch_key_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "not allowed" in text or "no matched result" in text


async def _read_keys_one_by_one(
    client: WebOsClient,
    keys: list[str],
    category: str,
) -> tuple[dict[str, Any], list[str], dict[str, str]]:
    found: dict[str, Any] = {}
    missing: list[str] = []
    rejected: dict[str, str] = {}
    for key in keys:
        try:
            raw = await client.get_system_settings(category, [key])
            extracted = extract_settings(raw)
            if key in extracted:
                found[key] = extracted[key]
            else:
                missing.append(key)
        except Exception as exc:
            rejected[key] = str(exc)
    return found, missing, rejected


async def read_settings(
    client: WebOsClient,
    keys: list[str],
    category: str = "picture",
    *,
    pic_mode: str | None = None,
    tv_input: str | None = None,
) -> tuple[dict[str, Any], list[str], dict[str, str]]:
    """Return (found, missing, rejected) for the requested keys.

    On batch failure with "not allowed" / "no matched result", reads each key
    separately so refused keys land in rejected instead of failing the whole call.
    """
    cat = picture_category(category, pic_mode=pic_mode, tv_input=tv_input)
    try:
        raw = await client.get_system_settings(cat, keys)
    except Exception as exc:
        if _is_batch_key_error(exc):
            return await _read_keys_one_by_one(client, keys, cat)
        raise

    found_all = extract_settings(raw)
    present = {k: found_all[k] for k in keys if k in found_all}
    missing = [k for k in keys if k not in present]
    return present, missing, {}
