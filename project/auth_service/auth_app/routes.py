from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from auth_app import crud, schemas
from auth_app.database import get_db
from auth_app.deps import get_current_user, get_current_verified_user
from auth_app.email import send_otp_email
from auth_app.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from auth_app import models

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# REGISTER
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/auth/register", response_model=schemas.UserResponse, status_code=201, tags=["Auth"])
async def register(
    data: schemas.UserRegister,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Register a new user. Sends a verification OTP to the provided email.
    The user must verify their email before accessing protected routes.
    """
    if crud.get_user_by_email(db, data.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    user = crud.create_user(db, data)

    # Issue verification OTP and send email in background
    otp_record = crud.create_otp(db, user.id, "verify")
    background_tasks.add_task(send_otp_email, user.email, otp_record.code, "verify")

    return user


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=schemas.TokenResponse, tags=["Auth"])
def login(data: schemas.UserLogin, db: Session = Depends(get_db)):
    """
    Login with email + password. Returns access + refresh tokens.
    Note: works even if email is unverified — but protected routes require verification.
    """
    user = crud.get_user_by_email(db, data.email)
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    return schemas.TokenResponse(
        access_token=create_access_token(user.id, user.email, user.is_superuser),
        refresh_token=create_refresh_token(user.id),
        user=schemas.UserResponse.model_validate(user),
    )


# ─────────────────────────────────────────────────────────────────────────────
# TOKEN REFRESH
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/auth/refresh", response_model=schemas.AccessTokenResponse, tags=["Auth"])
def refresh_token(data: schemas.RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a refresh token for a new access token."""
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = crud.get_user_by_id(db, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    return schemas.AccessTokenResponse(
        access_token=create_access_token(user.id, user.email, user.is_superuser)
    )


# ─────────────────────────────────────────────────────────────────────────────
# TOKEN VERIFY  (used by other microservices)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/auth/verify-token", response_model=schemas.TokenVerifyResponse, tags=["Auth"])
def verify_token(data: schemas.RefreshRequest):
    """
    Validate an access token. Called by Orders / Items services to confirm identity.
    Pass the token in the request body as { "refresh_token": "<access_token>" }.
    """
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "access":
        return schemas.TokenVerifyResponse(valid=False)

    return schemas.TokenVerifyResponse(
        valid=True,
        user_id=int(payload["sub"]),
        email=payload.get("email"),
        is_superuser=payload.get("su", False),
    )


# ─────────────────────────────────────────────────────────────────────────────
# OTP — EMAIL VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/auth/otp/send-verification", status_code=202, tags=["OTP"])
async def send_verification_otp(
    data: schemas.OTPRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Resend email verification OTP."""
    user = crud.get_user_by_email(db, data.email)
    if not user:
        # Don't reveal whether email exists
        return {"message": "If that email is registered, a code has been sent."}
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    otp_record = crud.create_otp(db, user.id, "verify")
    background_tasks.add_task(send_otp_email, user.email, otp_record.code, "verify")
    return {"message": "Verification code sent. Check your inbox."}


@router.post("/auth/otp/verify-email", response_model=schemas.TokenResponse, tags=["OTP"])
def verify_email(data: schemas.OTPVerify, db: Session = Depends(get_db)):
    """
    Verify email with OTP. On success, returns tokens — user is logged in immediately.
    data.purpose must be 'verify'.
    """
    if data.purpose != "verify":
        raise HTTPException(status_code=400, detail="Purpose must be 'verify'")

    user = crud.get_user_by_email(db, data.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    otp = crud.verify_otp(db, user.id, data.code, "verify")
    if not otp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    crud.mark_verified(db, user)

    return schemas.TokenResponse(
        access_token=create_access_token(user.id, user.email, user.is_superuser),
        refresh_token=create_refresh_token(user.id),
        user=schemas.UserResponse.model_validate(user),
    )


# ─────────────────────────────────────────────────────────────────────────────
# OTP — PASSWORD RESET
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/auth/otp/forgot-password", status_code=202, tags=["OTP"])
async def forgot_password(
    data: schemas.OTPRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Request a password-reset OTP. Always returns 202 to avoid email enumeration."""
    user = crud.get_user_by_email(db, data.email)
    if user and user.is_active:
        otp_record = crud.create_otp(db, user.id, "reset")
        background_tasks.add_task(send_otp_email, user.email, otp_record.code, "reset")
    return {"message": "If that email is registered, a reset code has been sent."}


@router.post("/auth/otp/reset-password", tags=["OTP"])
def reset_password(data: schemas.PasswordResetConfirm, db: Session = Depends(get_db)):
    """Confirm password reset with OTP + new password."""
    user = crud.get_user_by_email(db, data.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    otp = crud.verify_otp(db, user.id, data.code, "reset")
    if not otp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    crud.set_password(db, user, data.new_password)
    return {"message": "Password reset successfully. You can now log in."}


# ─────────────────────────────────────────────────────────────────────────────
# OTP — PASSWORDLESS LOGIN (magic code)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/auth/otp/send-login", status_code=202, tags=["OTP"])
async def send_login_otp(
    data: schemas.OTPRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Send a magic login code — passwordless authentication."""
    user = crud.get_user_by_email(db, data.email)
    if user and user.is_active:
        otp_record = crud.create_otp(db, user.id, "login")
        background_tasks.add_task(send_otp_email, user.email, otp_record.code, "login")
    return {"message": "If that email is registered, a login code has been sent."}


@router.post("/auth/otp/login", response_model=schemas.TokenResponse, tags=["OTP"])
def otp_login(data: schemas.OTPVerify, db: Session = Depends(get_db)):
    """Complete passwordless login with the magic code."""
    if data.purpose != "login":
        raise HTTPException(status_code=400, detail="Purpose must be 'login'")

    user = crud.get_user_by_email(db, data.email)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    otp = crud.verify_otp(db, user.id, data.code, "login")
    if not otp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    # Auto-verify email on successful OTP login
    if not user.is_verified:
        crud.mark_verified(db, user)

    return schemas.TokenResponse(
        access_token=create_access_token(user.id, user.email, user.is_superuser),
        refresh_token=create_refresh_token(user.id),
        user=schemas.UserResponse.model_validate(user),
    )


# ─────────────────────────────────────────────────────────────────────────────
# USER — ME endpoints (protected)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/users/me", response_model=schemas.UserResponse, tags=["Users"])
def get_me(current_user: models.User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user


@router.patch("/users/me", response_model=schemas.UserResponse, tags=["Users"])
def update_me(
    data: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Update name and/or password for the currently authenticated user."""
    return crud.update_user(db, current_user, data)
