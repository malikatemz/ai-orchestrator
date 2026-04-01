import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from fastapi import Request, HTTPException, status


class RateLimitStorage(ABC):
    """Abstract interface for rate limit storage backends."""
    @abstractmethod
    def get_timestamps(self, key: str) -> deque[float]:
        pass

    @abstractmethod
    def add_timestamp(self, key: str, timestamp: float):
        pass

    @abstractmethod
    def clean_old(self, key: str, window_start: float):
        pass


class InMemoryRateLimitStorage(RateLimitStorage):
    """In-memory implementation using deque for efficient sliding window."""
    def __init__(self):
        self._client_requests: dict[str, deque[float]] = defaultdict(deque)

    def get_timestamps(self, key: str) -> deque[float]:
        return self._client_requests[key]

    def add_timestamp(self, key: str, timestamp: float):
        self._client_requests[key].append(timestamp)

    def clean_old(self, key: str, window_start: float):
        timestamps = self._client_requests[key]
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()


class RateLimiter:
    """Rate limiter using sliding window algorithm."""
    def __init__(self, storage: RateLimitStorage, requests: int = 60, window_seconds: int = 60):
        self.storage = storage
        self.requests = requests
        self.window_seconds = window_seconds

    def is_rate_limited(self, key: str) -> bool:
        """Check if the key is rate limited."""
        now = time.time()
        window_start = now - self.window_seconds
        self.storage.clean_old(key, window_start)
        timestamps = self.storage.get_timestamps(key)
        return len(timestamps) >= self.requests

    def record_request(self, key: str):
        """Record a request for the key."""
        now = time.time()
        self.storage.add_timestamp(key, now)


# Global instance for MVP; inject via DI in production
_storage = InMemoryRateLimitStorage()
_limiter = RateLimiter(_storage)


def maybe_rate_limit(request: Request):
    """Middleware function to enforce rate limiting."""
    key = request.client.host if request.client else "unknown"
    if _limiter.is_rate_limited(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({_limiter.requests}/{_limiter.window_seconds}s)",
        )
    _limiter.record_request(key)
