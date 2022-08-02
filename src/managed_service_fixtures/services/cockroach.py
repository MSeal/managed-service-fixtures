from typing import Callable, Tuple

import mirakuru
import pytest

from managed_service_fixtures.base_manager import (
    ExternalServiceLifecycleManager,
    ServiceDetails,
)


class CockroachDetails(ServiceDetails):
    hostname: str = "localhost"
    sql_port: int = 26257
    http_port: int = 8008
    username: str = "root"
    password: str = ""
    dbname: str = "defaultdb"

    @property
    def sync_dsn(self) -> str:
        """Project self as a SQLAlchemy synchronous DSN"""
        return f"cockroachdb://{self.username}:{self.password}@{self.hostname}:{self.sql_port}/{self.dbname}"

    @property
    def async_dsn(self) -> str:
        """Project self as a SQLAlchemy asynchronous DSN"""
        return f"cockroachdb+asyncpg://{self.username}:{self.password}@{self.hostname}:{self.sql_port}/{self.dbname}"

    @property
    def webui(self) -> str:
        """Web UI/Dashboard URL for debug and query review"""
        return f"http://{self.hostname}:{self.http_port}"


class CockroachManager(ExternalServiceLifecycleManager):
    """
    Start an ephemeral in-memory CockroachDB read connection details from a filepath defined
    by a TEST_CRDB_DETAILS environment variable.

    Cockroach uses two ports, one for sql connections and one to host an http dashboard.

    There is no table schema creation here, users will need to do that somewhere else.

    See https://www.cockroachlabs.com/docs/stable/install-cockroachdb.html for
    installing Cockroach.
    """

    env_file_pointer: str = "TEST_CRDB_DETAILS"
    json_state_file_name = "cockroachdb.json"
    service_details_class = CockroachDetails

    def _start_service(self) -> Tuple[CockroachDetails, mirakuru.Executor]:
        sql_port = self.unused_tcp_port_factory()
        http_port = self.unused_tcp_port_factory()
        hostname = "localhost"
        username = "root"
        password = ""

        details = CockroachDetails(
            hostname=hostname,
            sql_port=sql_port,
            http_port=http_port,
            username=username,
            password=password,
            # defaultdb exists, and 'root' user has superuser privs over it.
            dbname="defaultdb",
        )

        # chdir to avoid heap_profiler/ subdir from littering top of gate tree.
        cockroach_cmd = f"""cd $TMPDIR && cockroach start-single-node --insecure --listen-addr  localhost:{sql_port} --http-addr localhost:{http_port} --store=type=mem,size=641mib"""
        process = mirakuru.TCPExecutor(
            cockroach_cmd, host=hostname, port=int(sql_port), shell=True
        )
        process.start()
        assert process.running()
        return details, process


@pytest.fixture(scope="session")
def managed_cockroach(
    worker_id: str,
    tmp_path_factory: pytest.TempPathFactory,
    unused_tcp_port_factory: Callable[[], int],
) -> CockroachDetails:
    """
    Yields connection details for a CockroachDB instance.

    SQLAlchemy connection example:
     - engine = create_engine(cockroach_details.sync_dsn)
     - async_engine = create_async_engine(cockroach_details.async_dsn)

    View the CRDB Dashboard at URL: print(cockroach_details.webui).
    """
    with CockroachManager(
        worker_id=worker_id,
        tmp_path_factory=tmp_path_factory,
        unused_tcp_port_factory=unused_tcp_port_factory,
    ) as cockroach_details:
        yield cockroach_details
