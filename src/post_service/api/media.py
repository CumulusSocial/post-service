from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from post_service.deps import get_current_user_id
from post_service.schemas.post import PresignRequest, PresignResponse
from post_service.services.media import MediaService

router = APIRouter()


@router.post("/media/presign", response_model=PresignResponse)
async def presign(
    body: PresignRequest,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    request: Request,
) -> PresignResponse:
    media: MediaService = request.app.state.media
    try:
        result = await media.presign_put(
            user_id=user_id,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return PresignResponse(
        upload_url=result.upload_url,
        media_key=result.media_key,
        expires_in=result.expires_in,
    )
