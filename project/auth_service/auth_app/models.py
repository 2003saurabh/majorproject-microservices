from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    ForeignKey, func, Index
)
from sqlalchemy.orm import relationship
from auth_app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_auth_users_email", "email"),
        {"schema": "auth"},
    )

    id             = Column(Integer, primary_key=True, index=True)
    email          = Column(String(255), unique=True, nullable=False)
    hashed_password= Column(String(255), nullable=False)
    full_name      = Column(String(255), nullable=True)
    is_active      = Column(Boolean, default=True, nullable=False)
    is_verified    = Column(Boolean, default=False, nullable=False)  # email verified
    is_superuser   = Column(Boolean, default=False, nullable=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), onupdate=func.now())

    otps = relationship("OTPCode", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User id={self.id} email={self.email}>"


class OTPCode(Base):
    """
    Stores short-lived OTP codes for:
      - purpose='verify'  → email verification after registration
      - purpose='reset'   → password reset
      - purpose='login'   → passwordless login (magic code)
    """
    __tablename__ = "otp_codes"
    __table_args__ = {"schema": "auth"}

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("auth.users.id"), nullable=False)
    code       = Column(String(10), nullable=False)
    purpose    = Column(String(20), nullable=False)   # verify | reset | login
    is_used    = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="otps")
