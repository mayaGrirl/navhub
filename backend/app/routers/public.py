import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import or_, select
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
                    }
                    for row in rows
                ],
            }
        )
    return payload


@router.get("/github")
def github(period: str = "past_24_hours"):
    from app.github_ranks import load_ranks

    if period not in {"past_24_hours", "past_week", "past_month", "total"}:
        period = "past_24_hours"
    return load_ranks(period)


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
