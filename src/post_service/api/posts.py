from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from post_service.db import get_session
from post_service.deps import get_current_user_id
from post_service.models.post import Post
from post_service.queue.publisher import SNSPublisher
from post_service.schemas.post import CreatePostRequest, PostList, PostOut
from post_service.services import posts as posts_svc
from post_service.services.media import MediaService

router = APIRouter()


def _publisher(request: Request) -> SNSPublisher:
    return request.app.state.sns


def _media(request: Request) -> MediaService:
    return request.app.state.media


async def _to_out(
    post: Post, media: MediaService, likes_count: int = 0
) -> PostOut:
    urls = await media.presign_get_many(media_keys=list(post.media_keys))
    return PostOut(
        id=post.id,
        author_id=post.author_id,
        content=post.content,
        media_keys=list(post.media_keys),
        media_urls=urls,
        created_at=post.created_at,
        likes_count=likes_count,
    )


@router.post("/posts", response_model=PostOut, status_code=status.HTTP_201_CREATED)
async def create_post(
    body: CreatePostRequest,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
) -> PostOut:
    post = await posts_svc.create_post(
        session, author_id=user_id, content=body.content, media_keys=body.media_keys
    )
    await _publisher(request).publish(
        event_type="post.created",
        actor_id=user_id,
        data={
            "post_id": post.id,
            "author_id": post.author_id,
            "content_preview": post.content[:140],
            "media_keys": list(post.media_keys),
            "created_at": post.created_at,
        },
    )
    return await _to_out(post, _media(request))


@router.get("/posts/by-id/{post_id}", response_model=PostOut)
async def get_post_by_id(
    post_id: uuid.UUID,
    _user: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
) -> PostOut:
    try:
        post = await posts_svc.get_post(session, post_id)
    except posts_svc.PostNotFound as e:
        raise HTTPException(status_code=404, detail="post not found") from e
    count = await posts_svc.likes_count(session, post.id)
    return await _to_out(post, _media(request), count)


@router.get("/posts/{user_id}", response_model=PostList)
async def list_user_posts(
    user_id: uuid.UUID,
    _viewer: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
) -> PostList:
    rows, next_cursor = await posts_svc.list_user_posts(
        session, author_id=user_id, limit=limit, cursor=cursor
    )
    media = _media(request)
    counts = await posts_svc.likes_count_many(session, [p.id for p in rows])
    items = [await _to_out(p, media, counts.get(p.id, 0)) for p in rows]
    return PostList(items=items, next_cursor=next_cursor)


@router.post("/posts/{post_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def like(
    post_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
) -> Response:
    try:
        created, author_id = await posts_svc.like_post(
            session, user_id=user_id, post_id=post_id
        )
    except posts_svc.PostNotFound as e:
        raise HTTPException(status_code=404, detail="post not found") from e
    if created:
        await _publisher(request).publish(
            event_type="post.liked",
            actor_id=user_id,
            data={"post_id": post_id, "author_id": author_id, "liker_id": user_id},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/posts/{post_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def unlike(
    post_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
) -> Response:
    try:
        deleted, author_id = await posts_svc.unlike_post(
            session, user_id=user_id, post_id=post_id
        )
    except posts_svc.PostNotFound as e:
        raise HTTPException(status_code=404, detail="post not found") from e
    if deleted:
        await _publisher(request).publish(
            event_type="post.unliked",
            actor_id=user_id,
            data={"post_id": post_id, "author_id": author_id, "liker_id": user_id},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
