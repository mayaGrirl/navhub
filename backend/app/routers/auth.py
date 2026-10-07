from datetime import datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import db_session, require_user
from app.models import AuthLog, IpBan, User
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
    issue_captcha,
    issue_match,
    take_captcha,
    take_match,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Creds(BaseModel):
    email: str
    password: str
    totp: str = ""
    captcha_id: str = ""
    captcha_progress: int = 0


class ProfileBody(BaseModel):
    display_name: str = ""


class PasswordBody(BaseModel):
    current_password: str
    new_password: str


def _cookie(response: Response, token: str) -> None:
    response.set_cookie("nav_session", token, httponly=True, samesite="lax", max_age=60 * 60 * 12, path="/")


def _console_cookie(response: Response, token: str) -> None:
    response.set_cookie("nav_console", token, httponly=True, samesite="lax", max_age=60 * 60 * 12, path="/")


@router.post("/captcha")
def captcha():
    if not rate_limit("captcha", 30, 60):
        raise HTTPException(status_code=429, detail="too many requests")
    return {"id": issue_captcha()}


@router.post("/captcha/match")
def captcha_match():
    if not rate_limit("captcha", 30, 60):
        raise HTTPException(status_code=429, detail="too many requests")
    token, target, shape = issue_match()
    return {"id": token, "target": target, "shape": shape}


def _email(value: str) -> str:
    return value.strip().lower()


@router.post("/register")
def register(body: Creds, response: Response, db: Session = Depends(db_session)):
    if not take_captcha(body.captcha_id, body.captcha_progress):
        raise HTTPException(status_code=400, detail="captcha required")
    email = _email(body.email)
    if not rate_limit(f"reg:{email}", 5, 3600):
        raise HTTPException(status_code=429, detail="too many requests")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=400, detail="email exists")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="email exists")
    db.refresh(user)
    token = new_session(user.id, user.role, False)
    _cookie(response, token)
    return {"id": user.id, "email": user.email, "role": user.role, "plan": user.plan}


@router.post("/login")
def login(body: Creds, request: Request, response: Response, db: Session = Depends(db_session)):
    email = _email(body.email)
    if not rate_limit(f"login:{email}", 10, 900):
        raise HTTPException(status_code=429, detail="too many requests")
    if lock_until(email):
        raise HTTPException(status_code=423, detail="temporarily locked")
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(body.password, user.password_hash):
        record_failure(email)
        raise HTTPException(status_code=401, detail="invalid credentials")
    ip = (request.client.host if request.client else "")[:64]
    if user.banned or (ip and db.scalar(select(IpBan.id).where(IpBan.ip == ip))):
        raise HTTPException(status_code=403, detail="banned")
    user.last_ip = ip
    db.add(AuthLog(user_id=user.id, kind="login"))
    db.commit()
    clear_failure(email)
    token = new_session(user.id, user.role, False)
    _cookie(response, token)
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "plan": plan_active(user),
        "totp_enabled": user.totp_enabled,
        "totp_ok": False,
    }


@router.post("/console")
def console_login(body: Creds, request: Request, response: Response, db: Session = Depends(db_session)):
    email = _email(body.email)
    if not rate_limit(f"console:{email}", 10, 900):
        raise HTTPException(status_code=429, detail="too many requests")
    if lock_until(email):
        raise HTTPException(status_code=423, detail="temporarily locked")
    if not take_match(body.captcha_id, body.captcha_progress):
        raise HTTPException(status_code=400, detail="captcha required")
    user = db.scalar(select(User).where(User.email == email))
    if not user or user.role != "admin" or not verify_password(body.password, user.password_hash):
        record_failure(email)
        raise HTTPException(status_code=401, detail="invalid credentials")
    if user.totp_enabled and not check_totp(user.totp_secret, body.totp):
        record_failure(email)
        raise HTTPException(status_code=401, detail="totp required")
    ip = (request.client.host if request.client else "")[:64]
    if user.banned or (ip and db.scalar(select(IpBan.id).where(IpBan.ip == ip))):
        raise HTTPException(status_code=403, detail="banned")
    user.last_ip = ip
    db.add(AuthLog(user_id=user.id, kind="login"))
    db.commit()
    clear_failure(email)
    token = new_session(user.id, user.role, user.totp_enabled)
    _console_cookie(response, token)
    return {"id": user.id, "email": user.email, "totp_enabled": user.totp_enabled, "totp_ok": user.totp_enabled}


