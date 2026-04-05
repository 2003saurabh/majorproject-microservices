from fastapi import Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from orders_app.config import get_settings

settings = get_settings()
bearer = HTTPBearer(auto_error=True)


def _decode(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise ValueError("not an access token")
        return payload
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


class CurrentUser:
    def __init__(self, user_id: int, email: str, is_superuser: bool):
        self.user_id      = user_id
        self.email        = email
        self.is_superuser = is_superuser


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> CurrentUser:
    payload = _decode(credentials.credentials)
    return CurrentUser(
        user_id=int(payload["sub"]),
        email=payload.get("email", ""),
        is_superuser=payload.get("su", False),
    )


def get_superuser(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    return user


def decode_ws_token(token: str) -> CurrentUser:
    """Used in WebSocket handshake where HTTPBearer isn't available."""
    payload = _decode(token)
    return CurrentUser(
        user_id=int(payload["sub"]),
        email=payload.get("email", ""),
        is_superuser=payload.get("su", False),
    )
