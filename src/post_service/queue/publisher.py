from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from post_service.config import settings
from post_service.logging import log


class SNSPublisher:
    def __init__(self, sns_client, topic_arn: str) -> None:
        self._client = sns_client
        self._topic_arn = topic_arn

    async def publish(
        self, *, event_type: str, actor_id: uuid.UUID, data: dict[str, Any]
    ) -> str:
        envelope = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "occurred_at": datetime.now(UTC).isoformat(),
            "actor_id": str(actor_id),
            "data": _jsonable(data),
        }
        body = json.dumps(envelope, separators=(",", ":"))
        try:
            await asyncio.to_thread(
                self._client.publish,
                TopicArn=self._topic_arn,
                Message=body,
                MessageAttributes={
                    "event_type": {"DataType": "String", "StringValue": event_type},
                },
            )
        except Exception:
            log.exception("sns.publish.failed", event_type=event_type)
            raise
        log.info("sns.publish", event_type=event_type, event_id=envelope["event_id"])
        return envelope["event_id"]


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def make_sns_client():
    import boto3  # local import: keeps tests fast

    return boto3.client(
        "sns",
        region_name=settings.aws_region,
        endpoint_url=settings.aws_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
