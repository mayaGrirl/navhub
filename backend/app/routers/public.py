import uuid
from datetime import datetime
from pathlib import Path

import secrets

import httpx
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import db_session, require_user
from app.models import Ad, Announcement, Category, IpBan, Level, Link, LinkMark, NewsItem, Page, PointRule, Tab, User
from app.urls import norm_url
from app.security import month_key, plan_active, quota_for, rate_limit, rds

router = APIRouter(prefix="/api", tags=["public"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "")[:64]


def _t(locale: str, en: str, zh: str) -> str:
    return zh if locale == "zh" else en


@router.get("/guard")
def guard(response: Response):
    token = secrets.token_urlsafe(24)
    rds.setex(f"pass:{token}", 60 * 60 * 6, "1")
    response.set_cookie("nav_pass", token, max_age=60 * 60 * 6, httponly=True, samesite="lax", path="/")
    return {"ok": True}


@router.get("/tree")
def tree(locale: str = "en", db: Session = Depends(db_session)):
    tabs = db.scalars(select(Tab).where(Tab.visible.is_(True)).order_by(Tab.sort, Tab.id)).all()
    payload = []
    for tab in tabs:
        categories = db.scalars(
            select(Category).where(Category.tab_id == tab.id, Category.visible.is_(True)).order_by(Category.sort, Category.id)
        ).all()
        payload.append(
            {
                "id": tab.id,
                "slug": tab.slug,
                "title": _t(locale, tab.title_en, tab.title_zh),
                "kind": tab.kind,
                "adult": tab.adult,
                "categories": [
                    {"id": c.id, "slug": c.slug, "title": _t(locale, c.title_en, c.title_zh)} for c in categories
                ],
            }
        )
    return payload


@router.get("/search")
def search(q: str = "", locale: str = "en", db: Session = Depends(db_session)):
    query = q.strip()
    if not query:
        return []
    like = f"%{query}%"
    rows = db.execute(
        select(Link, Category, Tab)
        .join(Category, Link.category_id == Category.id)
        .join(Tab, Category.tab_id == Tab.id)
        .where(
            Link.status == "published",
            Tab.visible.is_(True),
            Category.visible.is_(True),
            or_(
                Link.title_zh.like(like),
                Link.title_en.like(like),
                Link.url.like(like),
                Link.description_zh.like(like),
                Link.description_en.like(like),
            ),
        )
        .limit(20)
    ).all()
    return [
        {
            "id": link.id,
            "title": _t(locale, link.title_en, link.title_zh),
            "url": link.url,
            "logo_url": link.logo_url,
            "tab_id": tab.id,
            "category_id": category.id,
            "tab": _t(locale, tab.title_en, tab.title_zh),
            "category": _t(locale, category.title_en, category.title_zh),
        }
        for link, category, tab in rows
    ]


@router.get("/links")
def links(category_id: int, locale: str = "en", q: str = "", db: Session = Depends(db_session)):
    rows = db.scalars(
        select(Link)
        .where(Link.category_id == category_id, Link.status == "published")
        .order_by(Link.sort, Link.id.desc())
    ).all()
    query = q.strip().lower()
    result = []
    for row in rows:
        title = _t(locale, row.title_en, row.title_zh)
        description = _t(locale, row.description_en, row.description_zh)
        if query and query not in title.lower() and query not in description.lower():
            continue
        result.append(
            {
                "id": row.id,
                "title": title,
                "description": description,
                "url": row.url,
                "logo_url": row.logo_url,
                "attachment_url": row.attachment_url,
                "is_free": row.is_free,
                "is_hot": row.is_hot,
                "vip_badge": row.vip_badge,
            }
        )
    return result


@router.get("/pages/{key}")
def page(key: str, locale: str = "en", db: Session = Depends(db_session)):
    row = db.scalar(select(Page).where(Page.key == key))
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return {
        "title": _t(locale, row.title_en, row.title_zh),
        "body": _t(locale, row.body_en, row.body_zh),
        "email": row.email,
        "phone": row.phone,
        "im": row.im,
        "address": row.address,
    }


@router.get("/ads")
def ads(slot: str = "", locale: str = "en", db: Session = Depends(db_session)):
    stmt = select(Ad).where(Ad.enabled.is_(True)).order_by(Ad.sort, Ad.id)
    if slot:
        stmt = stmt.where(Ad.slot == slot)
    rows = db.scalars(stmt).all()
    return [{"id": r.id, "slot": r.slot, "image_url": r.image_url, "link_url": r.link_url, "title": _t(locale, r.title_en, r.title_zh)} for r in rows]


@router.get("/announcements")
def announcements(locale: str = "en", db: Session = Depends(db_session)):
    rows = db.scalars(select(Announcement).where(Announcement.enabled.is_(True)).order_by(Announcement.id.desc())).all()
    return [{"id": r.id, "title": _t(locale, r.title_en, r.title_zh), "body": _t(locale, r.body_en, r.body_zh)} for r in rows]


@router.get("/news")
def news(db: Session = Depends(db_session)):
    from fetch_news import today_start

    categories = db.scalars(select(NewsItem.category).where(NewsItem.published_at >= today_start()).distinct()).all()
    rows = []
    for category in categories:
        rows.extend(
            db.scalars(
                select(NewsItem).where(NewsItem.category == category, NewsItem.published_at >= today_start()).order_by(NewsItem.published_at.desc(), NewsItem.id.desc()).limit(8)
            ).all()
        )
    return [
        {
            "id": row.id,
            "title": row.title,
            "url": row.url,
            "source": row.source,
            "category": row.category,
            "summary": row.summary,
            "published_at": row.published_at.isoformat() if row.published_at else None,
        }
        for row in rows
    ]


@router.get("/board")
def board(tab_id: int, locale: str = "en", db: Session = Depends(db_session)):
    categories = db.scalars(select(Category).where(Category.tab_id == tab_id, Category.visible.is_(True)).order_by(Category.sort, Category.id)).all()
    payload = []
    for category in categories:
        rows = db.scalars(select(Link).where(Link.category_id == category.id, Link.status == "published").order_by(Link.sort, Link.id.desc())).all()
        payload.append(
            {
                "id": category.id,
                "title": _t(locale, category.title_en, category.title_zh),
                "links": [
                    {
                        "id": row.id,
                        "title": _t(locale, row.title_en, row.title_zh),
                        "description": _t(locale, row.description_en, row.description_zh),
                        "url": row.url,
                        "logo_url": row.logo_url,
                        "is_free": row.is_free,
                        "is_hot": row.is_hot,
                        "favorite_count": row.favorite_count or 0,
                        "recommend_count": row.recommend_count or 0,
                    }
                    for row in rows
                ],
            }
        )
    return payload


def user_level(db: Session, user: User) -> Level:
    rows = db.scalars(select(Level).where(Level.level <= 10).order_by(Level.min_points.desc(), Level.level.desc())).all()
    points = user.points or 0
    for row in rows:
        if points >= row.min_points:
            return row
    return rows[-1] if rows else Level(level=0, min_points=0, proxy_per_minute=10)


@router.get("/me/level")
def my_level(user: User = Depends(require_user), db: Session = Depends(db_session)):
    row = user_level(db, user)
    ladder = db.scalars(select(Level).where(Level.level <= 10).order_by(Level.level)).all()
    rule = db.get(PointRule, 1)
    per_link = rule.points_per_link if rule else 1
    return {
        "points": user.points or 0,
        "level": row.level,
        "proxy_per_minute": row.proxy_per_minute,
        "next_points": next_points(db, row),
        "points_per_link": per_link,
        "levels": [{"level": item.level, "min_points": item.min_points, "proxy_per_minute": item.proxy_per_minute} for item in ladder],
    }


def next_points(db: Session, current: Level) -> int | None:
    nxt = db.scalar(select(Level).where(Level.level == current.level + 1))
    return nxt.min_points if nxt else None


@router.post("/links/{link_id}/mark")
def mark_link(link_id: int, payload: dict, user: User = Depends(require_user), db: Session = Depends(db_session)):
    kind = payload.get("kind")
    if kind not in {"favorite", "recommend"}:
        raise HTTPException(status_code=400, detail="kind required")
    link = db.get(Link, link_id)
    if not link or link.status != "published":
        raise HTTPException(status_code=404, detail="not found")
    row = db.scalar(select(LinkMark).where(LinkMark.user_id == user.id, LinkMark.link_id == link_id, LinkMark.kind == kind))
    field = "favorite_count" if kind == "favorite" else "recommend_count"
    if row:
        db.delete(row)
        setattr(link, field, max(0, (getattr(link, field) or 0) - 1))
        on = False
    else:
        db.add(LinkMark(user_id=user.id, link_id=link_id, kind=kind))
        setattr(link, field, (getattr(link, field) or 0) + 1)
        on = True
    db.commit()
    return {"on": on, "favorite_count": link.favorite_count or 0, "recommend_count": link.recommend_count or 0}


@router.get("/me/marks")
def my_marks(locale: str = "en", user: User = Depends(require_user), db: Session = Depends(db_session)):
    rows = db.scalars(select(LinkMark).where(LinkMark.user_id == user.id)).all()
    items = []
    for mark in rows:
        link = db.get(Link, mark.link_id)
        if not link:
            continue
        items.append({"id": link.id, "kind": mark.kind, "title": _t(locale, link.title_en, link.title_zh), "url": link.url, "logo_url": link.logo_url, "favorite_count": link.favorite_count or 0, "recommend_count": link.recommend_count or 0})
    return {"items": items}


@router.get("/ranks")
def ranks(locale: str = "en", db: Session = Depends(db_session)):
    def board(kind: str):
        from sqlalchemy import text

        rows = db.execute(
            text(
                "SELECT id, title_en, title_zh, url, logo_url, "
                + ("favorite_count" if kind == "favorite" else "recommend_count")
                + " AS total FROM links WHERE status = 'published' AND "
                + ("favorite_count" if kind == "favorite" else "recommend_count")
                + " > 0 ORDER BY total DESC LIMIT 5"
            ),
            {"kind": kind},
        ).all()
        return [{"id": row.id, "title": _t(locale, row.title_en, row.title_zh), "url": row.url, "logo_url": row.logo_url or "", "count": row.total} for row in rows]

    def clicks():
        from sqlalchemy import text

        rows = db.execute(
            text(
                "SELECT id, title_en, title_zh, url, logo_url, click_count AS total "
                "FROM links WHERE status = 'published' AND click_count > 0 "
                "ORDER BY total DESC LIMIT 10"
            )
        ).all()
        return [{"id": row.id, "title": _t(locale, row.title_en, row.title_zh), "url": row.url, "logo_url": row.logo_url or "", "count": row.total} for row in rows]

    return {"favorites": board("favorite"), "recommends": board("recommend"), "clicks": clicks()}


@router.post("/links/{link_id}/click")
def count_click(link_id: int, db: Session = Depends(db_session)):
    link = db.get(Link, link_id)
    if not link or link.status != "published":
        raise HTTPException(status_code=404, detail="not found")
    link.click_count = (link.click_count or 0) + 1
    link.clicks_ready = True
    db.commit()
    return {"click_count": link.click_count}


@router.post("/proxy/token")
def issue_proxy_token(user: User = Depends(require_user), db: Session = Depends(db_session)):
    user.proxy_token = secrets.token_urlsafe(32)
    db.commit()
    return {"token": user.proxy_token}


@router.get("/proxy/token")
def read_proxy_token(user: User = Depends(require_user)):
    return {"token": user.proxy_token or ""}


@router.get("/proxy/acquire")
def acquire_proxy(token: str = Query(default=""), authorization: str | None = Header(default=None), x_proxy_token: str | None = Header(default=None), db: Session = Depends(db_session)):
    token = (x_proxy_token or token or "").strip()
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    user = db.scalar(select(User).where(User.proxy_token == token)) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="proxy token required")
    level = user_level(db, user)
    if not rate_limit(f"proxy:{user.id}", level.proxy_per_minute, 60):
        raise HTTPException(status_code=429, detail="too many requests")
    base = (settings.proxy_pool_url or "").rstrip("/")
    if not base:
        return {"proxy": None}
    try:
        response = httpx.get(f"{base}/acquire", timeout=8)
        response.raise_for_status()
        return {"proxy": response.json().get("proxy")}
    except httpx.HTTPError:
        return {"proxy": None}


