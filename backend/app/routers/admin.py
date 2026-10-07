from datetime import datetime, timedelta

import httpx
import uuid
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crawl import fetch_meta, schedule_jobs, start_job, stop_job
from app.deps import db_session, require_admin, require_admin_setup
from app.security import client_ip, hash_password, checked_image
from app.models import Ad, AdminAlert, Announcement, AuthLog, Category, CrawlItem, CrawlJob, CrawlLog, Feedback, FeedbackNote, IpBan, Level, Link, MailLog, MailTask, NewsItem, Page, PointRule, Tab, User
from app.urls import norm_url
router = APIRouter(prefix="/api/manage", tags=["admin"], dependencies=[Depends(require_admin)])
setup_router = APIRouter(prefix="/api/manage", tags=["admin"])


@setup_router.get("/ping")
def ping(user: User = Depends(require_admin_setup), nav_console: str | None = Cookie(default=None)):
    from app.security import read_session

    data = read_session(nav_console) or {}
    return {"ok": True, "totp_enabled": user.totp_enabled, "totp_ok": bool(data.get("totp_ok"))}


@setup_router.get("/user-trend")
def user_trend(grain: str = "day", db: Session = Depends(db_session), _user: User = Depends(require_admin)):
    now = datetime.utcnow()
    buckets = []
    if grain == "month":
        year, month = now.year, now.month
        marks = []
        for _ in range(12):
            marks.append((year, month))
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        for year, month in reversed(marks):
            start = datetime(year, month, 1)
            end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
            buckets.append((start, end, f"{year}-{month:02d}"))
    else:
        today = datetime(now.year, now.month, now.day)
        for offset in range(13, -1, -1):
            start = today - timedelta(days=offset)
            buckets.append((start, start + timedelta(days=1), start.strftime("%m-%d")))
    created = list(db.scalars(select(User.created_at)).all())
    logins = list(db.scalars(select(AuthLog.created_at).where(AuthLog.kind == "login")).all())

    def count(times, start, end):
        return sum(1 for item in times if item and start <= item < end)

    return {
        "labels": [label for _start, _end, label in buckets],
        "register": [count(created, start, end) for start, end, _label in buckets],
        "login": [count(logins, start, end) for start, end, _label in buckets],
        "total": [sum(1 for item in created if item and item < end) for _start, end, _label in buckets],
    }


def _tab(row: Tab) -> dict:
    return {
        "id": row.id,
        "slug": row.slug,
        "title_en": row.title_en,
        "title_zh": row.title_zh,
        "kind": row.kind,
        "sort": row.sort,
        "visible": row.visible,
        "adult": row.adult,
    }


@router.get("/tabs")
def list_tabs(db: Session = Depends(db_session)):
    return [_tab(row) for row in db.scalars(select(Tab).order_by(Tab.sort.desc(), Tab.id)).all()]


