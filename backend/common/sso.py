"""
SSO introspect client.

Validates session-id cookies against the configured SSO provider's
`/introspect` endpoint (see `SSO_AUTH_ORIGIN` in config).

Caching strategy:
- Successful introspections are cached for `cache_ttl` seconds.
- If the auth service is unreachable and a stale cache entry exists, it is
  served for an additional `stale_grace_ttl` seconds so that brief outages do
  not log everyone out. A sid that legitimately expires is still rejected by
  the auth service on the next refresh, so the only risk is a ≤30s+grace
  window after a logout — an acceptable tradeoff for internal systems.
"""
import time
from dataclasses import dataclass
from typing import Optional

import aiohttp

from core.config import env_config
from common.logger import logger


@dataclass(frozen=True)
class SSOUser:
    sub: str
    email: str
    exp: int
    username: str = ""


class SSOError(Exception):
    """Raised when introspection cannot determine a verdict (auth service down
    with no usable cache). Callers should surface this as 503, not 401."""


_sso_conf = env_config.sso_config

# sid -> (user | None, cached_at, is_stale_allowed_until)
#   user = None means a cached negative result (still inside cache_ttl)
_cache: dict[str, tuple[Optional[SSOUser], float, float]] = {}


def _now() -> float:
    return time.time()


async def introspect(sid: str) -> Optional[SSOUser]:
    """Validate a sid with the auth service.

    Returns the user on success, None if the sid is explicitly invalid.
    Raises SSOError if the auth service is unreachable and no usable cache
    entry exists.
    """
    if not sid:
        return None

    now = _now()
    cached = _cache.get(sid)
    if cached is not None and now - cached[1] < _sso_conf['cache_ttl']:
        return cached[0]

    try:
        result = await _call_introspect(sid)
    except Exception as e:
        # Fall back to a stale-but-recent positive result if we have one.
        if cached is not None and cached[0] is not None and now < cached[2]:
            logger.warning(f"[SSO] introspect failed ({e}); serving stale cache for sid={sid[:6]}…")
            return cached[0]
        logger.error(f"[SSO] introspect failed with no cache fallback: {e}")
        raise SSOError(str(e)) from e

    if result.get('valid'):
        user = SSOUser(
            sub=result['sub'],
            email=result['email'],
            exp=int(result['exp']),
            username=result.get('username', ''),
        )
        _cache[sid] = (user, now, now + _sso_conf['cache_ttl'] + _sso_conf['stale_grace_ttl'])
        return user

    # Explicit negative response: cache briefly so a tight retry loop doesn't hammer auth.
    _cache[sid] = (None, now, now)
    reason = result.get('reason', 'unknown')
    logger.debug(f"[SSO] sid rejected: {reason}")
    return None


async def _call_introspect(sid: str) -> dict:
    url = f"{_sso_conf['auth_origin']}/introspect"
    timeout = aiohttp.ClientTimeout(total=_sso_conf['request_timeout'])
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.post(url, json={"sid": sid}) as r:
            r.raise_for_status()
            return await r.json()


def invalidate(sid: str) -> None:
    """Drop a sid from cache (e.g., after a 401 downstream)."""
    _cache.pop(sid, None)


def build_login_url(return_to: str) -> str:
    from urllib.parse import quote
    return f"{_sso_conf['auth_origin']}/login?redirect={quote(return_to, safe='')}"


def build_logout_url() -> str:
    return f"{_sso_conf['auth_origin']}/logout"
