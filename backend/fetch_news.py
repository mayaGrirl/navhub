import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx
from sqlalchemy import delete, inspect, select, text

from app.db import Base, SessionLocal, engine
from app.models import Announcement, NewsItem

FEEDS = [
    ("society", "BBC 中文", "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml"),
    ("society", "NPR", "https://feeds.npr.org/1001/rss.xml"),
    ("society", "BBC News", "https://feeds.bbci.co.uk/news/rss.xml"),
    ("tech", "IT之家", "https://www.ithome.com/rss/"),
    ("tech", "少数派", "https://sspai.com/feed"),
    ("tech", "爱范儿", "https://www.ifanr.com/feed"),
    ("digital", "IT之家", "https://www.ithome.com/rss/"),
    ("business", "虎嗅", "https://www.huxiu.com/rss/0.xml"),
    ("games", "机核", "https://www.gcores.com/rss"),
    ("entertainment", "新浪娱乐", "https://rss.sina.com.cn/ent/hot_roll.xml"),
    ("sports", "新浪体育", "https://rss.sina.com.cn/sports/global/focus.xml"),
    ("society", "中国新闻网", "https://www.chinanews.com.cn/rss/scroll-news.xml"),
    ("world", "联合早报", "https://www.zaobao.com/rss/realtime/china"),
    ("world", "BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("entertainment", "BBC Entertainment", "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"),
    ("film", "Variety", "https://variety.com/feed/"),
    ("business", "BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("sports", "BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml"),
    ("health", "BBC Health", "https://feeds.bbci.co.uk/news/health/rss.xml"),
    ("education", "BBC Education", "https://feeds.bbci.co.uk/news/education/rss.xml"),
    ("travel", "Conde Nast Traveler", "https://www.cntraveler.com/feed/rss"),
    ("food", "Bon Appetit", "https://www.bonappetit.com/feed/rss"),
    ("auto", "Car and Driver", "https://www.caranddriver.com/rss/all.xml/"),
    ("house", "Guardian Money", "https://www.theguardian.com/money/rss"),
    ("fashion", "Harper's Bazaar", "https://www.harpersbazaar.com/rss/all.xml/"),
    ("military", "BBC News", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("games", "Polygon", "https://www.polygon.com/rss/index.xml"),
    ("science", "ScienceDaily", "https://www.sciencedaily.com/rss/all.xml"),
    ("digital", "The Verge", "https://www.theverge.com/rss/index.xml"),
    ("ai-news", "Hacker News", "https://hnrss.org/frontpage"),
    ("jobs", "Guardian Work", "https://www.theguardian.com/money/work-and-careers/rss"),
    ("startup", "TechCrunch", "https://techcrunch.com/feed/"),
    ("history", "History", "https://www.history.com/rss"),
    ("parenting", "Guardian Family", "https://www.theguardian.com/lifeandstyle/parents-and-parenting/rss"),
    ("tech", "Hacker News", "https://hnrss.org/frontpage"),
    ("tech", "BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("tech", "The Verge", "https://www.theverge.com/rss/index.xml"),
]


def node_text(node, name: str) -> str:
    found = node.find(name)
    return (found.text or "").strip() if found is not None and found.text else ""


def clean_url(url: str) -> str:
    return url.split("?")[0][:500]


SHANGHAI = timezone(timedelta(hours=8))


def today_start() -> datetime:
    now = datetime.now(SHANGHAI)
    return now.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)


def parse_date(value: str):
    parsed = None
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(SHANGHAI).replace(tzinfo=None)


def main() -> None:
    Base.metadata.create_all(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("news_items")}
    if "category" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE news_items ADD COLUMN category VARCHAR(40) NOT NULL DEFAULT 'tech'"))
    with engine.begin() as conn:
        indexes = conn.execute(text("SHOW INDEX FROM news_items WHERE Key_name='url' AND Non_unique=0")).fetchall()
        if indexes:
            conn.execute(text("ALTER TABLE news_items DROP INDEX url"))
    db = SessionLocal()
    added = 0
    seen = set()
    try:
        if not db.scalar(select(Announcement.id)):
            db.add(Announcement(title_en="Welcome", title_zh="欢迎", body_en="Directory notices show up here.", body_zh="系统消息会显示在这里。", enabled=True))
        for category, source, url in FEEDS:
            try:
                response = httpx.get(url, timeout=20, follow_redirects=True, headers={"User-Agent": "NavhubBot/1.0"})
                response.raise_for_status()
                root = ET.fromstring(response.content)
            except Exception as exc:
                print("skip", source, exc.__class__.__name__)
                continue
            for item in list(root.iter("item"))[:12]:
                link = clean_url(node_text(item, "link"))
                title = node_text(item, "title")
                if not link or not title or (category, link) in seen or db.scalar(select(NewsItem).where(NewsItem.url == link, NewsItem.category == category)):
                    continue
                seen.add((category, link))
                summary = node_text(item, "description")
                db.add(
                    NewsItem(
                        title=title[:300],
                        url=link[:500],
                        source=source,
                        category=category,
                        summary=summary[:400],
                        published_at=parse_date(node_text(item, "pubDate")),
                    )
                )
                added += 1
        removed = db.execute(delete(NewsItem).where((NewsItem.published_at.is_(None)) | (NewsItem.published_at < today_start()))).rowcount
        db.commit()
        print("news", added, "removed", removed)
    finally:
        db.close()


def schedule_news() -> None:
    def loop():
        while True:
            try:
                main()
            except Exception as exc:
                print("news sync failed", exc.__class__.__name__)
            time.sleep(300)

    threading.Thread(target=loop, daemon=True).start()


if __name__ == "__main__":
    main()
