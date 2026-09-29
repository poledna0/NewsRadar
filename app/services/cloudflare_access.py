import asyncio
import json
import re
import time

import httpx
import jwt

from app.config import get_settings

_jwks_cache: tuple[float, list[dict]] | None = None
_jwks_lock = asyncio.Lock()


async def verify_access_token(token: str) -> bool:
    """Verify a Cloudflare Access assertion locally against its cached signing keys."""
    settings = get_settings()
    team = (settings.cf_access_team_domain or "").strip().lower()
    audience = (settings.cf_access_audience or "").strip()
    if not team or not audience or not re.fullmatch(r"[a-z0-9.-]+", team):
        return False

    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        return False
    key_id = header.get("kid")
    if not key_id or header.get("alg") != "RS256":
        return False

    keys = await _get_signing_keys(team)
    key_data = next((key for key in keys if key.get("kid") == key_id), None)
    if key_data is None:
        _invalidate_keys()
        keys = await _get_signing_keys(team, force=True)
        key_data = next((key for key in keys if key.get("kid") == key_id), None)
    if key_data is None:
        return False

    signing_key = jwt.PyJWK.from_dict(key_data, algorithm="RS256").key
    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=f"https://{team}",
            options={"require": ["exp", "iss", "aud"]},
        )
    except jwt.InvalidTokenError:
        return False
    return bool(claims.get("email"))


async def _get_signing_keys(team: str, force: bool = False) -> list[dict]:
    global _jwks_cache
    now = time.monotonic()
    if not force and _jwks_cache and now - _jwks_cache[0] < 900:
        return _jwks_cache[1]
    async with _jwks_lock:
        now = time.monotonic()
        if not force and _jwks_cache and now - _jwks_cache[0] < 900:
            return _jwks_cache[1]
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            response = await client.get(f"https://{team}/cdn-cgi/access/certs")
            response.raise_for_status()
            keys = response.json().get("keys", [])
        if not keys:
            raise ValueError("Cloudflare Access returned no signing keys")
        _jwks_cache = (now, keys)
        return keys


def _invalidate_keys() -> None:
    global _jwks_cache
    _jwks_cache = None