@router.post("/tabs")
def create_tab(payload: dict, db: Session = Depends(db_session)):
    row = Tab(
        slug=payload["slug"],
        title_en=payload.get("title_en") or payload["slug"],
        title_zh=payload.get("title_zh") or payload["slug"],
        kind=payload.get("kind") or "links",
        sort=int(payload.get("sort") or 0),
        visible=bool(payload.get("visible", True)),
        adult=bool(payload.get("adult", False)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _tab(row)


@router.put("/tabs/{tab_id}")
def update_tab(tab_id: int, payload: dict, db: Session = Depends(db_session)):
    row = db.get(Tab, tab_id)
    if not row:
        raise HTTPException(404, "not found")
    for key in ("slug", "title_en", "title_zh", "kind"):
        if key in payload:
            setattr(row, key, payload[key])
    for key in ("sort",):
        if key in payload:
            setattr(row, key, int(payload[key]))
    for key in ("visible", "adult"):
        if key in payload:
            setattr(row, key, bool(payload[key]))
    db.commit()
    return _tab(row)


@router.delete("/tabs/{tab_id}")
def delete_tab(tab_id: int, db: Session = Depends(db_session)):
    row = db.get(Tab, tab_id)
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}


@router.get("/categories")
def list_categories(tab_id: int | None = None, db: Session = Depends(db_session)):
    stmt = select(Category).order_by(Category.sort.desc(), Category.id)
    if tab_id:
        stmt = stmt.where(Category.tab_id == tab_id)
    rows = db.scalars(stmt).all()
    return [
        {
            "id": r.id,
            "tab_id": r.tab_id,
            "slug": r.slug,
            "title_en": r.title_en,
            "title_zh": r.title_zh,
            "sort": r.sort,
            "visible": r.visible,
        }
        for r in rows
    ]


@router.post("/categories")
def create_category(payload: dict, db: Session = Depends(db_session)):
    row = Category(
        tab_id=int(payload["tab_id"]),
        slug=payload["slug"],
        title_en=payload.get("title_en") or payload["slug"],
        title_zh=payload.get("title_zh") or payload["slug"],
        sort=int(payload.get("sort") or 0),
        visible=bool(payload.get("visible", True)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.put("/categories/{category_id}")
def update_category(category_id: int, payload: dict, db: Session = Depends(db_session)):
    row = db.get(Category, category_id)
    if not row:
        raise HTTPException(404, "not found")
    for key in ("slug", "title_en", "title_zh"):
        if key in payload:
            setattr(row, key, payload[key])
    if "tab_id" in payload:
        row.tab_id = int(payload["tab_id"])
    if "sort" in payload:
        row.sort = int(payload["sort"])
    if "visible" in payload:
        row.visible = bool(payload["visible"])
    db.commit()
    return {"ok": True}


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(db_session)):
    row = db.get(Category, category_id)
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}


def _link(row: Link) -> dict:
    return {
        "id": row.id,
        "category_id": row.category_id,
        "title_en": row.title_en,
        "title_zh": row.title_zh,
        "description_en": row.description_en,
        "description_zh": row.description_zh,
        "url": row.url,
        "logo_url": row.logo_url,
        "attachment_url": row.attachment_url,
        "is_free": row.is_free,
        "is_hot": row.is_hot,
        "vip_badge": row.vip_badge,
        "status": row.status,
        "source": row.source,
        "review_note": row.review_note or "",
        "client_ip": row.client_ip or "",
        "sort": row.sort,
        "favorite_count": row.favorite_count or 0,
        "recommend_count": row.recommend_count or 0,
        "click_count": row.click_count or 0,
    }


@router.get("/link-stats")
def link_stats(db: Session = Depends(db_session)):
    rows = db.execute(select(Link.source, Link.id)).all()
    user = sum(1 for source, _id in rows if source == "user")
    return {
        "total": len(rows),
        "user": user,
        "system": len(rows) - user,
        "news": db.scalar(select(func.count()).select_from(NewsItem)) or 0,
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
        "ads": db.scalar(select(func.count()).select_from(Ad)) or 0,
        "tabs": db.scalar(select(func.count()).select_from(Tab)) or 0,
    }


@router.get("/links")
def list_links(status: str = "", db: Session = Depends(db_session)):
    stmt = select(Link).order_by(Link.id.desc())
    if status:
        stmt = stmt.where(Link.status == status)
    return [_link(row) for row in db.scalars(stmt.limit(1000)).all()]


@router.post("/links")
def create_link(payload: dict, db: Session = Depends(db_session)):
    row = Link(
        category_id=int(payload["category_id"]),
        title_en=payload.get("title_en") or "",
        title_zh=payload.get("title_zh") or "",
        description_en=payload.get("description_en") or "",
        description_zh=payload.get("description_zh") or "",
        url=payload["url"],
        logo_url=payload.get("logo_url") or "",
        attachment_url=payload.get("attachment_url") or "",
        is_free=bool(payload.get("is_free", False)),
        is_hot=bool(payload.get("is_hot", False)),
        norm_url=norm_url(payload["url"]),
        status=payload.get("status") or "published",
        source="admin",
        sort=int(payload.get("sort") or 0),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _link(row)


@router.put("/links/{link_id}")
def update_link(link_id: int, payload: dict, db: Session = Depends(db_session)):
    row = db.get(Link, link_id)
    if not row:
        raise HTTPException(404, "not found")
    for key in ("title_en", "title_zh", "description_en", "description_zh", "url", "logo_url", "attachment_url", "status"):
        if key in payload:
            setattr(row, key, payload[key] or "")
    if "category_id" in payload:
        row.category_id = int(payload["category_id"])
    for key in ("is_free", "is_hot", "vip_badge"):
        if key in payload:
            setattr(row, key, bool(payload[key]))
    if "sort" in payload:
        row.sort = int(payload["sort"])
    for key in ("favorite_count", "recommend_count", "click_count"):
        if key in payload:
            setattr(row, key, max(0, int(payload[key] or 0)))
            if key == "click_count":
                row.clicks_ready = True
            else:
                row.counts_ready = True
    db.commit()
    return _link(row)


@router.post("/links/bump")
def bump_links(payload: dict, db: Session = Depends(db_session)):
    import random

    field = payload.get("field")
    if field not in ("favorite_count", "recommend_count", "click_count"):
        raise HTTPException(400, "bad field")
    ids = [int(item) for item in (payload.get("ids") or [])]
    rows = db.scalars(select(Link).where(Link.id.in_(ids))).all() if ids else []
    for row in rows:
        added = random.randint(1, 20)
        setattr(row, field, max(0, (getattr(row, field) or 0) + added))
        if field == "click_count":
            row.clicks_ready = True
        else:
            row.counts_ready = True
    db.commit()
    return {"ok": True, "count": len(rows)}


@router.delete("/links/{link_id}")
def delete_link(link_id: int, db: Session = Depends(db_session)):
    row = db.get(Link, link_id)
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}


@router.get("/pages")
def pages(db: Session = Depends(db_session)):
    rows = db.scalars(select(Page)).all()
    return [
        {
            "id": r.id,
            "key": r.key,
            "title_en": r.title_en,
            "title_zh": r.title_zh,
            "body_en": r.body_en,
            "body_zh": r.body_zh,
            "email": r.email,
            "phone": r.phone,
            "im": r.im,
            "address": r.address,
        }
        for r in rows
    ]


@router.put("/pages/{page_id}")
def update_page(page_id: int, payload: dict, db: Session = Depends(db_session)):
    row = db.get(Page, page_id)
    if not row:
        raise HTTPException(404, "not found")
    for key in ("title_en", "title_zh", "body_en", "body_zh", "email", "phone", "im", "address"):
        if key in payload:
            setattr(row, key, payload[key] or "")
    db.commit()
    return {"ok": True}


AD_SLOTS = [
    ("banner", "首页顶部右侧", "搜索框右边轮播", 10),
    ("strip", "首页栏目上方", "通栏横图", 20),
    ("github-growth", "首页右侧", "增量榜下面", 30),
    ("github-total", "首页右侧", "总量榜下面", 40),
    ("rail", "首页右侧", "竖图广告", 50),
    ("footer", "页面底部", "页脚右侧", 60),
    ("about-1", "关于我们", "右侧第 1 个", 70),
    ("about-2", "关于我们", "右侧第 2 个", 80),
    ("about-3", "关于我们", "右侧第 3 个", 90),
    ("contact-1", "联系方式", "右侧第 1 个", 100),
    ("contact-2", "联系方式", "右侧第 2 个", 110),
    ("contact-3", "联系方式", "右侧第 3 个", 120),
    ("auth-1", "登录 / 注册", "左侧第 1 张", 130),
    ("auth-2", "登录 / 注册", "左侧第 2 张", 140),
    ("auth-3", "登录 / 注册", "左侧第 3 张", 150),
    ("account-1", "个人中心", "右侧第 1 个", 160),
    ("account-2", "个人中心", "右侧第 2 个", 170),
] + [
    (f"feed-{slug}-{n}", page, f"内容区第 {n} 条", 200 + i * 10 + n)
    for i, (slug, page) in enumerate([
        ("general", "每日资讯"),
        ("ai", "AI工具"),
        ("cross-border", "跨境电商"),
        ("media", "午夜媒体"),
        ("telegram", "TG群"),
    ])
    for n in (1, 2, 3, 4)
]


def ensure_ads(db: Session):
    have = set(db.scalars(select(Ad.slot)).all())
    for slot, page, where, sort in AD_SLOTS:
        if slot in have:
            continue
        db.add(Ad(slot=slot, title_zh=f"{page} · {where}", title_en=slot, image_url="", link_url="", enabled=False, sort=sort))
    db.commit()


@router.get("/ads")
def list_ads(db: Session = Depends(db_session)):
    ensure_ads(db)
    rows = db.scalars(select(Ad).order_by(Ad.sort, Ad.id)).all()
    return [
        {
            "id": r.id,
            "slot": r.slot,
            "image_url": r.image_url,
            "link_url": r.link_url,
            "title_en": r.title_en,
            "title_zh": r.title_zh,
            "enabled": r.enabled,
            "show_placeholder": bool(r.show_placeholder),
            "sort": r.sort,
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        }
        for r in rows
    ]


CAROUSEL_SLOTS = {"banner"}


@router.post("/ads")
def create_ad(payload: dict, db: Session = Depends(db_session)):
    slot = payload.get("slot") or ""
    if slot not in CAROUSEL_SLOTS:
        raise HTTPException(400, "ad slots are fixed")
    row = Ad(
        slot=slot,
        image_url=payload.get("image_url") or "",
        link_url=payload.get("link_url") or "",
        title_en=payload.get("title_en") or "",
        title_zh=payload.get("title_zh") or "",
        enabled=bool(payload.get("enabled", True)),
        show_placeholder=bool(payload.get("show_placeholder", True)),
        sort=int(payload.get("sort") or 0),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    from app.security import rds
    rds.delete("home:zh", "home:en")
    return {"id": row.id}


@router.put("/ads/{ad_id}")
def update_ad(ad_id: int, payload: dict, db: Session = Depends(db_session)):
    row = db.get(Ad, ad_id)
    if not row:
        raise HTTPException(404, "not found")
    for key in ("image_url", "link_url", "title_en", "title_zh"):
        if key in payload:
            setattr(row, key, payload[key] or "")
    if "enabled" in payload:
        row.enabled = bool(payload["enabled"])
    if "show_placeholder" in payload:
        row.show_placeholder = bool(payload["show_placeholder"])
    row.updated_at = datetime.utcnow()
    from app.security import rds
    rds.delete("home:zh", "home:en")
    if "sort" in payload:
        row.sort = int(payload["sort"] or 0)
    db.commit()
    return {"ok": True}


@router.delete("/ads/{ad_id}")
def delete_ad(ad_id: int, db: Session = Depends(db_session)):
    row = db.get(Ad, ad_id)
    if not row or row.slot not in CAROUSEL_SLOTS:
        raise HTTPException(400, "ad slots are fixed")
    others = db.scalar(select(func.count()).select_from(Ad).where(Ad.slot == row.slot, Ad.id != row.id))
    if not others:
        raise HTTPException(400, "ad slots are fixed")
    db.delete(row)
    db.commit()
    from app.security import rds
    rds.delete("home:zh", "home:en")
    return {"ok": True}


@router.post("/uploads")
async def upload_ad_image(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        suffix = checked_image(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="image required") from exc
    folder = Path(__file__).resolve().parents[3] / "frontend" / "public" / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{suffix}"
    (folder / name).write_bytes(raw)
    return {"url": f"/uploads/{name}"}


@router.get("/news")
def list_news(db: Session = Depends(db_session)):
    rows = db.scalars(select(NewsItem).order_by(NewsItem.published_at.desc(), NewsItem.id.desc()).limit(500)).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "url": r.url,
            "source": r.source,
            "category": r.category,
            "published_at": r.published_at.isoformat() if r.published_at else "",
        }
        for r in rows
    ]


@router.delete("/news/{item_id}")
def delete_news(item_id: int, db: Session = Depends(db_session)):
    row = db.get(NewsItem, item_id)
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}


