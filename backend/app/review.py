import ipaddress
import random
import threading
from datetime import datetime
from urllib.parse import urlparse

import httpx
from sqlalchemy import select

from app.db import SessionLocal
from app.models import AdminAlert, Link, PointRule, User
from app.security import rds
from app.urls import norm_url


def _private(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local"):
        return True
    try:
        return ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _opens(url: str) -> bool:
    if _private(url):
        return False
    try:
        with httpx.Client(follow_redirects=True, timeout=8) as client:
            response = client.get(url, headers={"User-Agent": "NEXA-review"})
        return response.status_code < 400
    except Exception:
        return False


def _run(link_id: int, user_id: int) -> None:
    db = SessionLocal()
    try:
        link = db.get(Link, link_id)
        user = db.get(User, user_id)
        if not link or not user or link.status not in {"reviewing", "pending"}:
            return
        key = norm_url(link.url)
        link.norm_url = key
        taken = db.scalar(select(Link.id).where(Link.norm_url == key, Link.id != link.id, Link.status.in_(("published", "reviewing"))))
        if taken:
            link.status = "rejected"
            link.review_note = "duplicate"
            hits = rds.incr(f"dupsubmit:{user_id}")
            if hits == 1:
                rds.expire(f"dupsubmit:{user_id}", 3600)
            if hits >= 3 and not db.scalar(select(AdminAlert.id).where(AdminAlert.user_id == user_id, AdminAlert.handled.is_(False))):
                db.add(AdminAlert(user_id=user.id, email=user.email, ip=link.client_ip or user.last_ip or "", detail="同一网址反复提交"))
            db.commit()
            return
        if not _opens(link.url):
            link.status = "rejected"
            link.review_note = "unreachable"
            db.commit()
            return
        rule = db.get(PointRule, 1)
        user.points = (user.points or 0) + (rule.points_per_link if rule else 1)
        link.status = "published"
        link.review_note = "opened"
        link.favorite_count = random.randint(6, 96)
        link.recommend_count = random.randint(2, 48)
        link.click_count = random.randint(12, 240)
        link.counts_ready = True
        link.clicks_ready = True
        link.created_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def schedule_review(link_id: int, user_id: int) -> None:
    threading.Thread(target=_run, args=(link_id, user_id), daemon=True).start()


def sweep_open() -> None:
    db = SessionLocal()
    try:
        rows = db.scalars(select(Link).where(Link.source == "user", Link.status.in_(("pending", "reviewing")))).all()
        jobs = [(row.id, row.submitter_id) for row in rows if row.submitter_id]
    finally:
        db.close()
    for link_id, user_id in jobs:
        schedule_review(link_id, user_id)
