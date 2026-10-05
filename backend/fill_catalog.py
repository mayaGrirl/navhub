"""Insert public directory links. Titles come from each site's own page when the fetch works."""

from sqlalchemy import select

from app.crawl import fetch_meta
from app.db import SessionLocal
from app.models import Category, Link, Tab

CATALOG = {
    ("ai", "chat"): ("AI Chat", "AI聊天", [
        ("https://chatgpt.com", "ChatGPT", False, True),
        ("https://claude.ai", "Claude", False, True),
        ("https://gemini.google.com", "Gemini", True, True),
        ("https://kimi.moonshot.cn", "Kimi", True, True),
        ("https://chat.deepseek.com", "DeepSeek", True, True),
    ]),
    ("ai", "image"): ("AI Image", "AI图像", [
        ("https://www.midjourney.com", "Midjourney", False, True),
        ("https://leonardo.ai", "Leonardo", True, False),
        ("https://firefly.adobe.com", "Firefly", False, False),
    ]),
    ("ai", "writing"): ("AI Writing", "AI写作", [
        ("https://www.notion.so", "Notion", True, False),
        ("https://grammarly.com", "Grammarly", True, False),
        ("https://www.jasper.ai", "Jasper", False, False),
    ]),
    ("ai", "coding"): ("AI Coding", "AI编程", [
        ("https://github.com/features/copilot", "GitHub Copilot", False, True),
        ("https://cursor.com", "Cursor", True, True),
        ("https://codeium.com", "Codeium", True, False),
    ]),
    ("cross-border", "sourcing"): ("Sourcing", "选品", [
        ("https://www.amazon.com", "Amazon", False, True),
        ("https://www.aliexpress.com", "AliExpress", False, False),
        ("https://sellercentral.amazon.com", "Seller Central", False, False),
    ]),
    ("cross-border", "logistics"): ("Logistics", "物流", [
        ("https://www.yunexpress.com", "YunExpress", False, False),
        ("https://www.17track.net", "17TRACK", True, True),
    ]),
    ("resources", "reports"): ("Reports", "报告", [
        ("https://arxiv.org", "arXiv", True, True),
        ("https://huggingface.co", "Hugging Face", True, True),
    ]),
    ("media", "video"): ("Video", "视频", [
        ("https://www.youtube.com", "YouTube", True, True),
        ("https://www.bilibili.com", "Bilibili", True, True),
    ]),
    ("media", "audio"): ("Audio", "音频", [
        ("https://open.spotify.com", "Spotify", True, False),
        ("https://podcasts.apple.com", "Apple Podcasts", True, False),
    ]),
}


def favicon(url: str) -> str:
    host = url.split("/")[2]
    return f"https://www.google.com/s2/favicons?domain={host}&sz=64"


def main() -> None:
    db = SessionLocal()
    added = 0
    try:
        example = db.scalar(select(Link).where(Link.url == "https://example.com"))
        if example:
            db.delete(example)
        for (tab_slug, cat_slug), (title_en, title_zh, items) in CATALOG.items():
            tab = db.scalar(select(Tab).where(Tab.slug == tab_slug))
            if not tab:
                continue
            category = db.scalar(select(Category).where(Category.tab_id == tab.id, Category.slug == cat_slug))
            if not category:
                category = Category(tab_id=tab.id, slug=cat_slug, title_en=title_en, title_zh=title_zh, sort=10)
                db.add(category)
                db.flush()
            for url, name, is_free, is_hot in items:
                if db.scalar(select(Link).where(Link.url == url)):
                    continue
                title = name
                description = ""
                logo = favicon(url)
                try:
                    meta = fetch_meta(url)
                    title = meta["title"] or name
                    description = meta["description"]
                    logo = meta["logo_url"] or logo
                except Exception:
                    description = "Official site."
                db.add(
                    Link(
                        category_id=category.id,
                        title_en=name,
                        title_zh=name,
                        description_en=(description or title)[:500],
                        description_zh=(description or title)[:500],
                        url=url,
                        logo_url=logo[:500],
                        is_free=is_free,
                        is_hot=is_hot,
                        status="published",
                        source="crawl",
                    )
                )
                added += 1
                print("added", name)
        db.commit()
        print("total", added)
    finally:
        db.close()


if __name__ == "__main__":
    main()
