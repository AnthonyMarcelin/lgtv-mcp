"""Run the lgtv-mcp HTTP server: python -m lgtv_mcp"""

from __future__ import annotations

from lgtv_mcp.config import load_config
from lgtv_mcp.server import create_mcp


def main() -> None:
    config = load_config()
    config.ensure_dirs()
    mcp = create_mcp(config)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
