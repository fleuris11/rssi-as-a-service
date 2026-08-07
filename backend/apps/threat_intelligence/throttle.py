"""Redis token-bucket throttle serializing every outbound call to
Breachsense at 1 req/s (bursts of 5) — ADR-013: the licence is a single,
platform-wide resource, so the bucket key is global (not per-tenant), and
must be safe under concurrent Celery workers on the ``monitoring`` queue.

The bucket state (tokens, last-refill timestamp) lives entirely inside a
single Lua script executed atomically by Redis (``EVAL``) — this is what
makes it safe under concurrency: two workers racing to acquire a token
can't both observe "1 token left" and both take it, the way a
read-then-write in Python would allow.
"""

import time

import redis
from django.conf import settings

BUCKET_KEY = "breachsense:throttle:bucket"
CAPACITY = 5
REFILL_RATE_PER_SECOND = 1.0
DEFAULT_ACQUIRE_TIMEOUT_SECONDS = 30
POLL_INTERVAL_SECONDS = 0.2

_TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local bucket = redis.call("HMGET", key, "tokens", "timestamp")
local tokens = tonumber(bucket[1])
local timestamp = tonumber(bucket[2])

if tokens == nil then
  tokens = capacity
  timestamp = now
end

local delta = now - timestamp
if delta < 0 then delta = 0 end
tokens = math.min(capacity, tokens + delta * refill_rate)

local allowed = 0
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
end

redis.call("HMSET", key, "tokens", tokens, "timestamp", now)
redis.call("EXPIRE", key, 60)

return {allowed, tostring(tokens)}
"""


class ThrottleTimeoutError(Exception):
    """Raised when no token became available within the acquire timeout —
    the caller (BreachsenseClient) should surface this as a network-level
    failure, not silently proceed unthrottled."""


_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            settings.BREACHSENSE_THROTTLE_REDIS_URL, decode_responses=True
        )
    return _redis_client


class RedisTokenBucketThrottle:
    """One instance is enough for the whole process — state lives in
    Redis, not in this object. Constructed per-call in practice (cheap,
    stateless wrapper) so tests can swap the Redis client easily.

    ``bucket_key``/``capacity``/``refill_rate_per_second`` default to the
    real licence limits but are overridable — tests use a dedicated key and
    a tiny/fast-refilling bucket so the *same* blocking logic that
    protects the real licence can be exercised in well under a second
    instead of waiting out a real 1 req/s rate.
    """

    def __init__(
        self,
        client: redis.Redis | None = None,
        *,
        bucket_key: str = BUCKET_KEY,
        capacity: int = CAPACITY,
        refill_rate_per_second: float = REFILL_RATE_PER_SECOND,
    ):
        self._client = client or get_redis_client()
        self._script = self._client.register_script(_TOKEN_BUCKET_SCRIPT)
        self._bucket_key = bucket_key
        self._capacity = capacity
        self._refill_rate = refill_rate_per_second

    def _try_acquire(self) -> bool:
        allowed, _tokens = self._script(
            keys=[self._bucket_key], args=[self._capacity, self._refill_rate, time.time()]
        )
        return bool(int(allowed))

    def acquire(self, *, timeout: float = DEFAULT_ACQUIRE_TIMEOUT_SECONDS) -> None:
        """Blocks until a token is available. Raises ThrottleTimeoutError
        if none becomes available within ``timeout`` seconds — this should
        only happen under a genuine incident (Redis down, or an
        unreasonable pile-up of concurrent callers), never in normal
        operation at the licence's own 1 req/s rate."""
        deadline = time.monotonic() + timeout
        while True:
            if self._try_acquire():
                return
            if time.monotonic() >= deadline:
                raise ThrottleTimeoutError(
                    f"Aucun jeton Breachsense disponible après {timeout}s "
                    "(licence limitée à 1 req/s, bursts de 5)."
                )
            time.sleep(POLL_INTERVAL_SECONDS)
