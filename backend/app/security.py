import hashlib
import random
import secrets
from datetime import datetime, timedelta

import time

import pyotp
import redis

from app.config import settings

rds = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return secrets.compare_digest(check, digest)


def new_session(user_id: int, role: str, totp_ok: bool) -> str:
    token = secrets.token_urlsafe(32)
    rds.setex(
        f"session:{token}",
        60 * 60 * 12,
        f"{user_id}|{role}|{int(totp_ok)}",
    )
    return token


def read_session(token: str | None) -> dict | None:
    if not token:
        return None
    raw = rds.get(f"session:{token}")
    if not raw:
        return None
    user_id, role, totp_ok = raw.split("|")
    return {"user_id": int(user_id), "role": role, "totp_ok": totp_ok == "1"}


def touch_session(token: str | None, seconds: int = 60 * 60 * 24 * 7) -> None:
    if token and rds.get(f"session:{token}"):
        rds.expire(f"session:{token}", seconds)


def drop_session(token: str | None) -> None:
    if token:
        rds.delete(f"session:{token}")


def mark_totp(token: str) -> None:
    data = read_session(token)
    if not data:
        return
    rds.setex(f"session:{token}", 60 * 60 * 12, f"{data['user_id']}|{data['role']}|1")


def client_ip(request) -> str:
    peer = (request.client.host if request.client else "") or ""
    if peer in {"127.0.0.1", "::1"}:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()[:64]
    return peer[:64]


def checked_image(raw: bytes) -> str:
    if not raw or len(raw) > 2 * 1024 * 1024:
        raise ValueError("image required")
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if raw.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return ".webp"
    raise ValueError("image required")


def rate_limit(key: str, limit: int, window: int) -> bool:
    count = rds.incr(key)
    if count == 1 or rds.ttl(key) < 0:
        rds.expire(key, window)
    return count <= limit


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="NEXA")


def totp_qr(uri: str) -> str:
    import segno

    return segno.make(uri, error="m").svg_inline(scale=4, border=2, dark="#111827", light="#ffffff")


def check_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def plan_active(user) -> str:
    if user.plan == "vip" and user.plan_expires_at and user.plan_expires_at < datetime.utcnow():
        return "free"
    return user.plan


def month_key(user_id: int) -> str:
    return f"submit:{user_id}:{datetime.utcnow():%Y%m}"


def quota_for(plan: str) -> int:
    return settings.vip_monthly_quota if plan == "vip" else settings.free_monthly_quota


def lock_until(email: str) -> bool:
    return rds.exists(f"lock:{email}") == 1


def record_failure(email: str) -> None:
    key = f"fail:{email}"
    count = rds.incr(key)
    if count == 1:
        rds.expire(key, 900)
    if count >= 5:
        rds.setex(f"lock:{email}", 900, "1")


def issue_captcha() -> str:
    token = secrets.token_urlsafe(18)
    rds.setex(f"captcha:{token}", 120, str(time.time()))
    return token


def take_captcha(token: str, progress: int) -> bool:
    if not token:
        return False
    key = f"captcha:{token}"
    raw = rds.get(key)
    if not raw:
        return False
    rds.delete(key)
    try:
        elapsed = time.time() - float(raw)
    except ValueError:
        return False
    return 0.45 <= elapsed <= 120 and progress >= 96


def issue_match() -> tuple[str, int, str]:
    token = secrets.token_urlsafe(18)
    target = random.randint(28, 86)
    shape = random.choice(["round", "circle", "diamond", "pill", "hex"])
    rds.setex(f"match:{token}", 120, f"{time.time()}|{target}")
    return token, target, shape


def take_match(token: str, progress: int) -> bool:
    if not token:
        return False
    key = f"match:{token}"
    raw = rds.get(key)
    if not raw:
        return False
    rds.delete(key)
    try:
        started, target = raw.split("|")
        elapsed = time.time() - float(started)
    except ValueError:
        return False
    return 0.05 <= elapsed <= 120 and abs(int(progress) - int(target)) <= 6


def clear_failure(email: str) -> None:
    rds.delete(f"fail:{email}", f"lock:{email}")
