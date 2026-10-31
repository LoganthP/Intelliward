from fastapi import Depends, Header, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_token
from app.db.models import User
from app.db.session import get_db

bearer = HTTPBearer(auto_error=False)


def _user_from_token(db: Session, token: str | None) -> User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue")
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Sign in again.")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is disabled")
    return user


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    return _user_from_token(db, cred.credentials if cred else None)


def user_from_query(token: str | None = Query(None), db: Session = Depends(get_db)) -> User:
    """For <img>/<video> stream URLs that cannot send headers."""
    return _user_from_token(db, token)


def require(*roles: str):
    def checker(user: User = Depends(current_user)) -> User:
        if user.access_role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot perform this action")
        return user
    return checker


def internal_auth(x_internal_token: str = Header(..., alias="X-Internal-Token")):
    if x_internal_token != settings.internal_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal token")
    return True


staff_scope = require("admin", "supervisor", "staff")
supervisor_up = require("admin", "supervisor")
admin_only = require("admin")
