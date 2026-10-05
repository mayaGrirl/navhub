from datetime import datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import db_session, require_user
from app.models import User
from app.security import (
    check_totp,
    clear_failure,
    drop_session,
    hash_password,
    lock_until,
    mark_totp,
    new_session,
    new_totp_secret,
    plan_active,
    rate_limit,
    read_session,
    record_failure,
    totp_uri,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Creds(BaseModel):
    email: str
    password: str
    totp: str = ""


def _cookie(response: Response, token: str) -> None:
    response.set_cookie("nav_session", token, httponly=True, samesite="lax", max_age=60 * 60 * 12, path="/")


@router.post("/register")
def register(body: Creds, response: Response, db: Session = Depends(db_session)):
    if not rate_limit(f"reg:{body.email}", 5, 3600):
        raise HTTPException(status_code=429, detail="too many requests")
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(status_code=400, detail="email exists")
    user = User(email=str(body.email), password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = new_session(user.id, user.role, False)
    _cookie(response, token)
    return {"id": user.id, "email": user.email, "role": user.role, "plan": user.plan}


@router.post("/login")
def login(body: Creds, response: Response, db: Session = Depends(db_session)):
    email = str(body.email)
    if not rate_limit(f"login:{email}", 10, 900):
        raise HTTPException(status_code=429, detail="too many requests")
    if lock_until(email):
        raise HTTPException(status_code=423, detail="temporarily locked")
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(body.password, user.password_hash):
        record_failure(email)
        raise HTTPException(status_code=401, detail="invalid credentials")
    if user.totp_enabled and not check_totp(user.totp_secret, body.totp):
        record_failure(email)
        raise HTTPException(status_code=401, detail="totp required")
    clear_failure(email)
    totp_ok = user.totp_enabled
    token = new_session(user.id, user.role, totp_ok)
    _cookie(response, token)
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "plan": plan_active(user),
        "totp_enabled": user.totp_enabled,
        "totp_ok": totp_ok,
    }


@router.post("/logout")
def logout(response: Response, nav_session: str | None = Cookie(default=None)):
    drop_session(nav_session)
    response.delete_cookie("nav_session", path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(require_user), nav_session: str | None = Cookie(default=None)):
    data = read_session(nav_session) or {}
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "plan": plan_active(user),
        "plan_expires_at": user.plan_expires_at.isoformat() if user.plan_expires_at else None,
        "totp_enabled": user.totp_enabled,
        "totp_ok": data.get("totp_ok", False),
    }


@router.post("/totp/setup")
def totp_setup(user: User = Depends(require_user), db: Session = Depends(db_session)):
    secret = new_totp_secret()
    user.totp_secret = secret
    user.totp_enabled = False
    db.commit()
    return {"secret": secret, "uri": totp_uri(secret, user.email)}


class TotpBody(BaseModel):
    code: str


@router.post("/totp/confirm")
def totp_confirm(
    body: TotpBody,
    user: User = Depends(require_user),
    db: Session = Depends(db_session),
    nav_session: str | None = Cookie(default=None),
):
    if not check_totp(user.totp_secret, body.code):
        raise HTTPException(status_code=400, detail="invalid code")
    user.totp_enabled = True
    db.commit()
    mark_totp(nav_session or "")
    return {"ok": True}


@router.post("/plan/vip")
def grant_self_note():
    raise HTTPException(status_code=400, detail="vip is granted by an administrator until a payment provider is connected")
