from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"
    http_port: int = 8002

    database_url: str = Field(
        default="postgresql+asyncpg://post:post@localhost:5432/post_db"
    )

    auth_base_url: str = "http://localhost:8001"
    jwt_issuer: str = "auth-service"
    jwks_refresh_seconds: int = 600

    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = None  # set to LocalStack URL in dev
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    sns_topic_arn: str = ""
    s3_bucket: str = "post-media"
    s3_presign_put_ttl: int = 300
    s3_presign_get_ttl: int = 900
    # Public-facing endpoint for presigned URLs (browser must reach this).
    # In prod (real S3), leave None. In dev with LocalStack, set to the host
    # URL the browser sees, e.g. http://localhost:4566 — post-service rewrites
    # the SDK-generated URL host before returning it to the client.
    s3_public_endpoint_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
