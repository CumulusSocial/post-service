from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreatePostRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    media_keys: list[str] = Field(default_factory=list, max_length=4)


class PostOut(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID
    content: str
    media_keys: list[str]
    media_urls: list[str]
    created_at: datetime
    likes_count: int = 0


class PostList(BaseModel):
    items: list[PostOut]
    next_cursor: str | None = None


class FollowRequest(BaseModel):
    followee_id: uuid.UUID


class UserList(BaseModel):
    items: list[uuid.UUID]
    next_cursor: str | None = None


class PresignRequest(BaseModel):
    content_type: str = Field(pattern=r"^[\w-]+/[\w.+-]+$")
    size_bytes: int = Field(gt=0, le=10 * 1024 * 1024)


class PresignResponse(BaseModel):
    upload_url: str
    media_key: str
    expires_in: int