@router.get("/announcements")
def list_announcements(db: Session = Depends(db_session)):
    rows = db.scalars(select(Announcement).order_by(Announcement.id.desc())).all()
    return [
        {"id": r.id, "title_en": r.title_en, "title_zh": r.title_zh, "body_en": r.body_en, "body_zh": r.body_zh, "image_url": r.image_url or "", "popup": bool(r.popup), "enabled": r.enabled, "created_at": r.created_at.isoformat() if r.created_at else ""}
        for r in rows
    ]


@router.post("/announcements")
def create_announcement(payload: dict, db: Session = Depends(db_session)):
    row = Announcement(
        title_en=payload.get("title_en") or "",
        title_zh=payload.get("title_zh") or "",
        body_en=payload.get("body_en") or "",
        body_zh=payload.get("body_zh") or "",
        image_url=payload.get("image_url") or "",
        popup=bool(payload.get("popup")),
        enabled=bool(payload.get("enabled", True)),
    )
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.put("/announcements/{item_id}")
def update_announcement(item_id: int, payload: dict, db: Session = Depends(db_session)):
    row = db.get(Announcement, item_id)
    if not row:
        raise HTTPException(404, "not found")
    for key in ("title_en", "title_zh", "body_en", "body_zh", "image_url"):
        if key in payload:
            setattr(row, key, payload[key] or "")
    if "enabled" in payload:
        row.enabled = bool(payload["enabled"])
    if "popup" in payload:
        row.popup = bool(payload["popup"])
    db.commit()
    return {"ok": True}


