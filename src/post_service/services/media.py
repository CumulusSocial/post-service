from __future__ import annotations

import asyncio
import mimetypes
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from post_service.config import settings

_ALLOWED = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def _rewrite_for_public(url: str) -> str:
    """Rewrite the S3 endpoint host to the public-facing one (dev only)."""
    if not settings.s3_public_endpoint_url or not settings.aws_endpoint_url:
        return url
    public = urlparse(settings.s3_public_endpoint_url)
    parts = urlparse(url)
    return urlunparse(parts._replace(scheme=public.scheme, netloc=public.netloc))


@dataclass(slots=True)
class Presigned:
    upload_url: str
    media_key: str
    expires_in: int


class MediaService:
    def __init__(self, s3_client, bucket: str) -> None:
        self._s3 = s3_client
        self._bucket = bucket

    @staticmethod
    def _ext(content_type: str) -> str:
        if content_type not in _ALLOWED:
            raise ValueError(f"unsupported content type: {content_type}")
        ext = mimetypes.guess_extension(content_type) or ".bin"
        return ext

    async def presign_put(
        self, *, user_id: uuid.UUID, content_type: str, size_bytes: int
    ) -> Presigned:
        ext = self._ext(content_type)
        key = f"users/{user_id}/{uuid.uuid4()}{ext}"
        url = await asyncio.to_thread(
            self._s3.generate_presigned_url,
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=settings.s3_presign_put_ttl,
        )
        return Presigned(
            upload_url=_rewrite_for_public(url),
            media_key=key,
            expires_in=settings.s3_presign_put_ttl,
        )

    async def presign_get(self, *, media_key: str) -> str:
        url = await asyncio.to_thread(
            self._s3.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": media_key},
            ExpiresIn=settings.s3_presign_get_ttl,
        )
        return _rewrite_for_public(url)

    async def presign_get_many(self, *, media_keys: list[str]) -> list[str]:
        if not media_keys:
            return []
        return await asyncio.gather(*(self.presign_get(media_key=k) for k in media_keys))


def make_s3_client():
    import boto3
    from botocore.config import Config

    endpoint_url = settings.aws_endpoint_url or \
        f"https://s3.{settings.aws_region}.amazonaws.com"

    cfg = Config(signature_version="s3v4", region_name=settings.aws_region)
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        config=cfg,
    )
