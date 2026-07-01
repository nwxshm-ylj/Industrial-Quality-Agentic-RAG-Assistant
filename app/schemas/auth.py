from typing import Literal

from pydantic import BaseModel, Field


RoleType = Literal["admin", "engineer", "viewer"]


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)


class UserInfo(BaseModel):
    username: str
    role: RoleType
    is_active: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8)
    role: RoleType = "viewer"


class CreateUserResponse(UserInfo):
    pass