@router.delete("/announcements/{item_id}")
def delete_announcement(item_id: int, db: Session = Depends(db_session)):
    row = db.get(Announcement, item_id)
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}


@router.get("/users")
def users(request: Request, db: Session = Depends(db_session), actor: User = Depends(require_admin)):
    ip = client_ip(request)
    if ip and actor.last_ip != ip:
        actor.last_ip = ip
        db.commit()
    rows = db.scalars(select(User).order_by(User.id.desc()).limit(1000)).all()
    levels = db.scalars(select(Level).where(Level.level <= 10).order_by(Level.min_points.desc(), Level.level.desc())).all()
    return [
        {
            "id": r.id,
            "email": r.email,
            "display_name": r.display_name or "",
            "role": r.role,
            "plan": r.plan,
            "points": r.points or 0,
            "level": next((item.level for item in levels if (r.points or 0) >= item.min_points), 0),
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "plan_expires_at": r.plan_expires_at.isoformat() if r.plan_expires_at else None,
            "totp_enabled": r.totp_enabled,
            "totp_confirmed": bool(r.totp_confirmed),
            "banned": bool(r.banned),
            "last_ip": r.last_ip or "",
            "proxy_unlimited": bool(r.proxy_unlimited),
            "proxy_limit": r.proxy_limit,
        }
        for r in rows
    ]


