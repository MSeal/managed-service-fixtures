import contextlib
import logging
import time

import click

from managed_service_fixtures import LoggingTCPExecutor, find_free_port

logger = logging.getLogger(__name__)


class MotoManager(LoggingTCPExecutor):
    cmd_template = "moto_server --host {host} --port {port} s3"
    env_name = "TEST_MOTO_DETAILS"


class RedisManager(LoggingTCPExecutor):
    cmd_template = "redis-server --port {port}"
    env_name = "TEST_REDIS_DETAILS"


class CockroachManager(LoggingTCPExecutor):
    # Cockroach has both a sql port and http (dashboard UI) port.
    # we don't need to record the http address in the connection details
    # when we're using "--insecure", then user is root, pw is none, and db is 'defaultdb'
    cmd_template = "cockroach start-single-node --insecure --listen-addr={host}:{sql_port} --http-addr {host}:{http_port} --store=type=mem,size=641mib"
    env_name = "TEST_CRDB_DETAILS"

    def extra_details(self) -> dict:
        d = {
            "sql_port": find_free_port(),
            "http_port": find_free_port(),
            "username": "root",
            "password": "",
            "dbname": "defaultdb",
        }
        # Override self.port. Mirakuru will block until it sees this port is in use.
        self.port = d["sql_port"]
        return d


class VaultManager(LoggingTCPExecutor):
    cmd_template = (
        "vault server -dev -dev-root-token-id=root --dev-listen-address={host}:{port}"
    )
    env_name = "TEST_VAULT_DETAILS"

    def extra_details(self) -> dict:
        return {"token": "root"}


@click.command()
def main():
    moto = MotoManager()
    redis = RedisManager()
    cockroach = CockroachManager()
    vault = VaultManager()
    contexts = [moto, redis, cockroach, vault]
    with contextlib.ExitStack() as stack:

        env_copy_paste_block = "\n"
        dot_env_file_block = "\n"
        for context in contexts:
            if context.env_name:
                env_copy_paste_block += f"{context.env_name}={context.connection_details_file}; export {context.env_name}\n"
                dot_env_file_block += (
                    f"{context.env_name}={context.connection_details_file}\n"
                )
        logger.info("Before running tests, set these environment variables:")
        logger.info(env_copy_paste_block)
        logger.info("Or if using a .env file, add these lines to it:")
        logger.info(dot_env_file_block)

        crdb_details = cockroach.connection_details
        logger.info(
            f"To introspect test database, run 'cockroach sql --host={crdb_details['host']}:{crdb_details['sql_port']} --insecure' "
        )
        for context in contexts:
            stack.enter_context(context)

        while True:
            time.sleep(1)


if __name__ == "__main__":
    main()
