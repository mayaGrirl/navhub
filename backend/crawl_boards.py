"""Crawl AI, cross-border, midnight media, and Telegram directories.

Existing URLs are skipped. Safe to run again every three days.
"""
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Category, Link, Tab

HEADERS = {"User-Agent": "Mozilla/5.0"}
SKIP_HOSTS = ("amz123.com", "tt123.com", "theporndude.com")
BLOCK = ("爱一番", "影视解析", "在线解析", "幼女", "未成年", "jailbait", "lolita", "underage")

AI_SLUG = {
    "聊天AI": "chat",
    "绘画AI": "image",
    "跨境AI": "cross-border-ai",
    "图像AI": "image",
    "阅读AI": "reading",
    "写作AI": "writing",
    "提示词": "prompts",
    "设计AI": "design",
    "音频AI": "audio-tools",
    "视频AI": "video-tools",
    "办公AI": "office",
    "编程AI": "coding",
    "内容检测": "moderation",
    "开发框架": "dev-platform",
    "训练模型": "training",
    "学习网站": "learning",
}

CROSS_SLUG = {
    "常用工具": "suite",
    "综合软件": "suite",
    "ERP软件": "erp",
    "推荐服务": "recommend",
    "入驻通道": "onboarding",
    "物流仓储": "logistics",
    "收款支付": "payments",
    "选品参考": "sourcing",
    "东南亚平台": "sea",
    "社交媒体": "social",
    "代理IP": "proxy-ip",
    "视频剪辑": "video-edit",
    "指纹检测": "fingerprint",
    "短信接码": "sms",
    "货源网站": "supply",
    "知产财税": "ip-tax",
    "培训服务": "training-svc",
    "跨境平台": "platforms",
    "其他工具": "other",
}


def fetch(url: str) -> str:
    response = httpx.get(url, timeout=40, follow_redirects=True, headers=HEADERS)
    response.raise_for_status()
    return response.text


def blocked(text: str) -> bool:
    low = (text or "").lower()
    return any(word.lower() in low for word in BLOCK)


def favicon(url: str) -> str:
    host = url.split("/")[2]
    return f"https://www.google.com/s2/favicons?domain={host}&sz=64"


def sections(html: str, mapping: dict[str, str]) -> list[tuple[str, str, str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    menus = [node.get_text(strip=True) for node in soup.select(".amz-peg-menu-item")]
    wraps = soup.select(".amz-tab-wrapper")
    if len(wraps) == len(menus) + 1:
        wraps = wraps[1:]
    rows = []
    for index, wrap in enumerate(wraps):
        name = menus[index] if index < len(menus) else ""
        slug = mapping.get(name)
        if not slug:
            continue
        for anchor in wrap.select("a[href^=http]"):
            url = (anchor.get("href") or "").split("?")[0].rstrip("/")
            if not url.startswith("http") or any(host in url for host in SKIP_HOSTS):
                continue
            title_el = anchor.select_one(".amz-item-title")
            title = title_el.get_text(strip=True) if title_el else anchor.get_text(" ", strip=True)
            intro_el = anchor.select_one(".amz-item-intro")
            intro = intro_el.get("title") or intro_el.get_text(strip=True) if intro_el else ""
            if title and not blocked(title) and not blocked(url):
                rows.append((slug, title[:160], url[:500], (intro or "")[:400]))
    return rows


def existing_urls(db) -> set[str]:
    return set(db.scalars(select(Link.url)).all())


def insert_rows(db, tab_slug: str, rows: list[tuple], known: set[str]) -> list[int]:
    tab = db.scalar(select(Tab).where(Tab.slug == tab_slug))
    if not tab:
        return []
    ids = []
    for slug, title, url, intro in rows:
        if url in known:
            continue
        category = db.scalar(select(Category).where(Category.tab_id == tab.id, Category.slug == slug))
        if not category:
            continue
        link = Link(
            category_id=category.id,
            title_en=title,
            title_zh=title,
            description_en=intro,
            description_zh=intro,
            url=url,
            logo_url=favicon(url),
            status="published",
            source="crawl",
        )
        db.add(link)
        db.flush()
        known.add(url)
        ids.append(link.id)
    return ids


def backup(ids: list[int]) -> Path:
    db = SessionLocal()
    folder = Path(__file__).resolve().parents[1] / ".local-mysql" / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    path = folder / f"directory-{stamp}.sql"
    try:
        lines = [
            "-- NEXA directory links crawled today",
            "SET NAMES utf8mb4;",
        ]
        if ids:
            rows = db.scalars(select(Link).where(Link.id.in_(ids))).all()
            for row in rows:
                def q(value: str) -> str:
                    return "'" + (value or "").replace("\\", "\\\\").replace("'", "''") + "'"

                lines.append(
                    "INSERT INTO links (id, category_id, title_en, title_zh, description_en, description_zh, url, logo_url, is_free, is_hot, vip_badge, status, source, sort, created_at) VALUES ("
                    f"{row.id}, {row.category_id}, {q(row.title_en)}, {q(row.title_zh)}, {q(row.description_en)}, {q(row.description_zh)}, {q(row.url)}, {q(row.logo_url)}, "
                    f"{int(row.is_free)}, {int(row.is_hot)}, {int(row.vip_badge)}, {q(row.status)}, {q(row.source)}, {row.sort}, {q(row.created_at.strftime('%Y-%m-%d %H:%M:%S') if row.created_at else '')});"
                )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
    finally:
        db.close()


def sync() -> tuple[int, Path]:
    from fill_media import main as fill_media
    from fill_tg import main as fill_tg

    started = datetime.utcnow().replace(microsecond=0)
    db = SessionLocal()
    try:
        known = existing_urls(db)
        before = len(known)
        ai = sections(fetch("https://www.amz123.com/ai"), AI_SLUG)
        cross = sections(fetch("https://www.tt123.com/"), CROSS_SLUG)
        print("fetched", "ai", len(ai), "cross", len(cross))
        insert_rows(db, "ai", ai, known)
        insert_rows(db, "cross-border", cross, known)
        db.commit()
        print("boards new", len(known) - before)
    finally:
        db.close()
    fill_media()
    fill_tg()
    db = SessionLocal()
    try:
        day = started.replace(hour=0, minute=0, second=0, microsecond=0)
        ids = list(db.scalars(select(Link.id).where(Link.created_at >= day, Link.source == "crawl")).all())
    finally:
        db.close()
    path = backup(ids)
    print("backup", path, "rows", len(ids))
    return len(ids), path


if __name__ == "__main__":
    sync()