@router.put("/users/{user_id}")
def update_user(user_id: int, payload: dict, db: Session = Depends(db_session), actor: User = Depends(require_admin)):
    row = db.get(User, user_id)
    if not row:
        raise HTTPException(404, "not found")
    if "role" in payload:
        row.role = payload["role"]
    if "banned" in payload:
        if row.id == actor.id and payload["banned"]:
            raise HTTPException(400, "cannot ban yourself")
        row.banned = bool(payload["banned"])
        if row.last_ip:
            existing = db.scalar(select(IpBan).where(IpBan.ip == row.last_ip))
            if row.banned and not existing:
                db.add(IpBan(ip=row.last_ip, reason="admin"))
            if not row.banned and existing:
                db.delete(existing)
    if "proxy_unlimited" in payload:
        row.proxy_unlimited = bool(payload["proxy_unlimited"])
    if "proxy_limit" in payload:
        raw = payload.get("proxy_limit")
        row.proxy_limit = None if raw in (None, "") else max(0, int(raw))
    if payload.get("plan") in {"free", "vip"}:
        row.plan = payload["plan"]
        if row.plan == "vip":
            days = int(payload.get("days") or 30)
            row.plan_expires_at = datetime.utcnow() + timedelta(days=days)
        else:
            row.plan_expires_at = None
    db.commit()
    return {"ok": True}


@router.post("/admins")
def create_admin(payload: dict, db: Session = Depends(db_session)):
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    if "@" not in email or len(password) < 8:
        raise HTTPException(400, "email or password invalid")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(400, "email exists")
    row = User(email=email, password_hash=hash_password(password), role="admin")
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.put("/users/{user_id}/password")
def reset_password(user_id: int, payload: dict, db: Session = Depends(db_session)):
    row = db.get(User, user_id)
    password = payload.get("password") or ""
    if not row:
        raise HTTPException(404, "not found")
    if len(password) < 8:
        raise HTTPException(400, "password too short")
    row.password_hash = hash_password(password)
    db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/reset-totp")
def reset_totp(user_id: int, db: Session = Depends(db_session)):
    row = db.get(User, user_id)
    if not row:
        raise HTTPException(404, "not found")
    row.totp_secret = ""
    row.totp_enabled = False
    row.totp_confirmed = False
    db.commit()
    return {"ok": True}


@router.get("/ip-bans")
def ip_bans(db: Session = Depends(db_session)):
    rows = db.scalars(select(IpBan).order_by(IpBan.id.desc()).limit(200)).all()
    return [{"id": r.id, "ip": r.ip, "reason": r.reason} for r in rows]


@router.post("/ip-bans")
def add_ip_ban(payload: dict, db: Session = Depends(db_session)):
    ip = (payload.get("ip") or "").strip()[:64]
    if not ip:
        raise HTTPException(400, "ip required")
    if not db.scalar(select(IpBan).where(IpBan.ip == ip)):
        db.add(IpBan(ip=ip, reason="admin"))
        db.commit()
    return {"ok": True}


@router.delete("/ip-bans")
def remove_ip_ban(ip: str, db: Session = Depends(db_session)):
    row = db.scalar(select(IpBan).where(IpBan.ip == ip))
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}


@router.get("/alerts")
def alerts(db: Session = Depends(db_session)):
    rows = db.scalars(select(AdminAlert).order_by(AdminAlert.id.desc()).limit(50)).all()
    return [
        {"id": row.id, "user_id": row.user_id, "email": row.email, "ip": row.ip, "detail": row.detail, "handled": row.handled}
        for row in rows
    ]


@router.post("/alerts/{alert_id}/ban")
def ban_from_alert(alert_id: int, db: Session = Depends(db_session)):
    row = db.get(AdminAlert, alert_id)
    if not row:
        raise HTTPException(404, "not found")
    user = db.get(User, row.user_id) if row.user_id else None
    if user:
        user.banned = True
    ip = row.ip or (user.last_ip if user else "")
    if ip and not db.scalar(select(IpBan.id).where(IpBan.ip == ip)):
        db.add(IpBan(ip=ip, reason=row.detail or "alert"))
    row.handled = True
    db.commit()
    return {"ok": True}


@router.get("/crawl/jobs")
def jobs(db: Session = Depends(db_session)):
    rows = db.scalars(select(CrawlJob).order_by(CrawlJob.id.desc())).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "list_url": r.list_url,
            "keyword": r.keyword or "",
            "category_id": r.category_id,
            "interval_minutes": r.interval_minutes,
            "enabled": r.enabled,
            "status": r.status or "idle",
            "message": r.message or "",
            "found_count": r.found_count or 0,
            "last_run_at": r.last_run_at.isoformat() if r.last_run_at else "",
        }
        for r in rows
    ]


