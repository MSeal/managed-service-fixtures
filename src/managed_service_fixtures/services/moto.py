from typing import Callable, Tuple

import mirakuru
import pytest

from managed_service_fixtures.base_manager import (
    ExternalServiceLifecycleManager,
    ServiceDetails,
)


class MotoDetails(ServiceDetails):
    hostname: str = "localhost"
    port: int = 5000

    @property
    def url(self):
        return f"http://{self.hostname}:{self.port}"


class MotoServiceManager(ExternalServiceLifecycleManager):
    """
    Start a dev-mode Vault server or read connection details from a filepath defined
    by a TEST_VAULT_DETAILS environment variable.

    If this manages the Vault server, the root token id is `root`.

    `pip install moto[server]` will install moto_server CLI.
    """

    env_file_pointer = "TEST_MOTO_DETAILS"
    json_state_file_name = "moto.json"
    service_details_class = MotoDetails

    def _start_service(self) -> Tuple[MotoDetails, mirakuru.Executor]:
        hostname = "localhost"
        port = self.unused_tcp_port_factory()
        details = MotoDetails(hostname=hostname, port=port)

        moto_cmd = f"moto_server --host {hostname} --port {port} s3"
        process = mirakuru.TCPExecutor(moto_cmd, host=hostname, port=int(port))
        process.start()
        assert process.running()
        return details, process


@pytest.fixture(scope="session")
def managed_moto(
    worker_id: str,
    tmp_path_factory: pytest.TempPathFactory,
    unused_tcp_port_factory: Callable[[], int],
) -> MotoDetails:
    """
    Yields connection details for a Moto server.

    boto3 connection example:
     - client = boto3.client('s3', endpoint_url=moto_details.url)
    """
    with MotoServiceManager(
        worker_id=worker_id,
        tmp_path_factory=tmp_path_factory,
        unused_tcp_port_factory=unused_tcp_port_factory,
    ) as moto_details:
        yield moto_details
