from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.deps import get_request_id, require_roles
from app.core.logger import log_security_event
from app.core.security import create_access_token
from app.schemas.auth import (
    CreateUserRequest,
    CreateUserResponse,
    LoginRequest,
    LoginResponse,
    UserInfo,
)
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
auth_service = AuthService()
audit_service = AuditService()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request):
    request_id = get_request_id(request)
    user = auth_service.authenticate_user(
        username=payload.username,
        password=payload.password,
    )
    if user is None:
        log_security_event(
            request_id=request_id,
            username=payload.username,
            role=None,
            action="login_failed",
            status="failed",
            error_message="用户名、密码错误或用户已停用",
        )
        audit_service.log_action(
            request_id=request_id,
            session_id=None,
            username=payload.username,
            role=None,
            action="login_failed",
            resource_type="auth",
            resource_id=payload.username,
            status="failed",
            detail="用户名、密码错误或用户已停用",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名、密码错误或用户已停用",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token({
        "sub": user["username"],
        "role": user["role"],
    })
    log_security_event(
        request_id=request_id,
        username=user["username"],
        role=user["role"],
        action="login_success",
        status="success",
    )
    audit_service.log_action(
        request_id=request_id,
        session_id=None,
        username=user["username"],
        role=user["role"],
        action="login_success",
        resource_type="auth",
        resource_id=user["username"],
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/users", response_model=CreateUserResponse)
def create_user(
    payload: CreateUserRequest,
    request: Request,
    current_user: dict = Depends(require_roles("admin")),
):
    try:
        user = auth_service.create_user(
            username=payload.username,
            password=payload.password,
            role=payload.role,
        )
    except ValueError as exc:
        status_code = (
            status.HTTP_409_CONFLICT
            if "已存在" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    audit_service.log_action(
        request_id=get_request_id(request),
        session_id=None,
        username=current_user["username"],
        role=current_user["role"],
        action="user_create",
        resource_type="user",
        resource_id=user["username"],
    )
    return user


@router.get("/users", response_model=list[UserInfo])
def list_users(
    current_user: dict = Depends(require_roles("admin")),
):
    return auth_service.list_users()
