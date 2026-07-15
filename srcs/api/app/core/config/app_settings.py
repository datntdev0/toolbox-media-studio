from dataclasses import dataclass
import os

from shared.decorators import singleton

@dataclass
class ConnectionStrings:
    azCosmosDb: str
    azStorageBlob: str
    azStorageQueue: str

@singleton
class AppSettings:

    def __init__(self):
        self.appName: str = "Toolbox Media Studio"
        self.environment: str = os.environ.get("FAST_ENVIRONMENT", "localhost")

        self.logLevel: str = "INFO"
        
        self.connectionStrings: ConnectionStrings = ConnectionStrings(
            azCosmosDb=os.environ.get("FAST_AZ_CONNECTION_STRING_COSMOSDB", ""),
            azStorageBlob=os.environ.get("FAST_AZ_CONNECTION_STRING_STORAGE_BLOB", ""),
            azStorageQueue=os.environ.get("FAST_AZ_CONNECTION_STRING_STORAGE_QUEUE", ""))
