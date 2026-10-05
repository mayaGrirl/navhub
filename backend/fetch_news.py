import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models import Announcement, NewsItem

FEEDS = [
    ("Hacker News", "https://hnrss.org/frontpage"),
    ("BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
]


def text(node, name: str) -> str:
    found = node.find(name)
    return (found.text or "").strip() if found is not None and found.text else ""


def parse_date(value: str):
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).replace(tzinfo=None)
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def main() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    added = 0
    try:
        if not db.scalar(select(Announcement.id)):
            db.add(Announcement(title_en="Welcome", title_zh="欢迎", body_en="Directory notices show up here.", body_zh="系统消息会显示在这里。", enabled=True))
        for source, url in FEEDS:
            try:
                response = httpx.get(url, timeout=20, follow_redirects=True, headers={"User-Agent": "NavhubBot/1.0"})
                response.raise_for_status()
                root = ET.fromstring(response.content)
            except Exception as exc:
                print("skip", source, exc.__class__.__name__)
                continue
            for item in list(root.iter("item"))[:12]:
                link = text(item, "link")
                title = text(item, "title")
                if not link or not title or db.scalar(select(NewsItem).where(NewsItem.url == link)):
                    continue
                summary = text(item, "description")
                db.add(
                    NewsItem(
                        title=title[:300],
                        url=link[:500],
                        source=source,
                        summary=summary[:400],
                        published_at=parse_date(text(item, "pubDate")),
                    )
                )
                added += 1
        db.commit()
        print("news", added)
    finally:
        db.close()


if __name__ == "__main__":
    main()
