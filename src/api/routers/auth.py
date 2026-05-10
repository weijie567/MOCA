from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.auth import DemoTokenRequest, LoginRequest, TokenResponse, UserResponse
from src.api.schemas.common import ApiResponse, ErrorDetail, UNAUTHORIZED
from src.auth.jwt import create_access_token, verify_password
from src.auth.permissions import get_current_user
from src.config import settings
from src.db.models import User
from src.db.session import get_session


router = APIRouter(tags=["auth"])


def _success(data: object, request: Request) -> ApiResponse:
    return ApiResponse(success=True, data=data, trace_id=request.state.trace_id)


@router.post("/login", response_model=ApiResponse)
async def login(payload: LoginRequest, request: Request, session: AsyncSession = Depends(get_session)) -> ApiResponse:
    stmt = select(User).where(User.username == payload.username)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": UNAUTHORIZED, "message": "Invalid username or password"},
        )

    token = create_access_token(
        {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
            "tenant_id": str(user.tenant_id),
        }
    )
    return _success(TokenResponse(access_token=token).model_dump(), request)


@router.get("/me", response_model=ApiResponse)
async def me(request: Request, user: User = Security(get_current_user)) -> ApiResponse:
    return _success(UserResponse.model_validate(user).model_dump(mode="json"), request)


@router.post("/demo-token", response_model=ApiResponse)
async def demo_token(
    payload: DemoTokenRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    if not settings.enable_demo_auth:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorDetail(code="FORBIDDEN", message="Demo auth is disabled").model_dump(),
        )

    stmt = select(User).where(User.username == payload.username)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorDetail(code=UNAUTHORIZED, message="User not found").model_dump(),
        )

    token = create_access_token(
        {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
            "tenant_id": str(user.tenant_id),
        }
    )
    return _success(TokenResponse(access_token=token).model_dump(), request)