def _console_actor(
    db: Session,
    nav_console: str | None,
) -> tuple[User, dict]:
    data = read_session(nav_console)
    if not data:
        raise HTTPException(status_code=401, detail="login required")
    user = db.get(User, data["user_id"])
    if not user or user.role != "admin":
        raise HTTPException(status_code=401, detail="login required")
    return user, data


@router.get("/console/me")
def console_me(db: Session = Depends(db_session), nav_console: str | None = Cookie(default=None)):
    user, data = _console_actor(db, nav_console)
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "totp_enabled": user.totp_enabled,
        "totp_bound": bool(user.totp_secret),
        "totp_ok": data.get("totp_ok", False),
    }


@router.post("/console/logout")
def console_logout(response: Response, nav_console: str | None = Cookie(default=None)):
    drop_session(nav_console)
    response.delete_cookie("nav_console", path="/")
    return {"ok": True}


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
        "display_name": user.display_name,
        "role": user.role,
        "plan": plan_active(user),
        "plan_expires_at": user.plan_expires_at.isoformat() if user.plan_expires_at else None,
        "totp_enabled": user.totp_enabled,
        "totp_bound": bool(user.totp_secret),
        "totp_ok": data.get("totp_ok", False),
    }


@router.patch("/profile")
def update_profile(body: ProfileBody, user: User = Depends(require_user), db: Session = Depends(db_session)):
    name = body.display_name.strip()[:40]
    user.display_name = name
    db.commit()
    return {"display_name": user.display_name}


@router.post("/console/password")
def console_change_password(
    body: PasswordBody,
    db: Session = Depends(db_session),
    nav_console: str | None = Cookie(default=None),
):
    user, _data = _console_actor(db, nav_console)
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="invalid credentials")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="password too short")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}


@router.post("/password")
def change_password(body: PasswordBody, user: User = Depends(require_user), db: Session = Depends(db_session)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="invalid credentials")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="password too short")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}


class TotpBody(BaseModel):
    code: str


class TotpSwitch(BaseModel):
    enabled: bool
    code: str = ""


@router.post("/console/totp/setup")
def console_totp_setup(db: Session = Depends(db_session), nav_console: str | None = Cookie(default=None)):
    user, _data = _console_actor(db, nav_console)
    secret = new_totp_secret()
    user.totp_secret = secret
    user.totp_enabled = False
    db.commit()
    return {"secret": secret, "uri": totp_uri(secret, user.email)}


@router.post("/console/totp/confirm")
def console_totp_confirm(
    body: TotpBody,
    db: Session = Depends(db_session),
    nav_console: str | None = Cookie(default=None),
):
    user, _data = _console_actor(db, nav_console)
    if not check_totp(user.totp_secret, body.code):
        raise HTTPException(status_code=400, detail="invalid code")
    user.totp_enabled = True
    db.commit()
    mark_totp(nav_console or "")
    return {"ok": True}


@router.post("/console/totp/switch")
def console_totp_switch(
    body: TotpSwitch,
    db: Session = Depends(db_session),
    nav_console: str | None = Cookie(default=None),
):
    user, _data = _console_actor(db, nav_console)
    if body.enabled:
        if not user.totp_secret or not check_totp(user.totp_secret, body.code):
            raise HTTPException(status_code=400, detail="invalid code")
        user.totp_enabled = True
        db.commit()
        mark_totp(nav_console or "")
    else:
        user.totp_enabled = False
        db.commit()
    return {"totp_enabled": user.totp_enabled, "totp_bound": bool(user.totp_secret)}


@router.post("/totp/setup")
def totp_setup(user: User = Depends(require_user), db: Session = Depends(db_session)):
    secret = new_totp_secret()
    user.totp_secret = secret
    user.totp_enabled = False
    db.commit()
    return {"secret": secret, "uri": totp_uri(secret, user.email)}


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


@router.post("/totp/switch")
def totp_switch(
    body: TotpSwitch,
    user: User = Depends(require_user),
    db: Session = Depends(db_session),
    nav_session: str | None = Cookie(default=None),
):
    if body.enabled:
        if not user.totp_secret or not check_totp(user.totp_secret, body.code):
            raise HTTPException(status_code=400, detail="invalid code")
        user.totp_enabled = True
        db.commit()
        mark_totp(nav_session or "")
    else:
        user.totp_enabled = False
        db.commit()
    return {"totp_enabled": user.totp_enabled, "totp_bound": bool(user.totp_secret)}


@router.post("/plan/vip")
def grant_self_note():
    raise HTTPException(status_code=400, detail="vip is granted by an administrator until a payment provider is connected")
