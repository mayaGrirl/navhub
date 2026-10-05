import secrets
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Category, Link, Page, Tab, User
from app.security import hash_password

GATE_FILE = Path(__file__).resolve().parents[1] / "data" / "admin_gate.txt"


def ensure_gate() -> str:
    if settings.admin_gate:
        return settings.admin_gate
    GATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if GATE_FILE.exists():
        return GATE_FILE.read_text(encoding="utf-8").strip()
    gate = secrets.token_urlsafe(18)
    GATE_FILE.write_text(gate, encoding="utf-8")
    return gate


def seed(db: Session) -> str:
    gate = ensure_gate()
    if not db.scalar(select(User).where(User.email == settings.admin_email)):
        db.add(
            User(
                email=settings.admin_email,
                password_hash=hash_password(settings.admin_password),
                role="admin",
            )
        )
    home = db.scalar(select(Tab).where(Tab.slug == "github"))
    if home:
        home.slug = "general"
        home.title_en = "Home"
        home.title_zh = "综合"
        home.kind = "home"
        home.sort = -1
    if db.scalar(select(Tab.id)):
        db.commit()
        return gate

    samples = [
        ("ai", "AI", "AI", "links", False, [("writing", "AI Writing", "AI写作")]),
        ("cross-border", "Cross-border", "跨境电商", "links", False, [("sourcing", "Sourcing", "选品")]),
        ("resources", "Resources", "资料", "links", False, [("reports", "Reports", "报告")]),
        ("media", "Media", "媒体", "links", False, [("video", "Video", "视频")]),
        ("general", "Home", "综合", "home", False, []),
        ("adult", "Adult", "成人", "links", True, [("sites", "Sites", "站点")]),
    ]
    for index, (slug, en, zh, kind, adult, cats) in enumerate(samples):
        tab = Tab(slug=slug, title_en=en, title_zh=zh, kind=kind, sort=index, adult=adult)
        db.add(tab)
        db.flush()
        for c_index, (c_slug, c_en, c_zh) in enumerate(cats):
            category = Category(tab_id=tab.id, slug=c_slug, title_en=c_en, title_zh=c_zh, sort=c_index)
            db.add(category)
            db.flush()
            if slug == "ai" and c_slug == "writing":
                db.add(
                    Link(
                        category_id=category.id,
                        title_en="Example writer",
                        title_zh="示例写作",
                        description_en="Sample card. Replace it from the admin console.",
                        description_zh="示例卡片，可在后台替换。",
                        url="https://example.com",
                        is_free=True,
                        status="published",
                        source="admin",
                    )
                )

    db.add(
        Page(
            key="about",
            title_en="About",
            title_zh="关于我们",
            body_en="A directory of links. Edit this page in the admin console.",
            body_zh="这是一个链接导航站。请在管理后台编辑本页。",
        )
    )
    db.add(
        Page(
            key="contact",
            title_en="Contact",
            title_zh="联系方式",
            body_en="Reach the editor with the details below.",
            body_zh="通过下面的方式联系站点编辑。",
            email="editor@example.com",
        )
    )
    db.add(
        Page(
            key="advertise",
            title_en="Advertise",
            title_zh="广告合作",
            body_en="Advertising slots are managed in the admin console.",
            body_zh="广告位在管理后台配置。",
        )
    )
    db.commit()
    return gate
