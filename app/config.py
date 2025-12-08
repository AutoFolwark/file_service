from enum import Enum

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.utils import BASE_DIR


class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"



class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "test_db"
    DB_USER: str = "postgres"
    DB_PASS: str = "testpass"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Application
    APP_NAME: str = "files-service"
    DEBUG: bool = True
    ROOT_PATH: str = ''
    ENVIRONMENT: str = "development"

    # RPC
    GRPC_SERVER_PORT: int = 50053
    RPC_API_URL: str = "localhost:50051"

    # S3
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION: str = "eu-north-1"
    S3_BUCKET: str = "vinas-files-development"
    S3_ENDPOINT_URL: str | None = None
    S3_USE_SSL: bool = True
    S3_FORCE_PATH_STYLE: bool = True
    S3_PRESIGNED_EXPIRES_IN: int = 900  # seconds

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@localhost/"
    RABBITMQ_EXCHANGE_NAME: str = "events"


    @property
    def enable_docs(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

settings = Settings()
