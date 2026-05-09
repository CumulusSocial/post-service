from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from post_service.models.follow import Follow


class CannotFollowSelf(Exception):
    pass


async def follow(
    session: AsyncSession, *, follower_id: uuid.UUID, followee_id: uuid.UUID
) -> bool:
    """Returns True if a new follow was created."""
    if follower_id == followee_id:
        raise CannotFollowSelf()
    stmt = pg_insert(Follow.__table__).values(
        follower_id=follower_id, followee_id=followee_id
    ).on_conflict_do_nothing(index_elements=["follower_id", "followee_id"])
    result = await session.execute(stmt)
    return result.rowcount > 0


async def unfollow(
    session: AsyncSession, *, follower_id: uuid.UUID, followee_id: uuid.UUID
) -> bool:
    result = await session.execute(
        delete(Follow).where(
            Follow.follower_id == follower_id, Follow.followee_id == followee_id
        )
    )
    return result.rowcount > 0


async def list_followers(
    session: AsyncSession, *, user_id: uuid.UUID, limit: int = 100, offset: int = 0
) -> list[uuid.UUID]:
    rows = await session.scalars(
        select(Follow.follower_id)
        .where(Follow.followee_id == user_id)
        .order_by(Follow.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows.all())


async def list_following(
    session: AsyncSession, *, user_id: uuid.UUID, limit: int = 100, offset: int = 0
) -> list[uuid.UUID]:
    rows = await session.scalars(
        select(Follow.followee_id)
        .where(Follow.follower_id == user_id)
        .order_by(Follow.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows.all())
