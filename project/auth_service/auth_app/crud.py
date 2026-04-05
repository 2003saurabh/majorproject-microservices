from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from auth_app import models, schemas
from auth_app.security import hash_password, generate_otp, otp_expiry


# ── User CRUD ─────────────────────────────────────────────────────────────────

def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()


def create_user(db: Session, data: schemas.UserRegister) -> models.User:
    user = models.User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: models.User, data: schemas.UserUpdate) -> models.User:
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.password is not None:
        user.hashed_password = hash_password(data.password)
    db.commit()
    db.refresh(user)
    return user


def mark_verified(db: Session, user: models.User) -> models.User:
    user.is_verified = True
    db.commit()
    db.refresh(user)
    return user


def set_password(db: Session, user: models.User, new_password: str) -> models.User:
    user.hashed_password = hash_password(new_password)
    db.commit()
    db.refresh(user)
    return user


# ── OTP CRUD ──────────────────────────────────────────────────────────────────

def invalidate_old_otps(db: Session, user_id: int, purpose: str) -> None:
    """Mark all unused OTPs for this user+purpose as used before issuing a new one."""
    db.query(models.OTPCode).filter(
        models.OTPCode.user_id == user_id,
        models.OTPCode.purpose == purpose,
        models.OTPCode.is_used == False,
    ).update({"is_used": True})
    db.commit()


def create_otp(db: Session, user_id: int, purpose: str) -> models.OTPCode:
    invalidate_old_otps(db, user_id, purpose)
    otp = models.OTPCode(
        user_id=user_id,
        code=generate_otp(),
        purpose=purpose,
        expires_at=otp_expiry(),
    )
    db.add(otp)
    db.commit()
    db.refresh(otp)
    return otp


def verify_otp(db: Session, user_id: int, code: str, purpose: str) -> Optional[models.OTPCode]:
    now = datetime.now(timezone.utc)
    otp = (
        db.query(models.OTPCode)
        .filter(
            models.OTPCode.user_id  == user_id,
            models.OTPCode.code     == code,
            models.OTPCode.purpose  == purpose,
            models.OTPCode.is_used  == False,
            models.OTPCode.expires_at > now,
        )
        .first()
    )
    if otp:
        otp.is_used = True
        db.commit()
    return otp
