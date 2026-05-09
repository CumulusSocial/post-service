from __future__ import annotations

import base64
import uuid
from datetime import datetime

from sqlalchemy import delete, desc, exists, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from post_service.models.like import Like
from post_service.models.post import Post


class PostNotFound(Exception):
    pass


def _encode_cursor(created_at: datetime, post_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{post_id}".encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    pad = "=" * (-len(cursor) % 4)
    raw = base64.urlsafe_b64decode(cursor + pad).decode()
    ts, pid = raw.split("|", 1)
    return datetime.fromisoformat(ts), uuid.UUID(pid)


async def create_post(
    session: AsyncSession,
    *,
    author_id: uuid.UUID,
    content: str,
    media_keys: list[str],
) -> Post:
    post = Post(author_id=author_id, content=content, media_keys=media_keys)
    session.add(post)
    await session.flush()
    await session.refresh(post)
    return post


async def get_post(session: AsyncSession, post_id: uuid.UUID) -> Post:
    p = await session.scalar(select(Post).where(Post.id == post_id))
    if p is None:
        raise PostNotFound(str(post_id))
    return p


async def list_user_posts(
    session: AsyncSession,
    *,
    author_id: uuid.UUID,
    limit: int = 20,
    cursor: str | None = None,
) -> tuple[list[Post], str | None]:
    stmt = select(Post).where(Post.author_id == author_id)
    if cursor:
        ts, pid = _decode_cursor(cursor)
        stmt = stmt.where((Post.created_at, Post.id) < (ts, pid))
    stmt = stmt.order_by(desc(Post.created_at), desc(Post.id)).limit(limit + 1)
    rows = list((await session.scalars(stmt)).all())
    next_cursor: str | None = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = _encode_cursor(last.created_at, last.id)
        rows = rows[:limit]
    return rows, next_cursor


async def like_post(
    session: AsyncSession, *, user_id: uuid.UUID, post_id: uuid.UUID
) -> tuple[bool, uuid.UUID]:
    """Returns (created, author_id). created=False if already liked."""
    post = await get_post(session, post_id)
    stmt = pg_insert(Like.__table__).values(
        user_id=user_id, post_id=post_id
    ).on_conflict_do_nothing(index_elements=["user_id", "post_id"])
    result = await session.execute(stmt)
    return result.rowcount > 0, post.author_id


async def unlike_post(
    session: AsyncSession, *, user_id: uuid.UUID, post_id: uuid.UUID
) -> tuple[bool, uuid.UUID]:
    """Returns (deleted, author_id)."""
    post = await get_post(session, post_id)
    result = await session.execute(
        delete(Like).where(Like.user_id == user_id, Like.post_id == post_id)
    )
    return result.rowcount > 0, post.author_id


async def is_liked_by(
    session: AsyncSession, *, user_id: uuid.UUID, post_id: uuid.UUID
) -> bool:
    return bool(
        await session.scalar(
            select(exists().where(Like.user_id == user_id, Like.post_id == post_id))
        )
    )
