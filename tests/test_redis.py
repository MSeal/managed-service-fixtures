import redis.asyncio as aioredis
import pytest

from managed_service_fixtures import RedisDetails


@pytest.fixture
async def redis_client(managed_redis: RedisDetails) -> aioredis.Redis:
    # Put this in a fixture to handle teardown, otherwise will sometimes see
    # "task destroyed but is still pending!" warnings, especially when running in parallel
    redis = await aioredis.from_url(managed_redis.url)
    yield redis
    await redis.close()


async def test_redis(redis_client: aioredis.Redis):
    await redis_client.set("foo", "bar")

    value = await redis_client.get("foo")
    assert value == b"bar"
