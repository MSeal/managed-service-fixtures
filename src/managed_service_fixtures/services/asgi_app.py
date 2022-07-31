import os
from typing import Callable, Tuple

import mirakuru
import pytest
from managed_service_fixtures.base_manager import (
    ExternalServiceLifecycleManager,
    ServiceDetails,
)


class AppDetails(ServiceDetails):
    hostname: str = "localhost"
    port: int = 8000


class AppManager(ExternalServiceLifecycleManager):
    """
    Start a FastAPI app with uvicorn, using a free port.
    To tell uvicorn where your app is located, set an environment variable TEST_APP_LOCATION.
    For instance, if your project has the line entrypoint = FastAPI() in myapp/start.py,
    you would set TEST_APP_LOCATION to "myapp.start:entrypoint".

    The default location to look for the app location is app.main:app.
    Note: all environment variables of the parent process (pytest runner) automatically get pased
    into the child process that mirakuru spawns.
    """

    app_location_pointer: str = "TEST_APP_LOCATION"
    env_file_pointer: str = "TEST_APP_DETAILS"
    json_state_file_name = "asgi.json"
    service_details_class = AppDetails

    def _start_service(self) -> Tuple[AppDetails, mirakuru.Executor]:
        hostname = "localhost"
        port = self.unused_tcp_port_factory()

        details = AppDetails(hostname=hostname, port=port)
        app_location = os.environ.get(self.app_location_pointer, "app.main:app")

        # chdir to avoid heap_profiler/ subdir from littering top of gate tree.
        uvicorn_cmd = f"""uvicorn --host {hostname} --port {port} {app_location}"""
        process = mirakuru.TCPExecutor(
            uvicorn_cmd, host=hostname, port=int(port), shell=True
        )
        process.start()
        assert process.running()
        return details, process


@pytest.fixture(scope="session")
def managed_asgi_app(
    worker_id: str,
    tmp_path_factory: pytest.TempPathFactory,
    unused_tcp_port_factory: Callable[[], int],
) -> AppDetails:
    with AppManager(
        worker_id=worker_id,
        tmp_path_factory=tmp_path_factory,
        unused_tcp_port_factory=unused_tcp_port_factory,
    ) as app_details:
        yield app_details
