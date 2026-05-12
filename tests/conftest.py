from __future__ import annotations

import base64
import os
import time
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from jose import jwt
from testcontainers.postgres import PostgresContainer


def _b64url_uint(n: int) -> str:
    byte_len = (n.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(n.to_bytes(byte_len, "big")).rstrip(b"=").decode("ascii")


@pytest.fixture(scope="session")
def keypair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub = priv.public_key()
    nums = pub.public_numbers()
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": "test-key",
        "n": _b64url_uint(nums.n),
        "e": _b64url_uint(nums.e),
    }
    return priv_pem, jwk


def make_token(priv_pem: str, *, sub: uuid.UUID, email: str = "u@example.com") -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": str(sub),
            "email": email,
            "iat": now,
            "exp": now + 600,
            "iss": "auth-service",
        },
        priv_pem,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )


@pytest.fixture(scope="session")
def postgres_url() -> AsyncIterator[str]:
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("psycopg2", "asyncpg")
        yield url


class FakeSNS:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def publish(self, *, TopicArn: str, Message: str, MessageAttributes: dict):  # noqa: N803
        import json
        self.events.append(json.loads(Message))
        return {"MessageId": str(uuid.uuid4())}


class FakeS3:
    def generate_presigned_url(self, op: str, *, Params: dict, ExpiresIn: int):  # noqa: N803
        bucket = Params["Bucket"]
        key = Params["Key"]
        return f"https://s3.fake/{bucket}/{key}?op={op}&exp={ExpiresIn}"


@pytest_asyncio.fixture
async def app_client(keypair, postgres_url) -> AsyncIterator[AsyncClient]:
    priv_pem, jwk = keypair

    os.environ["DATABASE_URL"] = postgres_url
    os.environ["AUTH_BASE_URL"] = "http://auth.fake"
    os.environ["JWT_ISSUER"] = "auth-service"
    os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:eu-south-1:000000000000:post-events"
    os.environ["S3_BUCKET"] = "test-bucket"

    from post_service.config import get_settings  # noqa: PLC0415
    get_settings.cache_clear()

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: PLC0415
    from sqlalchemy.pool import NullPool  # noqa: PLC0415

    from post_service import db as db_mod  # noqa: PLC0415
    from post_service.models import follow, like, post  # noqa: F401, PLC0415
    from post_service.models.base import Base  # noqa: PLC0415

    # Replace module-level engine with a NullPool one so connections aren't
    # carried across event loops between tests.
    db_mod.engine = create_async_engine(postgres_url, poolclass=NullPool)
    db_mod.SessionLocal = async_sessionmaker(
        db_mod.engine, expire_on_commit=False
    )

    async with db_mod.engine.begin() as conn:
        await conn.exec_driver_sql('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
        await conn.run_sync(Base.metadata.create_all)

    # patch JWKS cache so it returns the test public key without HTTP
    from post_service.security import jwt_verify  # noqa: PLC0415
    jwt_verify.reset_cache_for_tests()
    jwt_verify._cache.keys = {"test-key": jwk}
    jwt_verify._cache.fetched_at = time.time()

    from post_service.main import app  # noqa: PLC0415
    from post_service.queue.publisher import SNSPublisher  # noqa: PLC0415
    from post_service.services.media import MediaService  # noqa: PLC0415

    fake_sns = FakeSNS()
    fake_s3 = FakeS3()

    async with app.router.lifespan_context(app):
        # override after lifespan started
        app.state.sns = SNSPublisher(fake_sns, "arn:aws:sns:eu-south-1:000000000000:post-events")
        app.state.media = MediaService(fake_s3, "test-bucket")
        app.state.fake_sns = fake_sns
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client._priv_pem = priv_pem  # type: ignore[attr-defined]
            yield client

    async with db_mod.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await db_mod.engine.dispose()


@pytest.fixture
def auth_headers(app_client):
    def _make(user_id: uuid.UUID) -> dict[str, str]:
        token = make_token(app_client._priv_pem, sub=user_id)
        return {"Authorization": f"Bearer {token}"}
    return _make
