import time
from collections import defaultdict

from fastapi import HTTPException, Request


class RateLimiter:
    """Simple in-memory rate limiter using a sliding window counter.

    Tracks requests per installation ID (extracted from webhook payload).
    Falls back to IP-based limiting if no installation ID is available.
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _clean_window(self, key: str) -> None:
        cutoff = time.time() - self.window_seconds
        self._requests[key] = [
            ts for ts in self._requests[key] if ts > cutoff
        ]

    def check(self, key: str) -> bool:
        """Return True if request is allowed, False if rate limited."""
        self._clean_window(key)
        if len(self._requests[key]) >= self.max_requests:
            return False
        self._requests[key].append(time.time())
        return True

    def remaining(self, key: str) -> int:
        """Return the number of remaining requests in the current window."""
        self._clean_window(key)
        return max(0, self.max_requests - len(self._requests[key]))

    def reset_time(self, key: str) -> float:
        """Return seconds until the oldest request expires from the window."""
        self._clean_window(key)
        if not self._requests[key]:
            return 0.0
        return max(0.0, self._requests[key][0] + self.window_seconds - time.time())


# Global instance
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)


async def check_rate_limit(request: Request) -> None:
    """FastAPI dependency that enforces rate limiting per client IP."""
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.check(client_ip):
        seconds_left = rate_limiter.reset_time(client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limited. Try again in {seconds_left:.0f} seconds.",
            headers={"Retry-After": str(int(seconds_left))},
        )
