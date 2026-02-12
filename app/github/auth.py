import time
from functools import lru_cache

import httpx
import jwt

from app.config import get_settings

# Cache installation tokens (valid for 1 hour, we refresh at 50 min)
_token_cache: dict[int, tuple[str, float]] = {}
TOKEN_TTL = 50 * 60  # refresh 10 min before expiry


def generate_jwt() -> str:
    """Generate a short-lived JWT for GitHub App authentication."""
    settings = get_settings()
    now = int(time.time())
    payload = {
        "iat": now - 60,  # account for clock skew
        "exp": now + 600,  # 10-minute max per GitHub spec
        "iss": settings.github_app_id,
    }
    private_key = settings.get_private_key_bytes()
    return jwt.encode(payload, private_key, algorithm="RS256")


async def get_installation_token(installation_id: int) -> str:
    """Exchange a JWT for an installation access token, with caching."""
    now = time.time()

    if installation_id in _token_cache:
        token, expires_at = _token_cache[installation_id]
        if now < expires_at:
            return token

    jwt_token = generate_jwt()
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers)
        resp.raise_for_status()

    token = resp.json()["token"]
    _token_cache[installation_id] = (token, now + TOKEN_TTL)
    return token