@router.get("/crawl/logs")
def crawl_logs(job_id: int = 0, db: Session = Depends(db_session)):
    stmt = select(CrawlLog).order_by(CrawlLog.id.desc()).limit(80)
    if job_id:
        stmt = select(CrawlLog).where(CrawlLog.job_id == job_id).order_by(CrawlLog.id.desc()).limit(80)
    rows = list(reversed(db.scalars(stmt).all()))
    names = {row.id: row.name for row in db.scalars(select(CrawlJob)).all()}
    return [
        {"id": r.id, "job_id": r.job_id, "job": names.get(r.job_id, ""), "message": r.message, "created_at": r.created_at.isoformat() if r.created_at else ""}
        for r in rows
    ]


@router.post("/crawl/jobs")
def create_job(payload: dict, db: Session = Depends(db_session)):
    keyword = (payload.get("keyword") or payload.get("name") or "").strip()
    list_url = (payload.get("list_url") or "").strip()
    if not list_url and not keyword:
        raise HTTPException(400, "填写关键词或网址")
    row = CrawlJob(
        name=payload.get("name") or keyword or "采集任务",
        list_url=list_url,
        keyword=keyword,
        category_id=int(payload["category_id"]),
        interval_minutes=max(1, int(payload.get("interval_minutes") or 1440)),
        enabled=True,
        status="idle",
    )
    db.add(row)
    db.commit()
    start_job(row.id)
    return {"id": row.id}


@router.put("/crawl/jobs/{job_id}")
def update_job(job_id: int, payload: dict, db: Session = Depends(db_session)):
    row = db.get(CrawlJob, job_id)
    if not row:
        raise HTTPException(404, "not found")
    if "name" in payload:
        row.name = payload.get("name") or row.name
    if "list_url" in payload:
        row.list_url = (payload.get("list_url") or "").strip()
    if "keyword" in payload:
        row.keyword = (payload.get("keyword") or "").strip()
    if "category_id" in payload:
        row.category_id = int(payload["category_id"])
    if "interval_minutes" in payload:
        row.interval_minutes = max(1, int(payload.get("interval_minutes") or 1440))
    if not (row.list_url or "").strip() and not (row.keyword or row.name or "").strip():
        raise HTTPException(400, "填写关键词或网址")
    db.commit()
    return {"ok": True}


@router.post("/crawl/jobs/{job_id}/run")
def run_job_now(job_id: int, db: Session = Depends(db_session)):
    row = db.get(CrawlJob, job_id)
    if not row:
        raise HTTPException(404, "not found")
    row.enabled = True
    db.commit()
    if not start_job(row.id):
        raise HTTPException(400, "already running")
    return {"ok": True}


@router.post("/crawl/jobs/{job_id}/stop")
def stop_job_now(job_id: int, db: Session = Depends(db_session)):
    row = db.get(CrawlJob, job_id)
    if not row:
        raise HTTPException(404, "not found")
    row.enabled = False
    stop_job(row.id)
    if row.status == "running":
        row.status = "stopped"
        row.message = "已停止"
    db.commit()
    return {"ok": True}


