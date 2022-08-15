import abc
import json
import logging
import os
import pathlib
import time
from types import TracebackType
from typing import Callable, List, Optional, Tuple, Type

import mirakuru
import pytest
from filelock import FileLock
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ServiceDetails(BaseModel):
    """
    Base class for service-specific connection details.

    Subclasses will likely have fields such as hostname, port, and
    maybe username/password. Also convenience @property's for URL/DSN construction.

    Subclasses should not override or re-use the `sessions` field. That field is
    used by the ExternalServiceLifecycleManager when controlling startup and
    shutdown of the service in parallel test execution
    """

    sessions: List[str] = Field(default_factory=list)
    is_manager: bool = True


class ExternalServiceLifecycleManager(abc.ABC):
    """
    Abstraction to manage the lifecycle of an external service (database, vault, redis, etc).
    Supports multiple use-cases:
     - Run tests serially and start services with mirakuru
     - Run tests in parallel (xdist) and only start a single instance of the service
     - Services are running already and this manager reads connection details from a file

    pytest-xdist aware architecture pattern inspired by
    https://github.com/pytest-dev/pytest-xdist#making-session-scoped-fixtures-execute-only-once

    When not running in parallel, the state file is not used in any way. A service is stood up,
    connection details returned, and service torn down at the end of the tests.

    When running in parallel however, each worker tries to establish a file lock and
    read the state file. If the connection details are not in the state file already,
    then that worker becomes the manager of the service.

    Workers that are not the manager only need to add their `worker_id` into the state file while
    they are processing tests, and remove their `worker_id` from the state file when complete.

    The single manager xdist worker will be responsible for starting an initializing the service
    in __enter__, and then once its own tests are complete and __exit__ is called,
    determine if any other workers still need it up. The manager will not tear down the service until
    all non-manager workers have removed their `worker_id` from the state file.

    Finally, you may set an environment variable pointing to a file containing connection details
    for a service started outside of this fixture, such as a remote test cluster. In that case,
    no process will be started or stopped by mirakuru.
    """

    # env_file_pointer would be something like TEST_REDIS_DETAILS
    # and would point to a file containing json-serialized connection details
    # to the service managed outside of mirakuru
    #
    # Subclasses should overwrite all three class attributes below
    env_file_pointer: str = None
    json_state_file_name: str = None
    service_details_class: Type[ServiceDetails] = ServiceDetails

    def __init__(
        self,
        worker_id: str,
        tmp_path_factory: pytest.TempPathFactory,
        unused_tcp_port_factory: Callable[[], int],
        # Optional overrides to cls attributes for factory fixture pattern
        env_file_pointer: Optional[str] = None,
        json_state_file_name: Optional[str] = None,
        service_details_class: Optional[Type[ServiceDetails]] = None,
    ):
        """
        All three init arguments should be pulled in from pytest fixtures.

        worker_id: pytest-xdist fixture to give a worker id when run in parallel
        tmp_path_factory: core pytest fixture, returns temporary directories.
        unused_tcp_port_factory: pytest-asyncio fixture, returns unused TCP ports.

        Example usage:

        @pytest.fixture(scope="session")
        def some_managed_service(
            worker_id: str,
            tmp_path_factory: pytest.TempPathFactory,
            unused_tcp_port_factory: Callable[[], int],
        ):
            with ExternalServiceLifecycleManagerSubclass(
                worker_id=worker_id,
                tmp_path_factory=tmp_path_factory,
                unused_tcp_port_factory=unused_tcp_port_factory,
            ) as service_details:
                yield service_details
        """
        self.env_file_pointer = env_file_pointer or self.env_file_pointer
        self.json_state_file_name = json_state_file_name or self.json_state_file_name
        self.service_details_class = service_details_class or self.service_details_class

        self.mirakuru_process = None  # set in __enter__, used in __exit__
        self.manage_process_lifecycle = False
        # ^^ may get set to True during __enter__ when running in parallel
        self.configed_from_env = False
        # ^^ gets set to True during __enter__ if service is being managed externally and
        # connection details are read from a file pointed at by environ variables

        self.worker_id = worker_id
        self.unused_tcp_port_factory = unused_tcp_port_factory

        # Need to position our state file in a dir common to all of the xdist
        # workers, but still scoped to be within this test run. Will end
        # up being something like $TMPDIR/pytest-of-<username>/pytest-N/
        root_tmp_dir = tmp_path_factory.getbasetemp().parent

        self.state_file_path = root_tmp_dir / self.json_state_file_name
        self.lock_file_path = pathlib.Path(str(self.state_file_path) + ".lock")

    @abc.abstractmethod
    def _start_service(
        self, is_manager: bool
    ) -> Tuple[ServiceDetails, mirakuru.Executor]:
        """
        Implement start-up logic using mirakuru and self.unused_tcp_port_factory.

        The logic here does NOT need to worry about serial vs parallel execution
        and this code path won't be entered if there is a pointer to a connection
        details filepath at env variable self.env_file_pointer.

        Must return a tuple of ServiceDetails-subclassed pydantic model and mirakuru process.
        """
        raise NotImplementedError()

    def _service_from_env(self):
        if self.env_file_pointer and os.environ.get(self.env_file_pointer):
            settings_file_path = pathlib.Path(os.environ[self.env_file_pointer])
            if settings_file_path.exists():
                content = json.loads(settings_file_path.read_text())
                service_details = self.service_details_class(**content)
                self.configed_from_env = True
                return service_details
            else:
                logger.warn(
                    f"Env variable {self.env_file_pointer} set but no file exists at {settings_file_path}. Starting new service."
                )

    def __enter__(self) -> ServiceDetails:
        # Check environment variables / class config to see if the service
        # is being started outside of this class (e.g. a remote test cluster)

        # Once we're here, we know we need to manage starting a process
        # and later stopping it in .__exit__.
        # If worker_id == 'master' then it means tests are serial and our
        # logic is going to be simple.
        if self.worker_id == "master":
            service_details = self._service_from_env()
            if not service_details:
                service_details, self.mirakuru_process = self._start_service()

        # Otherwise tests are in parallel and the logic is more complicated
        else:
            with FileLock(self.lock_file_path):
                if not self.state_file_path.is_file():
                    # Lock file doesn't exist, which means this instance is the
                    # first to try and access it, so it becomes the manager among
                    # parallel pytest workers.
                    self.manage_process_lifecycle = True
                    service_details = self._service_from_env()
                    if not service_details:
                        service_details, self.mirakuru_process = self._start_service()

                    state_file_dict = service_details.dict()
                    state_file_dict["sessions"] = []
                else:
                    # If the lock file does exist, this worker needs to record
                    # that it is using the service and the manager should not shut
                    # it down until this instance has exited the context block
                    self.manage_process_lifecycle = False
                    state_file_dict = json.loads(self.state_file_path.read_text())
                    service_details = self.service_details_class(
                        is_manager=False, **state_file_dict
                    )

                    # This is why ServiceDetails subclasses should not
                    # override or re-use the `sessions` field.
                    service_details.sessions.append(self.worker_id)

                # Manager or not, serialize created or mutated state_file_dict
                # to state_file_path while still holding the lockfile lock.
                self.state_file_path.write_text(
                    service_details.json(exclude={"is_manager"})
                )

        return service_details

    def __exit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> None:
        # If the service is being managed externally, we have nothing to do here
        if self.configed_from_env:
            return

        # If tests were run serially, the shutdown logic is simple
        elif self.worker_id == "master":
            self.mirakuru_process.stop()

        # Lastly the complicated part, shutting down the service in parallel test exec
        # If this instance is the manager, it polls the state file until there's no
        # registered workers left, then shuts down the service.
        # Otherwise this worker needs to remove itself from the state file.
        else:
            if self.manage_process_lifecycle:
                any_other_users = True  # We assume at first, anyway.

                while True:
                    with FileLock(self.lock_file_path):
                        state_file_dict = json.loads(self.state_file_path.read_text())
                        # Only the *other* xdist sessions record their presence in here. Not us.
                        # (can then use an empty-or-not test on this list).
                        any_other_users = bool(len(state_file_dict["sessions"]))

                        if not any_other_users:
                            # Finally, nobody else using it!
                            self.mirakuru_process.stop()

                            # Clean up our files.
                            self.state_file_path.unlink()
                            # Implicitly also releases the FileLock!
                            self.lock_file_path.unlink()

                            break  # Blessed freedom. Skips sleep.

                    # Lock released, but still looping. There are other sessions still.
                    # Try again in a bit!
                    time.sleep(0.25)

            else:
                with FileLock(self.lock_file_path):
                    # All we need to do is remove ourselves from the current sessions. The manager
                    # session is responsible for hanging around until all workers are unregistered
                    # and then shutting down the service.
                    state_file_dict = json.loads(self.state_file_path.read_text())

                    concurrent_sessions = state_file_dict["sessions"]
                    assert self.worker_id in concurrent_sessions
                    concurrent_sessions.remove(self.worker_id)

                    self.state_file_path.write_text(json.dumps(state_file_dict))
