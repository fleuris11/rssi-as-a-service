import time

import pytest

from apps.threat_intelligence.throttle import RedisTokenBucketThrottle, ThrottleTimeoutError

# Tiny/fast-refilling bucket, dedicated key — exercises the exact same
# Lua-script logic as the real 1 req/s / bursts-of-5 licence limit, in
# well under a second, and never collides with the module-level
# BUCKET_KEY (cleaned separately by the autouse fixture).
_TEST_KEY = "breachsense:throttle:test-bucket"


def _throttle(*, capacity=2, refill_rate=20.0):
    return RedisTokenBucketThrottle(
        bucket_key=_TEST_KEY, capacity=capacity, refill_rate_per_second=refill_rate
    )


@pytest.fixture(autouse=True)
def _clean_test_bucket():
    from apps.threat_intelligence.throttle import get_redis_client

    get_redis_client().delete(_TEST_KEY)
    yield
    get_redis_client().delete(_TEST_KEY)


class TestRedisTokenBucketThrottle:
    def test_burst_capacity_is_immediately_available(self):
        throttle = _throttle(capacity=5, refill_rate=0.001)
        started = time.monotonic()
        for _ in range(5):
            throttle.acquire(timeout=1)
        elapsed = time.monotonic() - started
        assert elapsed < 0.5

    def test_exceeding_burst_blocks_until_refill(self):
        throttle = _throttle(capacity=2, refill_rate=20.0)  # refill: 1 token/50ms
        throttle.acquire(timeout=1)
        throttle.acquire(timeout=1)  # burst exhausted

        started = time.monotonic()
        throttle.acquire(timeout=2)  # must wait for a refill
        elapsed = time.monotonic() - started

        assert elapsed >= 0.03  # some real wait happened, not an instant grant

    def test_raises_on_timeout_when_no_token_available(self):
        throttle = _throttle(capacity=1, refill_rate=0.001)  # effectively no refill within timeout
        throttle.acquire(timeout=1)  # consume the only token

        with pytest.raises(ThrottleTimeoutError):
            throttle.acquire(timeout=0.3)

    def test_serializes_concurrent_callers_no_double_grant(self):
        """The property that actually matters (ADR-013): under concurrency,
        the number of successful acquires never exceeds what the bucket
        capacity + refill during the window allows — two callers can never
        both be granted the same last token."""
        import threading

        throttle = _throttle(capacity=3, refill_rate=0.001)
        granted = []
        lock = threading.Lock()

        def worker():
            try:
                throttle.acquire(timeout=0.5)
                with lock:
                    granted.append(1)
            except ThrottleTimeoutError:
                pass

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(granted) == 3
