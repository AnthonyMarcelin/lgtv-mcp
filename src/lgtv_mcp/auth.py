"""Bearer token verification (constant-time, never logged)."""

from __future__ import annotations

import hashlib
import hmac

from mcp.server.auth.provider import AccessToken


def tokens_equal(provided: str, expected: str) -> bool:
    """Constant-time equality via SHA-256 digests (length-safe)."""
    a = hashlib.sha256(provided.encode("utf-8")).digest()
    b = hashlib.sha256(expected.encode("utf-8")).digest()
    return hmac.compare_digest(a, b)


class StaticBearerVerifier:
    """TokenVerifier that accepts a single static bearer token."""

    def __init__(self, expected_token: str) -> None:
        self._expected = expected_token

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or not tokens_equal(token, self._expected):
            return None
        return AccessToken(
            token="ok",
            client_id="lgtv-mcp",
            scopes=[],
        )