@router.delete("/crawl/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(db_session)):
    row = db.get(CrawlJob, job_id)
    if row:
        stop_job(row.id)
        for item in db.scalars(select(CrawlItem).where(CrawlItem.job_id == row.id, CrawlItem.status == "pending")).all():
            db.delete(item)
        db.delete(row)
        db.commit()
    return {"ok": True}


@router.post("/crawl/fetch")
def fetch_one(payload: dict, db: Session = Depends(db_session)):
    try:
        meta = fetch_meta(payload["url"])
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    item = CrawlItem(
        category_id=int(payload["category_id"]),
        title=meta["title"],
        url=meta["url"],
        description=meta["description"],
        logo_url=meta["logo_url"],
    )
    db.add(item)
    db.commit()
    return {"id": item.id, **meta}


@router.get("/crawl/items")
def crawl_items(db: Session = Depends(db_session)):
    rows = db.scalars(select(CrawlItem).where(CrawlItem.status == "pending").order_by(CrawlItem.id.desc()).limit(100)).all()
    return [
        {"id": r.id, "category_id": r.category_id, "title": r.title, "url": r.url, "description": r.description, "logo_url": r.logo_url}
        for r in rows
    ]


@router.post("/crawl/items/{item_id}/approve")
def approve(item_id: int, db: Session = Depends(db_session)):
    item = db.get(CrawlItem, item_id)
    if not item:
        raise HTTPException(404, "not found")
    link = Link(
        category_id=item.category_id,
        title_en=item.title or item.url,
        title_zh=item.title or item.url,
        description_en=item.description,
        description_zh=item.description,
        url=item.url,
        logo_url=item.logo_url,
        status="published",
        source="crawl",
    )
    item.status = "approved"
    db.add(link)
    db.commit()
    return {"ok": True}


def _pool():
    from app.config import settings

    return (settings.proxy_pool_url or "").rstrip("/")


@router.get("/levels")
def list_levels(db: Session = Depends(db_session)):
    rows = db.scalars(select(Level).where(Level.level <= 10).order_by(Level.level)).all()
    rule = db.get(PointRule, 1)
    return {
        "points_per_link": rule.points_per_link if rule else 1,
        "levels": [{"level": r.level, "min_points": r.min_points, "proxy_per_minute": r.proxy_per_minute} for r in rows],
    }


@router.put("/levels/{level}")
def save_level(level: int, payload: dict, db: Session = Depends(db_session)):
    row = db.get(Level, level)
    if not row:
        raise HTTPException(404, "not found")
    row.min_points = int(payload.get("min_points") or 0)
    row.proxy_per_minute = int(payload.get("proxy_per_minute") or 1)
    db.commit()
    return {"ok": True}


@router.put("/point-rule")
def save_point_rule(payload: dict, db: Session = Depends(db_session)):
    row = db.get(PointRule, 1) or PointRule(id=1)
    row.points_per_link = max(1, int(payload.get("points_per_link") or 1))
    db.add(row)
    db.commit()
    return {"points_per_link": row.points_per_link}


def _open_lists() -> list[str]:
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "proxy-pool" / "sources.py"
    spec = importlib.util.spec_from_file_location("pool_sources", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.LISTS)


@router.get("/proxies")
def proxies():
    lists = _open_lists()
    base = _pool()
    empty = {
        "count": 0,
        "sources": len(lists),
        "items": [],
        "source_items": [{"id": index + 1, "url": url} for index, url in enumerate(lists)],
        "note": "proxy pool is not running",
    }
    if not base:
        empty["note"] = "PROXY_POOL_URL is empty"
        return empty
    try:
        alive = httpx.get(f"{base}/alive", timeout=8)
        sources = httpx.get(f"{base}/sources", timeout=8)
        alive.raise_for_status()
        sources.raise_for_status()
        data = alive.json()
        stored = sources.json().get("items", [])
        seen = {item.get("url") for item in stored}
        for url in lists:
            if url not in seen:
                stored.append({"id": None, "url": url})
        data["source_items"] = stored
        data["sources"] = len(stored)
        data["note"] = "每 3 分钟检测一次，打不开的代理会删掉。"
        return data
    except httpx.HTTPError:
        return empty


@router.delete("/proxies")
def remove_proxy(url: str):
    base = _pool()
    if not base:
        raise HTTPException(status_code=400, detail="proxy pool is not running")
    httpx.delete(f"{base}/proxies", params={"url": url}, timeout=8)
    return {"ok": True}


@router.delete("/proxy-sources")
def remove_proxy_source(url: str):
    base = _pool()
    if not base:
        raise HTTPException(status_code=400, detail="proxy pool is not running")
    httpx.delete(f"{base}/sources", params={"url": url}, timeout=8)
    return {"ok": True}


@router.get("/mail")
def mail_state(db: Session = Depends(db_session)):
    from app.mailer import mail_row, public_mail
    row = mail_row(db)
    logs = db.scalars(select(MailLog).order_by(MailLog.id.desc()).limit(30)).all()
    tasks = db.scalars(select(MailTask).order_by(MailTask.id.desc())).all()
    return {
        "settings": public_mail(row),
        "tasks": [
            {"id": t.id, "subject": t.subject, "body": t.body, "audience": t.audience, "run_at": t.run_at.isoformat() if t.run_at else "", "interval_minutes": t.interval_minutes, "enabled": t.enabled}
            for t in tasks
        ],
        "logs": [
            {"id": r.id, "recipient": r.recipient, "subject": r.subject, "channel": r.channel, "status": r.status, "message": r.message, "created_at": r.created_at.isoformat() if r.created_at else ""}
            for r in logs
        ],
    }


@router.put("/mail")
def save_mail(payload: dict, db: Session = Depends(db_session)):
    from app.config import settings
    from app.mailer import mail_row, public_mail
    row = mail_row(db)
    for key in ("gmail_enabled", "netease_enabled", "sendgrid_enabled", "mailgun_enabled", "ses_enabled", "notify_default", "money_dm"):
        if key in payload:
            setattr(row, key, bool(payload[key]))
    for key in ("gmail_host", "gmail_user", "gmail_pass", "gmail_from", "gmail_from_name", "netease_host", "netease_user", "netease_pass", "netease_from", "netease_from_name", "sendgrid_key", "sendgrid_from", "sendgrid_from_name", "mailgun_key", "mailgun_domain", "mailgun_region", "mailgun_from", "mailgun_from_name"):
        if key in payload:
            setattr(row, key, str(payload.get(key) or "").strip()[:300])
    if row.gmail_enabled and not (row.gmail_user.strip() or settings.mail_smtp_user) :
        raise HTTPException(400, "开启 Gmail 需要填写账号和密码")
    if row.gmail_enabled and not (row.gmail_pass.strip() or settings.mail_smtp_pass):
        raise HTTPException(400, "开启 Gmail 需要填写账号和密码")
    if row.netease_enabled and not ((row.netease_user.strip() or settings.mail_smtp_163_user) and (row.netease_pass.strip() or settings.mail_smtp_163_pass)):
        raise HTTPException(400, "开启 163 需要填写账号和密码")
    if row.sendgrid_enabled and not (row.sendgrid_key.strip() or settings.sendgrid_api_key):
        raise HTTPException(400, "开启 SendGrid 需要填写 API Key")
    if row.mailgun_enabled and not ((row.mailgun_key.strip() or settings.mailgun_api_key) and (row.mailgun_domain.strip() or settings.mailgun_domain)):
        raise HTTPException(400, "开启 Mailgun 需要填写 API Key 和域名")
    for key in ("gmail_port", "netease_port"):
        if key in payload:
            try:
                setattr(row, key, int(payload.get(key) or 0))
            except (TypeError, ValueError):
                setattr(row, key, 0)
    db.commit()
    return public_mail(row)


@router.post("/mail/test")
def test_mail(payload: dict, db: Session = Depends(db_session)):
    from app.mailer import _channels, deliver, mail_row
    email = (payload.get("email") or "").strip()
    if "@" not in email:
        raise HTTPException(400, "填写测试邮箱")
    channels = [item for item in _channels(mail_row(db)) if item != "log"]
    if not channels:
        raise HTTPException(400, "Gmail 和 163 的账号密码还没填写，测试信发不出去")
    channel = deliver(db, email, "NEXA 测试邮件", "这是一封配置测试邮件。收到它，说明当前发信通道可用。")
    last = db.scalars(select(MailLog).order_by(MailLog.id.desc()).limit(1)).first()
    if channel == "error":
        raise HTTPException(400, (last.message if last else "") or "发送失败")
    return {"ok": True, "channel": channel, "message": "已发送"}


@router.post("/mail/send")
def send_mail_now(payload: dict, db: Session = Depends(db_session)):
    from app.mailer import deliver, send_bulk
    subject = (payload.get("subject") or "").strip()
    body = (payload.get("body") or "").strip()
    if not subject or not body:
        raise HTTPException(400, "填写标题和正文")
    email = (payload.get("email") or "").strip()
    if email:
        channel = deliver(db, email, subject, body)
        return {"sent": 1, "channel": channel}
    result = send_bulk(subject, body, payload.get("audience") or "all")
    return result


@router.post("/mail/tasks")
def create_mail_task(payload: dict, db: Session = Depends(db_session)):
    subject = (payload.get("subject") or "").strip()
    body = (payload.get("body") or "").strip()
    if not subject or not body:
        raise HTTPException(400, "填写标题和正文")
    when = payload.get("run_at") or ""
    run_at = datetime.fromisoformat(when.replace("Z", "")) if when else datetime.utcnow()
    row = MailTask(subject=subject, body=body, audience=payload.get("audience") or "all", run_at=run_at, interval_minutes=max(0, int(payload.get("interval_minutes") or 0)), enabled=True)
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.delete("/mail/tasks/{task_id}")
def delete_mail_task(task_id: int, db: Session = Depends(db_session)):
    row = db.get(MailTask, task_id)
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}


