import hvac
from managed_service_fixtures import VaultDetails


async def test_vault(managed_vault: VaultDetails):
    client = hvac.Client(url=managed_vault.url, token=managed_vault.token)
    assert client.is_authenticated()

    # The path may already exist if we're using an already started Vault (e.g. run-test-services)
    if "test-mount-path/" not in client.sys.list_mounted_secrets_engines()["data"]:
        client.sys.enable_secrets_engine(backend_type="kv-v2", path="test-mount-path")

    client.secrets.kv.v2.create_or_update_secret(
        path="test-mount-path", secret={"foo": "bar"}
    )

    list_result = client.secrets.kv.v2.list_secrets(path="/")
    assert "test-mount-path" in list_result["data"]["keys"]

    read_result = client.secrets.kv.v2.read_secret_version(path="test-mount-path")
    assert read_result["data"]["data"]["foo"] == "bar"
