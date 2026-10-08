import json
import time
from datetime import datetime, timedelta

from app.db import SessionLocal
from app.models import ActionLog, User
from app.security import read_session

KEEP = timedelta(days=90)
_last_purge = 0.0

EXACT = {
    ("POST", "/api/auth/register"): "register",
    ("POST", "/api/auth/login"): "login",
    ("POST", "/api/auth/console"): "admin_login",
    ("POST", "/api/auth/logout"): "logout",
    ("POST", "/api/auth/console/logout"): "admin_logout",
    ("PATCH", "/api/auth/profile"): "profile",
    ("POST", "/api/auth/password"): "password",
    ("POST", "/api/auth/console/password"): "admin_password",
    ("POST", "/api/auth/totp/setup"): "totp_setup",
    ("POST", "/api/auth/totp/confirm"): "totp_confirm",
    ("POST", "/api/auth/totp/switch"): "totp_switch",
    ("POST", "/api/auth/console/totp/setup"): "totp_setup",
    ("POST", "/api/auth/console/totp/confirm"): "totp_confirm",
    ("POST", "/api/auth/console/totp/switch"): "totp_switch",
    ("POST", "/api/auth/plan/vip"): "plan",
    ("POST", "/api/submissions"): "submit",
    ("POST", "/api/feedback"): "feedback",
    ("POST", "/api/uploads"): "upload",
    ("POST", "/api/proxy/token"): "proxy_token",
    ("POST", "/api/video/resolve"): "video",
    ("GET", "/api/search"): "search",
    ("POST", "/api/manage/admins"): "admin_create",
    ("POST", "/api/manage/uploads"): "admin_upload",
    ("POST", "/api/manage/ip-bans"): "ip_ban",
    ("DELETE", "/api/manage/ip-bans"): "ip_unban",
    ("PUT", "/api/manage/mail"): "mail_settings",
    ("POST", "/api/manage/mail/test"): "mail_test",
    ("POST", "/api/manage/mail/send"): "mail_send",
    ("PUT", "/api/manage/point-rule"): "point_rule",
    ("POST", "/api/manage/crawl/fetch"): "crawl_fetch",
    ("DELETE", "/api/manage/proxies"): "proxy_clear",
    ("DELETE", "/api/manage/proxy-sources"): "proxy_source_clear",
}

PREFIX = (
    ("/api/feedback/", "feedback_reply"),
    ("/api/manage/tabs", "tab"),
    ("/api/manage/categories", "category"),
    ("/api/manage/links", "link"),
    ("/api/manage/pages", "page"),
    ("/api/manage/ads", "ad"),
    ("/api/manage/news", "news"),
    ("/api/manage/announcements", "notice"),
    ("/api/manage/users", "user"),
    ("/api/manage/alerts", "alert"),
    ("/api/manage/crawl/jobs", "crawl"),
    ("/api/manage/crawl/items", "crawl_item"),
    ("/api/manage/levels", "level"),
    ("/api/manage/mail/tasks", "mail_task"),
    ("/api/manage/feedback", "feedback_admin"),
)

TRACK_ACTIONS = {"view", "locale", "tab", "notice", "search_web", "adult", "account"}


def session_user_id(cookie: str | None) -> int | None:
    data = read_session(cookie)
    if not data or not data.get("user_id"):
        return None
    try:
        return int(data["user_id"])
    except (TypeError, ValueError):
        return None


def action_for(method: str, path: str) -> str | None:
    path = path.rstrip("/") or "/"
    if path in {"/api/track", "/api/auth/captcha", "/api/auth/captcha/match"}:
        return None
    if path.startswith("/api/links/") and path.endswith("/click"):
        return "click"
    if path.startswith("/api/links/") and path.endswith("/mark"):
        return "mark"
    key = (method, path)
    if key in EXACT:
        return EXACT[key]
    if method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    for prefix, action in PREFIX:
        if path.startswith(prefix):
            return action
    if path.startswith("/api/manage/"):
        return "admin"
    if path.startswith("/api/auth/"):
        return "account"
    return None


def _email_hint(raw: bytes) -> str:
    try:
        data = json.loads(raw.decode("utf-8", "ignore") or "{}")
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    email = str(data.get("email") or "").strip().lower()[:255]
    return email if "@" in email else ""


def purge_old(db) -> None:
    db.query(ActionLog).filter(ActionLog.created_at < datetime.utcnow() - KEEP).delete(synchronize_session=False)


def add_log(db, user_id: int | None, email: str, role: str, action: str, ok: bool, detail: str, ip: str) -> None:
    global _last_purge
    db.add(ActionLog(
        user_id=user_id,
        email=(email or "")[:255],
        role=(role or "")[:20],
        action=(action or "")[:40],
        ok=bool(ok),
        detail=(detail or "")[:300],
        ip=(ip or "")[:64],
    ))
    now = time.time()
    if now - _last_purge > 3600:
        _last_purge = now
        purge_old(db)


def write_action(method: str, path: str, query: str, status: int, ip: str, user_id: int | None, email_hint: str) -> None:
    action = action_for(method, path)
    if not action:
        return
    detail = f"{method} {path}"
    if action == "search" and query:
        from urllib.parse import parse_qs
        text = (parse_qs(query).get("q") or [""])[0].strip()
        detail = (text or query)[:300]
    db = SessionLocal()
    try:
        user = db.get(User, user_id) if user_id else None
        if not user and email_hint:
            user = db.query(User).filter(User.email == email_hint).one_or_none()
        role = user.role if user else ("admin" if action.startswith("admin") else "")
        add_log(
            db,
            user.id if user else None,
            user.email if user else email_hint,
            role,
            action,
            status < 400,
            detail,
            ip,
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def write_track(action: str, detail: str, ip: str, user_id: int | None) -> None:
    if action not in TRACK_ACTIONS:
        return
    db = SessionLocal()
    try:
        user = db.get(User, user_id) if user_id else None
        add_log(
            db,
            user.id if user else None,
            user.email if user else "",
            user.role if user else "",
            action,
            True,
            detail,
            ip,
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
