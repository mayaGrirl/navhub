from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import db_session, require_user
from app.models import Ad, Announcement, Category, Link, NewsItem, Page, Tab, User
from app.security import month_key, plan_active, quota_for, rds

router = APIRouter(prefix="/api", tags=["public"])


def _t(locale: str, en: str, zh: str) -> str:
    return zh if locale == "zh" else en


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
    rows = db.scalars(select(NewsItem).order_by(NewsItem.published_at.desc(), NewsItem.id.desc()).limit(40)).all()
    return [
        {
            "id": row.id,
            "title": row.title,
            "url": row.url,
            "source": row.source,
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
                    }
                    for row in rows
                ],
            }
        )
    return payload


@router.get("/github")
def github(period: str = "past_24_hours"):
    allowed = {"past_24_hours", "past_week", "past_month"}
    if period not in allowed:
        period = "past_24_hours"
    cache_key = f"github:{period}"
    cached = rds.get(cache_key)
    if cached:
        import json

        return json.loads(cached)
    import httpx

    try:
        response = httpx.get(
            "https://api.ossinsight.io/v1/trends/repos/",
            params={"period": period, "language": "All"},
            timeout=20,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json().get("data", {}).get("rows", [])[:20]
    except Exception:
        return []
    import json

    if data:
        rds.setex(cache_key, 3600, json.dumps(data))
    return data


@router.post("/submissions")
def submit(payload: dict, user: User = Depends(require_user), db: Session = Depends(db_session)):
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
    link = Link(
        category_id=category.id,
        title_en=payload.get("title_en") or payload.get("title") or "Untitled",
        title_zh=payload.get("title_zh") or payload.get("title") or "未命名",
        description_en=payload.get("description_en") or payload.get("description") or "",
        description_zh=payload.get("description_zh") or payload.get("description") or "",
        url=payload.get("url") or "",
        logo_url=payload.get("logo_url") or "",
        attachment_url=payload.get("attachment_url") or "",
        status="pending",
        source="user",
        submitter_id=user.id,
        vip_badge=plan == "vip",
    )
    if not link.url.startswith("http"):
        raise HTTPException(status_code=400, detail="url required")
    db.add(link)
    db.commit()
    rds.incr(key)
    rds.expire(key, 60 * 60 * 24 * 40)
    return {"id": link.id, "status": link.status, "plan": plan, "used": used + 1, "limit": limit}
