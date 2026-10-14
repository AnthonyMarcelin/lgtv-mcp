"""HTTP auth: /healthz public, /mcp requires Bearer."""

from __future__ import annotations

from starlette.testclient import TestClient

from lgtv_mcp.auth import tokens_equal
from lgtv_mcp.config import Config
from lgtv_mcp.server import create_app

_MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def test_tokens_equal_constant_time():
    assert tokens_equal("abc", "abc")
    assert not tokens_equal("abc", "abd")
    assert not tokens_equal("short", "much-longer-token")


def test_healthz_unauthenticated(config: Config):
    app = create_app(config)
    with TestClient(app) as client:
        r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_mcp_rejects_without_bearer(config: Config):
    app = create_app(config)
    with TestClient(app) as client:
        r = client.post(
            "/mcp",
            headers=_MCP_HEADERS,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
    assert r.status_code == 401


def test_mcp_rejects_wrong_bearer(config: Config):
    app = create_app(config)
    with TestClient(app) as client:
        r = client.post(
            "/mcp",
            headers={**_MCP_HEADERS, "Authorization": "Bearer wrong-token"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
    assert r.status_code == 401


def test_mcp_accepts_valid_bearer(config: Config, auth_header: dict[str, str]):
    app = create_app(config)
    with TestClient(app) as client:
        r = client.post(
            "/mcp",
            headers={**_MCP_HEADERS, **auth_header},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            },
        )
    assert r.status_code != 401
    assert r.status_code in (200, 202)
