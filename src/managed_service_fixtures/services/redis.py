from typing import Callable, Tuple

import mirakuru
import pytest

from managed_service_fixtures.base_manager import (
    ExternalServiceLifecycleManager,
    ServiceDetails,
)


class RedisDetails(ServiceDetails):
    hostname: str = "localhost"
    port: int = 6379

    @property
    def url(self):
        return f"redis://{self.hostname}:{self.port}"


class RedisServiceManager(ExternalServiceLifecycleManager):
    """
    Start a Redis server or read connection details from a filepath defined
    by a TEST_REDIS_DETAILS environment variable.

    See https://redis.io/topics/quickstart#installing-redis for installing Redis.
    """

    env_file_pointer = "TEST_REDIS_DETAILS"
    json_state_file_name = "redis.json"
    service_details_class = RedisDetails

    def _start_service(self) -> Tuple[RedisDetails, mirakuru.Executor]:
        hostname = "localhost"
        port = self.unused_tcp_port_factory()
        details = RedisDetails(hostname=hostname, port=port)

        redis_cmd = f"redis-server --port {port}"

        process = mirakuru.TCPExecutor(redis_cmd, host=hostname, port=int(port))
        process.start()
        assert process.running()
        return details, process


@pytest.fixture(scope="session")
def managed_redis(
    worker_id: str,
    tmp_path_factory: pytest.TempPathFactory,
    unused_tcp_port_factory: Callable[[], int],
) -> RedisDetails:
    """
    Return a Redis server's connection details for this test session.

    Modes of operation:

    * If env variable TEST_REDIS_DETAILS is set, then it is assumed that it names
    the port number a long-lived instance of Redis is listening on localhost at.

    * Otherwise, a transient service will be created. Currently one per
        each xdist runner, if running under xdist.
    """
    with RedisServiceManager(
        worker_id=worker_id,
        tmp_path_factory=tmp_path_factory,
        unused_tcp_port_factory=unused_tcp_port_factory,
    ) as redis_details:
        yield redis_details
