from collections import deque

import pytest
from fastapi import HTTPException

from app.rate_limiter import InMemoryRateLimitStorage, RateLimiter, maybe_rate_limit


class DummyClient:
    def __init__(self, host: str):
        self.host = host


class DummyRequest:
    def __init__(self, host: str = "127.0.0.1"):
        self.client = DummyClient(host)


class TestInMemoryRateLimiter:
    def test_it_records_and_reads_request_timestamps(self):
        storage = InMemoryRateLimitStorage()
        storage.add_timestamp("client-1", 10.0)

        assert list(storage.get_timestamps("client-1")) == [10.0]

    def test_it_cleans_expired_timestamps(self):
        storage = InMemoryRateLimitStorage()
        storage._client_requests["client-1"] = deque([1.0, 4.0, 8.0])

        storage.clean_old("client-1", 5.0)

        assert list(storage.get_timestamps("client-1")) == [8.0]

    def test_it_flags_requests_above_the_boundary(self, monkeypatch):
        storage = InMemoryRateLimitStorage()
        limiter = RateLimiter(storage=storage, requests=2, window_seconds=60)
        monkeypatch.setattr("app.rate_limiter.time.time", lambda: 100.0)

        limiter.record_request("client-1")
        limiter.record_request("client-1")

        assert limiter.is_rate_limited("client-1") is True


class TestMaybeRateLimit:
    def test_it_raises_http_429_when_global_limiter_is_exhausted(self, monkeypatch):
        class ExhaustedLimiter:
            requests = 60
            window_seconds = 60

            @staticmethod
            def is_rate_limited(key: str) -> bool:
                return True

            @staticmethod
            def record_request(key: str) -> None:
                raise AssertionError("record_request should not run when already rate limited")

        monkeypatch.setattr("app.rate_limiter._limiter", ExhaustedLimiter())

        with pytest.raises(HTTPException) as exc:
            maybe_rate_limit(DummyRequest())

        assert exc.value.status_code == 429

    def test_it_records_requests_when_under_the_limit(self, monkeypatch):
        captured = []

        class HealthyLimiter:
            requests = 60
            window_seconds = 60

            @staticmethod
            def is_rate_limited(key: str) -> bool:
                return False

            @staticmethod
            def record_request(key: str) -> None:
                captured.append(key)

        monkeypatch.setattr("app.rate_limiter._limiter", HealthyLimiter())

        maybe_rate_limit(DummyRequest("10.0.0.8"))

        assert captured == ["10.0.0.8"]
