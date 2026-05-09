from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from post_service.db import get_session
from post_service.deps import get_current_user_id
from post_service.queue.publisher import SNSPublisher
from post_service.schemas.post import FollowRequest, UserList
from post_service.services import follows as follows_svc

router = APIRouter()


def _publisher(request: Request) -> SNSPublisher:
    return request.app.state.sns


@router.post("/follow", status_code=status.HTTP_204_NO_CONTENT)
async def create_follow(
    body: FollowRequest,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
) -> Response:
    try:
        created = await follows_svc.follow(
            session, follower_id=user_id, followee_id=body.followee_id
        )
    except follows_svc.CannotFollowSelf as e:
        raise HTTPException(status_code=400, detail="cannot follow yourself") from e
    if created:
        await _publisher(request).publish(
            event_type="follow.created",
            actor_id=user_id,
            data={"follower_id": user_id, "followee_id": body.followee_id},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/follow", status_code=status.HTTP_204_NO_CONTENT)
async def remove_follow(
    body: FollowRequest,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
) -> Response:
    deleted = await follows_svc.unfollow(
        session, follower_id=user_id, followee_id=body.followee_id
    )
    if deleted:
        await _publisher(request).publish(
            event_type="follow.deleted",
            actor_id=user_id,
            data={"follower_id": user_id, "followee_id": body.followee_id},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/follows/{user_id}/followers", response_model=UserList)
async def followers(
    user_id: uuid.UUID,
    _viewer: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> UserList:
    items = await follows_svc.list_followers(
        session, user_id=user_id, limit=limit, offset=offset
    )
    return UserList(items=items)


@router.get("/follows/{user_id}/following", response_model=UserList)
async def following(
    user_id: uuid.UUID,
    _viewer: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> UserList:
    items = await follows_svc.list_following(
        session, user_id=user_id, limit=limit, offset=offset
    )
    return UserList(items=items)
