from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.core.security import create_token, verify_password
from app.db.models import User
from app.db.session import get_db
from app.services import audit, serializers

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username.strip().lower()).first()
    if user is None or not user.active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Username or password is incorrect")
    audit.committed_append(db, "auth.login", {"user_id": user.id, "username": user.username})
    return {"access_token": create_token(user.id, user.access_role), "token_type": "bearer",
            "user": serializers.user(user)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return serializers.user(user)
