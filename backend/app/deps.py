from fastapi import Cookie, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import read_session
from app.seed import ensure_gate


def db_session(db: Session = Depends(get_db)) -> Session:
    return db


def current_user(
    db: Session = Depends(get_db),
    nav_session: str | None = Cookie(default=None),
) -> User | None:
    data = read_session(nav_session)
    if not data:
        return None
    return db.get(User, data["user_id"])


def require_user(user: User | None = Depends(current_user)) -> User:
    if not user:
        raise HTTPException(status_code=401, detail="login required")
    if user.banned:
        raise HTTPException(status_code=403, detail="banned")
    return user


def _admin_from_gate(
    db: Session,
    nav_console: str | None,
    x_admin_gate: str | None,
) -> tuple[User, dict]:
    if not x_admin_gate or x_admin_gate != ensure_gate():
        raise HTTPException(status_code=404, detail="not found")
    data = read_session(nav_console)
    if not data:
        raise HTTPException(status_code=401, detail="login required")
    user = db.get(User, data["user_id"])
    if not user or user.role != "admin" or user.banned:
        raise HTTPException(status_code=404, detail="not found")
    if user.totp_enabled and not data.get("totp_ok"):
        raise HTTPException(status_code=401, detail="totp required")
    return user, data


def require_admin_setup(
    db: Session = Depends(get_db),
    nav_console: str | None = Cookie(default=None),
    x_admin_gate: str | None = Header(default=None),
) -> User:
    user, _data = _admin_from_gate(db, nav_console, x_admin_gate)
    return user


def require_admin(
    db: Session = Depends(get_db),
    nav_console: str | None = Cookie(default=None),
    x_admin_gate: str | None = Header(default=None),
) -> User:
    user, _data = _admin_from_gate(db, nav_console, x_admin_gate)
    return user
