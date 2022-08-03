from typing import Callable, Tuple

import mirakuru
import pytest

from managed_service_fixtures.base_manager import (
    ExternalServiceLifecycleManager,
    ServiceDetails,
)


class VaultDetails(ServiceDetails):
    hostname: str = "localhost"
    port: int = 8200
    token: str = "root"

    @property
    def url(self):
        return f"http://{self.hostname}:{self.port}"


class VaultManager(ExternalServiceLifecycleManager):
    """
    Start a dev-mode Vault server or read connection details from a filepath defined
    by a TEST_VAULT_DETAILS environment variable.

    If this manages the Vault server, the root token id is `root`.

    See https://www.vaultproject.io/docs/install for installing Vault.
    """

    env_file_pointer = "TEST_VAULT_DETAILS"
    json_state_file_name = "vault.json"
    service_details_class = VaultDetails

    def _start_service(self) -> Tuple[VaultDetails, mirakuru.Executor]:
        hostname = "localhost"
        port = self.unused_tcp_port_factory()

        details = VaultDetails(hostname=hostname, port=port, token="root")

        vault_cmd = f"vault server -dev -dev-listen-address={hostname}:{port} -dev-root-token-id=root"

        process = mirakuru.TCPExecutor(vault_cmd, host=hostname, port=int(port))
        process.start()
        assert process.running()
        return details, process


@pytest.fixture(scope="session")
def managed_vault(
    worker_id: str,
    tmp_path_factory: pytest.TempPathFactory,
    unused_tcp_port_factory: Callable[[], int],
) -> VaultDetails:
    """
    Yields connection details for a Vault server.

    hvac.py connection example:
     - client = hvac.Client(url=vault_details.url, token=vault_details.token)
    """
    with VaultManager(
        worker_id=worker_id,
        tmp_path_factory=tmp_path_factory,
        unused_tcp_port_factory=unused_tcp_port_factory,
    ) as vault_details:
        yield vault_details
