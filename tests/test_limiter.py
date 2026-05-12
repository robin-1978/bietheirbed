from __future__ import annotations

import pytest

from pc_assistant.harness.limiter import RateLimiter


class TestRateLimiter:
    def test_allows_under_limit(self):
        limiter = RateLimiter(max_calls=5, window_seconds=60)
        for _ in range(5):
            assert limiter.is_allowed("test") is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter(max_calls=3, window_seconds=60)
        for _ in range(3):
            limiter.is_allowed("test")
        assert limiter.is_allowed("test") is False

    def test_remaining(self):
        limiter = RateLimiter(max_calls=5, window_seconds=60)
        limiter.is_allowed("test")
        assert limiter.remaining("test") == 4

    def test_different_keys_independent(self):
        limiter = RateLimiter(max_calls=1, window_seconds=60)
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key2") is True

    def test_reset_specific_key(self):
        limiter = RateLimiter(max_calls=1, window_seconds=60)
        limiter.is_allowed("test")
        limiter.reset("test")
        assert limiter.is_allowed("test") is True

    def test_reset_all(self):
        limiter = RateLimiter(max_calls=1, window_seconds=60)
        limiter.is_allowed("a")
        limiter.is_allowed("b")
        limiter.reset()
        assert limiter.is_allowed("a") is True
        assert limiter.is_allowed("b") is True
