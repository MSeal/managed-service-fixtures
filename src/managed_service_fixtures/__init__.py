from importlib_metadata import version

from .services.asgi_app import AppDetails, managed_asgi_app
from .services.cockroach import CockroachDetails, managed_cockroach
from .services.moto import MotoDetails, managed_moto
from .services.redis import RedisDetails, managed_redis
from .services.vault import VaultDetails, managed_vault

__version__ = version(__package__)