def _feedback_detail(db: Session, row: Feedback) -> dict:
    user = db.get(User, row.user_id)
    notes = db.scalars(select(FeedbackNote).where(FeedbackNote.feedback_id == row.id).order_by(FeedbackNote.id)).all()
    return {
        "id": row.id,
        "email": user.email if user else "",
        "title": row.title,
        "body": row.body,
        "image_url": row.image_url,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        "notes": [
            {"id": note.id, "role": note.role, "body": note.body, "created_at": note.created_at.isoformat() if note.created_at else ""}
            for note in notes
        ],
    }


@router.get("/feedback")
def list_feedback(db: Session = Depends(db_session)):
    rows = db.scalars(select(Feedback).order_by(Feedback.id.desc()).limit(200)).all()
    return [_feedback_detail(db, row) for row in rows]


@router.put("/feedback/{feedback_id}")
def update_feedback(feedback_id: int, payload: dict, db: Session = Depends(db_session)):
    row = db.get(Feedback, feedback_id)
    if not row:
        raise HTTPException(404, "not found")
    labels = {"pending": "待处理", "working": "处理中", "done": "已完成", "rejected": "拒绝", "closed": "关闭"}
    status = (payload.get("status") or row.status).strip()
    if status not in labels:
        raise HTTPException(400, "状态不正确")
    note = (payload.get("note") or "").strip()
    changed = status != row.status
    if changed:
        row.status = status
    if changed or note:
        row.updated_at = datetime.utcnow()
        text = f"状态更新为{labels[status]}" if changed else ""
        if note:
            text = f"{text}\n{note}".strip()
        db.add(FeedbackNote(feedback_id=row.id, role="admin", body=text))
    db.commit()
    return _feedback_detail(db, row)
