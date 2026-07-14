from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.core.logger import log_security_event
from app.core.security import decode_access_token
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService, VALID_ROLES
from app.core.telemetry_context import update_request_context


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)
auth_service = AuthService()
audit_service = AuditService()


def get_request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _raise_unauthorized(
    request: Request,
    error_message: str,
    username: str | None = None,
) -> None:
    request_id = get_request_id(request)
    log_security_event(
        request_id=request_id,
        username=username,
        role=None,
        action="auth_token_invalid",
        status="invalid",
        error_message=error_message,
    )
    audit_service.log_action(
        request_id=request_id,
        session_id=None,
        username=username,
        role=None,
        action="permission_denied",
        resource_type="api",
        resource_id=request.url.path,
        status="denied",
        detail=error_message,
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=error_message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
) -> dict:
    if not token:
        _raise_unauthorized(request, "缺少 Bearer 访问令牌")

    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        _raise_unauthorized(request, str(exc))

    username = payload.get("sub")
    if not username:
        _raise_unauthorized(request, "访问令牌缺少用户标识")

    user = auth_service.get_user_by_username(str(username))
    if user is None or not user.get("is_active"):
        _raise_unauthorized(
            request,
            "用户不存在或已停用",
            username=str(username),
        )
    update_request_context(
        username=user.get("username"),
        role=user.get("role"),
    )
    return user


def require_roles(*roles: str) -> Callable:
    allowed_roles = {role.lower() for role in roles}
    invalid_roles = allowed_roles - VALID_ROLES
    if invalid_roles:
        raise ValueError(f"未知角色: {sorted(invalid_roles)}")

    def dependency(
        request: Request,
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        user_role = current_user.get("role")
        if user_role not in allowed_roles:
            request_id = get_request_id(request)
            detail = (
                f"角色 {user_role} 无权访问 {request.url.path}；"
                f"允许角色: {sorted(allowed_roles)}"
            )
            log_security_event(
                request_id=request_id,
                username=current_user.get("username"),
                role=user_role,
                action="permission_denied",
                status="denied",
                error_message=detail,
            )
            audit_service.log_action(
                request_id=request_id,
                session_id=None,
                username=current_user.get("username"),
                role=user_role,
                action="permission_denied",
                resource_type="api",
                resource_id=request.url.path,
                status="denied",
                detail=detail,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail,
            )
        return current_user

    return dependency
