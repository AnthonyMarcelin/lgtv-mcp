"""CLI pairing: python -m lgtv_mcp.pair

Connects to the TV (60s timeout while the user accepts the prompt).
Prints only "paired" or an error. Never prints the client key.
"""

from __future__ import annotations

import asyncio
import sys

from lgtv_mcp.config import load_config
from lgtv_mcp.tv import create_client


PAIR_TIMEOUT_S = 60.0


async def _pair() -> int:
    try:
        config = load_config()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    config.ensure_dirs()
    client = None
    try:
        client = await create_client(config)
        await asyncio.wait_for(client.connect(), timeout=PAIR_TIMEOUT_S)
        if not client.is_registered():
            print("error: pairing failed", file=sys.stderr)
            return 1
        print("paired")
        return 0
    except asyncio.TimeoutError:
        print(
            "error: timed out waiting for pairing (accept the prompt on the TV)",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass


def main() -> None:
    raise SystemExit(asyncio.run(_pair()))


if __name__ == "__main__":
    main()
