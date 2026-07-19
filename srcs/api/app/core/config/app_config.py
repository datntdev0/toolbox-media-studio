import os
from dataclasses import dataclass

from shared.decorators import singleton


@dataclass
class ConnectionStrings:
    azCosmosDb: str
    azStorageBlob: str
    azStorageQueue: str

@dataclass
class Security:
    jwt_algorithm: str
    jwt_signing_key: str
    jwt_expire_minutes: int
    default_admin_email: str
    default_admin_password: str

@dataclass
class CacheSettings:
    ttl_default: int
    ttl_crawler: int

@dataclass
class FlareSolverrSettings:
    base_url: str
    default_max_timeout_ms: int

CACHE_TTL_DEFAULT = 3600
CACHE_TTL_CRAWLER = 604800

@singleton
class AppConfig:

    def __init__(self):
        self.appName: str = "Toolbox Media Studio"
        self.environment: str = os.environ.get("FAST_ENVIRONMENT", "localhost")

        self.logLevel: str = "INFO"

        self.azCosmosDbDatabaseName: str = os.environ.get(
            "FAST_AZ_COSMOSDB_DATABASE_NAME",
            "datntdev.mediastudio",
        )

        self.connectionStrings: ConnectionStrings = ConnectionStrings(
            azCosmosDb=os.environ.get("FAST_AZ_CONNECTION_STRING_COSMOSDB", ""),
            azStorageBlob=os.environ.get("FAST_AZ_CONNECTION_STRING_STORAGE_BLOB", ""),
            azStorageQueue=os.environ.get("FAST_AZ_CONNECTION_STRING_STORAGE_QUEUE", ""),
        )

        self.security: Security = Security(
            jwt_algorithm=os.environ.get("FAST_SECURITY_JWT_ALGORITHM", "HS256"),
            jwt_signing_key=os.environ.get(
                "FAST_SECURITY_JWT_SIGNING_KEY",
                "datntdev.mediastudio",
            ),
            jwt_expire_minutes=int(os.environ.get("FAST_SECURITY_JWT_EXPIRE_MINUTES", "60")),
            default_admin_email=os.environ.get("FAST_SECURITY_DEFAULT_ADMIN_EMAIL"),
            default_admin_password=os.environ.get("FAST_SECURITY_DEFAULT_ADMIN_PASSWORD"),
        )

        self.cache: CacheSettings = CacheSettings(
            ttl_default=CACHE_TTL_DEFAULT,
            ttl_crawler=CACHE_TTL_CRAWLER,
        )

        self.flaresolverr: FlareSolverrSettings = FlareSolverrSettings(
            base_url=os.environ.get("FAST_FLARESOLVERR_BASE_URL", "http://localhost:8191/v1"),
            default_max_timeout_ms=int(os.environ.get("FAST_FLARESOLVERR_MAX_TIMEOUT_MS", "60000")),
        )
