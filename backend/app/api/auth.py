from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.schemas import AuthMeResponse, LoginRequest, MessageResponse
from app.services.auth import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthMeResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> AuthMeResponse:
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    request.session["user_id"] = user.id
    return AuthMeResponse.model_validate(user)


@router.post("/logout", response_model=MessageResponse)
def logout(request: Request) -> MessageResponse:
    request.session.clear()
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=AuthMeResponse)
def me(current_user=Depends(get_current_user)) -> AuthMeResponse:
    return AuthMeResponse.model_validate(current_user)