@router.get("/github")
def github(period: str = "past_24_hours"):
    from app.github_ranks import load_ranks

    if period not in {"past_24_hours", "past_week", "past_month", "total"}:
        period = "past_24_hours"
    try:
        return load_ranks(period)
    except Exception as exc:
        print("github load failed", exc.__class__.__name__)
        return []


@router.post("/uploads")
async def upload_logo(file: UploadFile = File(...), user: User = Depends(require_user)):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="image required")
    raw = await file.read()
    if not raw or len(raw) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="image required")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        suffix = ".png"
    folder = Path(__file__).resolve().parents[3] / "frontend" / "public" / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{suffix}"
    (folder / name).write_bytes(raw)
    return {"url": f"/uploads/{name}"}


@router.post("/submissions")
def submit(payload: dict, request: Request, user: User = Depends(require_user), db: Session = Depends(db_session)):
    plan = plan_active(user)
    if plan == "free" and user.plan == "vip":
        user.plan = "free"
        db.commit()
    key = month_key(user.id)
    used = int(rds.get(key) or 0)
    limit = quota_for(plan)
    if used >= limit:
        raise HTTPException(status_code=429, detail="monthly quota reached")
    category = db.get(Category, int(payload.get("category_id") or 0))
    if not category:
        raise HTTPException(status_code=400, detail="category required")
    title = (payload.get("title") or payload.get("title_zh") or payload.get("title_en") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="name required")
    link = Link(
        category_id=category.id,
        title_en=(payload.get("title_en") or title).strip(),
        title_zh=(payload.get("title_zh") or title).strip(),
        description_en=payload.get("description_en") or payload.get("description") or "",
        description_zh=payload.get("description_zh") or payload.get("description") or "",
        url=payload.get("url") or "",
        logo_url=payload.get("logo_url") or "",
        attachment_url=payload.get("attachment_url") or "",
        status="reviewing",
        source="user",
        submitter_id=user.id,
        vip_badge=plan == "vip",
        client_ip=_client_ip(request),
    )
    if not link.url.startswith("http"):
        raise HTTPException(status_code=400, detail="url required")
    link.norm_url = norm_url(link.url)
    user.last_ip = link.client_ip
    if user.banned or db.scalar(select(IpBan.id).where(IpBan.ip == link.client_ip)):
        raise HTTPException(status_code=403, detail="banned")
    db.add(link)
    db.commit()
    db.refresh(link)
    rds.incr(key)
    rds.expire(key, 60 * 60 * 24 * 40)
    from app.review import schedule_review

    schedule_review(link.id, user.id)
    return {"id": link.id, "status": link.status, "plan": plan, "used": used + 1, "limit": limit}


@router.get("/me/submissions")
def my_submissions(page: int = 1, locale: str = "en", user: User = Depends(require_user), db: Session = Depends(db_session)):
    size = 10
    page = max(page, 1)
    total = db.scalar(select(func.count()).select_from(Link).where(Link.submitter_id == user.id)) or 0
    rows = db.execute(
        select(Link, Category, Tab)
        .join(Category, Link.category_id == Category.id)
        .join(Tab, Category.tab_id == Tab.id)
        .where(Link.submitter_id == user.id)
        .order_by(Link.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "id": link.id,
                "title": link.title_zh or link.title_en,
                "url": link.url,
                "logo_url": link.logo_url or "",
                "status": link.status,
                "note": link.review_note or "",
                "tab_id": tab.id,
                "category_id": category.id,
                "tab": _t(locale, tab.title_en, tab.title_zh),
                "category": _t(locale, category.title_en, category.title_zh),
            }
            for link, category, tab in rows
        ],
    }
