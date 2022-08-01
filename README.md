# managed-service-fixtures

`managed-service-fixtures` is a collection of [pytest fixtures](https://docs.pytest.org/en/6.2.x/fixture.html) used to manage external processes such as databases, redis, and vault while running integration tests. 

Testing Python applications that depend on external services such as a database, redis server, or storing data in Amazon S3 can be difficult. One solution is Unit testing: mock any kind of network IO and isolate tests to your application logic alone. With larger applications, you may find yourself in "mock hell" or discover that you're missing real-world bugs.

`managed-service-fixtures` is designed to help you write Integration tests that require an external service be active. In the simplest case, where `pytest` is run serially and manages starting and stopping the service, then `managed-service-fixtures` is basically a wrapper around the excellent [mirakuru.py](https://github.com/ClearcodeHQ/mirakuru) library with some [Pydantic](https://pydantic-docs.helpmanual.io/) modeling for the service connection details. There are two common non-simple use cases this library addresses as well.

The first non-simple use-case is running tests in parallel with `pytest-xdist`. A naive fixture that starts and stops a service with `mirakuru`, even if it were sessions coped, would end up creating one service for each worker. `managed-service-fixtures` addresses this situation by using `FileLock` and a state file that each worker registers itself in. Only one worker ends up being the manager, responsible for starting the service and then shutting it down once all other workers have unregistered themselves (completed their tests).

The second non-simple use-case is managing services outside of the `pytest` fixtures. You might want to point your tests towards a service on a remote cluster. You might also want to stop `pytest` from tearing down a database after the tests complete so that you can introspect and debug what is in there. In those cases where you are manually starting and stopping services, you can set environment variables pointing to a file with connection details to those services, then the fixtures in `managed-service-fixtures` will not try to handle lifecycle management itself.

# Example

See the `tests/` directory for more usage examples.

```python
# tests/conftest.py
# https://docs.pytest.org/en/7.1.x/how-to/fixtures.html#using-fixtures-from-other-projects

pytest_plugins = 'managed_service_fixtures'
```

```python
# tests/test_vault.py
import hvac
from managed_service_fixtures import VaultDetails


def test_vault_connection(managed_vault: VaultDetails):
    client = hvac.Client(url=managed_vault.url, token=managed_vault.token)
    assert client.is_authenticated()
    assert client.sys.is_initialized()
    assert not client.sys.is_sealed()
```

# Fixtures

You may need to install a system library or CLI depending on which service you want to manage with `mirakuru` / `managed-service-fixtures`.

 - `managed_cockroach` starts an in-memory instance of [CockroachDB](https://www.cockroachlabs.com/docs/stable/frequently-asked-questions.html), see [install instructions](https://www.cockroachlabs.com/docs/stable/install-cockroachdb.html) for setting up the `cockroach` CLI
 - `managed_moto` starts a [Moto - Mock AWS Service](https://github.com/spulec/moto), `pip install moto` to enable the CLI
 - `managed_redis` starts a [Redis](https://redis.io/) server, See [install instructions](https://redis.io/docs/getting-started/installation/) to enable the `redis-server` CLI
 - `managed_vault` starts a [Vault](https://www.vaultproject.io/) server, see [install instructions](https://www.vaultproject.io/docs/install) to enable the `vault` CLI

# ASGI apps

`managed-service-fixtures` supports running an ASGI app (such as a [FastAPI](https://fastapi.tiangolo.com/) or [Starlette](https://www.starlette.io/) app) with `uvicorn` as a managed service. You may want to use this if:
 
 - You're using `httpx.AsyncClient` for [async tests](https://fastapi.tiangolo.com/advanced/async-tests/) and need to test websocket endpoints
 - You have a `websockets` application/library and need to spin up a server to test request/responses

A downside to running an ASGI app in an external process is that you lose breakpoint/debug support in your tests.


