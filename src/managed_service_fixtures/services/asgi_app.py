from typing import Callable, Optional, Tuple

import mirakuru
import pytest

from managed_service_fixtures.base_manager import (
    ExternalServiceLifecycleManager,
    ServiceDetails,
)


class AppDetails(ServiceDetails):
    hostname: str = "localhost"
    port: int = 8000

    @property
    def url(self) -> str:
        return f"http://{self.hostname}:{self.port}"

    @property
    def ws_base(self) -> str:
        return f"ws://{self.hostname}:{self.port}"


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

    env_file_pointer: str = "TEST_APP_DETAILS"
    json_state_file_name = "asgi.json"
    service_details_class = AppDetails

    def __init__(self, app_location, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app_location = app_location

    def _start_service(self) -> Tuple[AppDetails, mirakuru.Executor]:
        hostname = "localhost"
        port = self.unused_tcp_port_factory()

        details = AppDetails(hostname=hostname, port=port)

        cmd = f"""uvicorn --host {hostname} --port {port} {self.app_location}"""
        process = mirakuru.TCPExecutor(cmd, host=hostname, port=int(port), shell=True)
        process.start()
        assert process.running()
        return details, process


@pytest.fixture(scope="session")
def managed_asgi_app_factory(
    worker_id: str,
    tmp_path_factory: pytest.TempPathFactory,
    unused_tcp_port_factory: Callable[[], int],
) -> Callable[[], AppDetails]:
    def _factory(
        app_location: Optional[str] = None,
        env_file_pointer: Optional[str] = None,
        json_state_file_name: Optional[str] = None,
    ) -> AppManager:
        return AppManager(
            worker_id=worker_id,
            tmp_path_factory=tmp_path_factory,
            unused_tcp_port_factory=unused_tcp_port_factory,
            app_location=app_location,
            env_file_pointer=env_file_pointer,
            json_state_file_name=json_state_file_name,
        )

    return _factory
