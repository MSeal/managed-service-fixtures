"""
Used in run_test_services.py style scripts which run a service outside of having pytest / fixtures
kick off the mirakuru spawning process.

You might use that if you want to introspect the service (database/vault/etc) before, during, or after
the tests run.
"""

import contextlib
import json
import pathlib
import socket
import subprocess
import tempfile
from typing import Optional

import mirakuru
import structlog


def find_free_port():
    # https://stackoverflow.com/a/45690594/1391176
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


class LoggingTCPExecutor:
    """
    Designed to be subclassed for your specific service, e.g. MotoManager(LoggingTCPExecutor).

    Starts a service using mirakuru and writes the connection details to a file in the temp directory.
    When the service stops, it cleans up the connection details file.

    If a connection details file already exists, it will not start the service nor clean up the file.

    Automatically finds free ports to use on localhost if one isn't specified.
    """

    cmd_template: str = ""
    host: str = "localhost"
    port: Optional[int] = None
    env_name: str = ""

    def __init__(self, verbose: bool = False):
        """
        Control logging verbosity by choosing stdout / stderr to be None (streams to
        main process stdout) or subprocess.PIPE (captures subprocess output and
        does not stream to main process sdout)

        TODO: Figure out how to capture and read stdout/stderr from multiple
        subprocesses and log them all in the main process color coded by sub-process
        e.g. Vault logs in red, Cockroach logs in green, etc
        """
        self.logger = structlog.get_logger(self.__class__.__name__)
        # XXX: tempfiles aren't getting cleaned up when a script is keyboard interrupted, not sure why.
        # For now the workaround is to call .unlink() in the __exit__ method
        with tempfile.NamedTemporaryFile(suffix=".json") as tmp_file:
            self.connection_details_file = pathlib.Path(tmp_file.name)

        self.port = self.port or find_free_port()
        self.connection_details = {"cmd_template": self.cmd_template}
        self.connection_details.update(self.extra_details())
        # set these after the extra details update in case a subclass is overriding them
        # as part of its extra details setup.
        self.connection_details["host"] = self.host
        self.connection_details["port"] = self.port
        # Finally build up the mirakuru command using the cmd template and connection details
        command = self.cmd_template.format(**self.connection_details)
        self.connection_details["command"] = command
        if verbose:
            stdout = None
            stderr = None
        else:
            stdout = subprocess.DEVNULL
            stderr = subprocess.DEVNULL

        self.executor = mirakuru.TCPExecutor(
            command=command,
            host=self.host,
            port=self.port,
            stdout=stdout,
            stderr=stderr,
        )

    def extra_details(self) -> dict:
        """
        Override this to return extra details to be included in the connection details file.
        """
        return {}

    @property
    def name(self):
        return self.command.split()[0]

    def __enter__(self):
        print("in enter")
        print(self.connection_details)
        print(self.executor)
        try:
            self.executor.__enter__()
        except mirakuru.ExecutorError as e:
            if "already running" in str(e):
                self.logger.warning(
                    f"Port {self.port} already in use when trying to start {self.executor}."
                )
        self.connection_details_file.write_text(
            json.dumps(self.connection_details, indent=4)
        )
        self.logger.info(
            f"Connection details for {self.executor} written to {self.connection_details_file}"
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.connection_details_file.unlink()
        self.executor.__exit__(exc_type, exc_val, exc_tb)
