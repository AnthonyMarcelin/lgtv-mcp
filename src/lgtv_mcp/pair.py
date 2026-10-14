"""CLI pairing: python -m lgtv_mcp.pair

Diagnostic raw websocket flow (bscpylgtv 0.5.5 hides the TV reply on
non-registered 2nd messages). Never prints the client key.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import ssl
import sys
from typing import Any

import websockets
from websockets.exceptions import InvalidHandshake, InvalidURI, WebSocketException

from lgtv_mcp.config import load_config
from lgtv_mcp.tv import create_client

PAIR_TIMEOUT_S = 90.0
WS_OPEN_TIMEOUT_S = 10.0
ERROR_HINT = (
    "TV refused (403 often means a previous prompt was denied or still open: "
    "close any dialog on the TV, then retry)"
)


def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def build_register_msg(client: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "forcePairing": False,
        "pairingType": "PROMPT",
        "manifest": client.manifest,
    }
    if client.client_key:
        payload["client-key"] = client.client_key
    return {"type": "register", "id": "register_0", "payload": payload}


def summarize_tv_message(msg: dict[str, Any]) -> str:
    payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
    return (
        f"tv: type={msg.get('type')!s} id={msg.get('id')!s} "
        f"pairingType={payload.get('pairingType')!s} error={payload.get('error')!s}"
    )


async def clear_stored_key(client: Any, host: str) -> None:
    """Clear pairing key in memory and storage when possible."""
    client.client_key = None
    storage = getattr(client, "storage", None)
    if storage is None:
        return
    db = getattr(storage, "db", None)
    if db is not None and host in db:
        del db[host]
        db.commit()
        return
    # StorageProto has no delete; set_key ignores None. Proceed without key.


async def open_tv_websocket(host: str) -> tuple[Any, str]:
    """Prefer wss://host:3001, fall back to ws://host:3000."""
    wss_url = f"wss://{host}:3001"
    ws_url = f"ws://{host}:3000"
    try:
        ws = await websockets.connect(
            wss_url,
            ssl=_ssl_ctx(),
            ping_interval=None,
            max_size=None,
            open_timeout=WS_OPEN_TIMEOUT_S,
        )
        print(f"using {wss_url}")
        return ws, wss_url
    except (OSError, asyncio.TimeoutError, InvalidHandshake, InvalidURI, WebSocketException) as exc:
        print(f"wss failed ({exc!s}), trying {ws_url}")
        ws = await websockets.connect(
            ws_url,
            ping_interval=None,
            max_size=None,
            open_timeout=WS_OPEN_TIMEOUT_S,
        )
        print(f"using {ws_url}")
        return ws, ws_url


async def run_pairing_session(
    ws: Any,
    client: Any,
    host: str,
    *,
    timeout_s: float = PAIR_TIMEOUT_S,
) -> int:
    """Send register and process TV messages until registered, error, or timeout."""
    await ws.send(json.dumps(build_register_msg(client)))
    deadline = asyncio.get_running_loop().time() + timeout_s
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            print("error: timed out waiting for pairing", file=sys.stderr)
            return 1
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        except asyncio.TimeoutError:
            print("error: timed out waiting for pairing", file=sys.stderr)
            return 1

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            print("tv: type=None id=None pairingType=None error=non-json", file=sys.stderr)
            continue
        if not isinstance(msg, dict):
            print("tv: type=None id=None pairingType=None error=non-object", file=sys.stderr)
            continue

        print(summarize_tv_message(msg))
        msg_type = msg.get("type")
        payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}

        if msg_type == "registered":
            key = payload.get("client-key")
            if not key:
                print("error: registered without client-key", file=sys.stderr)
                return 1
            await client.storage.set_key(host, key)
            client.client_key = key
            print("paired")
            return 0

        if msg_type == "error":
            print(f"error: {payload.get('error', msg)!s}", file=sys.stderr)
            print(ERROR_HINT, file=sys.stderr)
            return 1


async def _pair(*, force: bool = False) -> int:
    try:
        config = load_config()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    config.ensure_dirs()
    host = config.lgtv_host
    client = await create_client(config)

    if client.client_key and not force:
        print("already paired")
        return 0

    if client.client_key and force:
        await clear_stored_key(client, host)

    ws = None
    try:
        ws, _url = await open_tv_websocket(host)
        return await run_pairing_session(ws, client, host, timeout_s=PAIR_TIMEOUT_S)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Pair with an LG webOS TV")
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-pair even if a client key is already stored",
    )
    args = parser.parse_args(argv)
    raise SystemExit(asyncio.run(_pair(force=args.force)))


if __name__ == "__main__":
    main()
