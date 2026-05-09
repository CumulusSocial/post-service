from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import httpx
from jose import JWTError, jwt

from post_service.config import settings


@dataclass
class JWKSCache:
    keys: dict[str, dict] = field(default_factory=dict)
    fetched_at: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_cache = JWKSCache()


async def _refresh_if_needed(client: httpx.AsyncClient) -> None:
    if time.time() - _cache.fetched_at < settings.jwks_refresh_seconds and _cache.keys:
        return
    async with _cache.lock:
        if time.time() - _cache.fetched_at < settings.jwks_refresh_seconds and _cache.keys:
            return
        url = f"{settings.auth_base_url.rstrip('/')}/.well-known/jwks.json"
        resp = await client.get(url, timeout=5.0)
        resp.raise_for_status()
        body = resp.json()
        _cache.keys = {k["kid"]: k for k in body.get("keys", [])}
        _cache.fetched_at = time.time()


async def verify(token: str, *, client: httpx.AsyncClient) -> dict:
    await _refresh_if_needed(client)
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as e:
        raise ValueError("malformed token") from e
    kid = header.get("kid")
    if kid is None or kid not in _cache.keys:
        # one forced refresh in case Auth rotated keys
        _cache.fetched_at = 0.0
        await _refresh_if_needed(client)
    if kid not in _cache.keys:
        raise ValueError("unknown signing key")
    try:
        return jwt.decode(
            token,
            _cache.keys[kid],
            algorithms=["RS256"],
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub"]},
        )
    except JWTError as e:
        raise ValueError(f"invalid token: {e}") from e


def reset_cache_for_tests() -> None:
    _cache.keys = {}
    _cache.fetched_at = 0.0
