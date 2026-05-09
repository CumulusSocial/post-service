from __future__ import annotations

import uuid
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from post_service.security.jwt_verify import verify

bearer = HTTPBearer(auto_error=True)


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> uuid.UUID:
    try:
        claims = await verify(credentials.credentials, client=client)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
        ) from e
    return uuid.UUID(claims["sub"])
