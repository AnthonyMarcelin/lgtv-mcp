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


async def read_settings(
    client: WebOsClient,
    keys: list[str],
    category: str = "picture",
) -> tuple[dict[str, Any], list[str]]:
    """Return (found, missing) for the requested keys."""
    raw = await client.get_system_settings(category, keys)
    found = extract_settings(raw)
    # Only keep requested keys that the TV actually returned
    present = {k: found[k] for k in keys if k in found}
    missing = [k for k in keys if k not in present]
    return present, missing
