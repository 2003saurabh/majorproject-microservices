from pydantic import BaseModel, EmailStr, Field, model_validator
from datetime import datetime
from typing import Optional


# ── User schemas ─────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email:     EmailStr
    password:  str  = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class UserResponse(BaseModel):
    id:          int
    email:       str
    full_name:   Optional[str]
    is_active:   bool
    is_verified: bool
    is_superuser:bool
    created_at:  datetime
    updated_at:  Optional[datetime]

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    password:  Optional[str] = Field(None, min_length=8, max_length=128)


# ── Token schemas ─────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    user:          UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"


class TokenVerifyResponse(BaseModel):
    valid:   bool
    user_id: Optional[int]  = None
    email:   Optional[str]  = None
    is_superuser: Optional[bool] = None


# ── OTP schemas ───────────────────────────────────────────────────────────────

class OTPRequest(BaseModel):
    email: EmailStr


class OTPVerify(BaseModel):
    email:   EmailStr
    code:    str = Field(..., min_length=4, max_length=10)
    purpose: str = Field(..., pattern="^(verify|reset|login)$")


class PasswordResetConfirm(BaseModel):
    email:        EmailStr
    code:         str = Field(..., min_length=4, max_length=10)
    new_password: str = Field(..., min_length=8, max_length=128)
