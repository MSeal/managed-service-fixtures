import aioredis
from managed_service_fixtures import RedisDetails


async def test_redis(managed_redis: RedisDetails):
    redis = await aioredis.from_url(managed_redis.url)
    await redis.set("foo", "bar")

    value = await redis.get("foo")
    assert value == b"bar"
