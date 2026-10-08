import html
import re
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx
from sqlalchemy import delete, inspect, select, text

from app.db import Base, SessionLocal, engine
from app.models import Announcement, NewsItem

_TAG = re.compile(r"<[^>]*>?")


def plain_text(value: str) -> str:
    text = html.unescape(value or "")
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


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
    ("world", "联合早报", "https://www.zaobao.com/rss/realtime/world"),
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
    ("house", "Guardian Property", "https://www.theguardian.com/society/housing/rss"),
    ("fashion", "Harper's Bazaar", "https://www.harpersbazaar.com/rss/all.xml/"),
    ("military", "Defense News", "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("games", "Polygon", "https://www.polygon.com/rss/index.xml"),
    ("science", "ScienceDaily", "https://www.sciencedaily.com/rss/all.xml"),
    ("digital", "The Verge", "https://www.theverge.com/rss/index.xml"),
    ("ai-news", "TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("jobs", "Guardian Work", "https://www.theguardian.com/money/work-and-careers/rss"),
    ("startup", "TechCrunch", "https://techcrunch.com/feed/"),
    ("history", "History", "https://www.history.com/rss"),
    ("parenting", "Guardian Family", "https://www.theguardian.com/lifeandstyle/parents-and-parenting/rss"),
    ("tech", "Hacker News", "https://hnrss.org/frontpage"),
    ("tech", "BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("tech", "The Verge", "https://www.theverge.com/rss/index.xml"),
    ("society", "Google 新闻", "https://news.google.com/rss?hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("society", "Google News", "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"),
    ("world", "Google 国际", "https://news.google.com/rss/headlines/section/topic/WORLD?hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("world", "Google World", "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en"),
    ("world", "卫报国际", "https://www.theguardian.com/world/rss"),
    ("world", "半岛电视台", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("tech", "Google 科技", "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("tech", "Google Technology", "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en"),
    ("tech", "36氪", "https://36kr.com/feed"),
    ("tech", "Solidot", "https://www.solidot.org/index.rss"),
    ("tech", "阮一峰", "http://www.ruanyifeng.com/blog/atom.xml"),
    ("business", "Google 财经", "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("business", "Google Business", "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"),
    ("business", "纽约时报", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
    ("entertainment", "Google 娱乐", "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("entertainment", "Google Entertainment", "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=en-US&gl=US&ceid=US:en"),
    ("sports", "Google 体育", "https://news.google.com/rss/headlines/section/topic/SPORTS?hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("sports", "Google Sports", "https://news.google.com/rss/headlines/section/topic/SPORTS?hl=en-US&gl=US&ceid=US:en"),
    ("health", "Google 健康", "https://news.google.com/rss/headlines/section/topic/HEALTH?hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("health", "Google Health", "https://news.google.com/rss/headlines/section/topic/HEALTH?hl=en-US&gl=US&ceid=US:en"),
    ("science", "Google 科学", "https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("science", "Google Science", "https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=en-US&gl=US&ceid=US:en"),
    ("film", "Google 影视", "https://news.google.com/rss/search?q=电影+OR+音乐&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("games", "Google 游戏", "https://news.google.com/rss/search?q=游戏+OR+电竞&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("auto", "Google 汽车", "https://news.google.com/rss/search?q=汽车&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("startup", "Google 创投", "https://news.google.com/rss/search?q=创业+OR+融资&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("ai-news", "Google 人工智能", "https://news.google.com/rss/search?q=人工智能+OR+AI&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("society", "百度新闻", "http://news.baidu.com/n?cmd=4&class=civilnews&tn=rss"),
    ("tech", "百度科技", "http://news.baidu.com/n?cmd=4&class=technnews&tn=rss"),
]


ATOM = "{http://www.w3.org/2005/Atom}"


def node_text(node, name: str) -> str:
    found = node.find(name)
    return (found.text or "").strip() if found is not None and found.text else ""


def clean_url(url: str) -> str:
    if "news.google.com" in url:
        return url[:500]
    return url.split("?")[0][:500]


def feed_entries(root):
    items = list(root.iter("item"))
    if items:
        return items
    return list(root.iter(f"{ATOM}entry"))


def entry_link(item) -> str:
    text = node_text(item, "link") or node_text(item, f"{ATOM}link")
    if text:
        return text
    for name in ("link", f"{ATOM}link"):
        for el in item.findall(name):
            href = el.get("href")
            if href:
                return href
    return ""


def entry_title(item) -> str:
    return node_text(item, "title") or node_text(item, f"{ATOM}title")


def entry_date(item) -> str:
    return node_text(item, "pubDate") or node_text(item, f"{ATOM}published") or node_text(item, f"{ATOM}updated")


SHANGHAI = timezone(timedelta(hours=8))


def today_start() -> datetime:
    now = datetime.now(SHANGHAI).replace(tzinfo=None)
    return now - timedelta(hours=24)


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
            for item in feed_entries(root)[:8]:
                link = clean_url(entry_link(item))
                title = entry_title(item)
                if not link or not title or (category, link) in seen or db.scalar(select(NewsItem).where(NewsItem.url == link, NewsItem.category == category)):
                    continue
                seen.add((category, link))
                summary = plain_text(node_text(item, "description") or node_text(item, f"{ATOM}summary"))
                db.add(
                    NewsItem(
                        title=plain_text(title)[:300],
                        url=link[:500],
                        source=source,
                        category=category,
                        summary=summary[:400],
                        published_at=parse_date(entry_date(item)) or datetime.now(SHANGHAI).replace(tzinfo=None),
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
        time.sleep(2 * 60)
        while True:
            try:
                main()
            except Exception as exc:
                print("news sync failed", exc.__class__.__name__)
            time.sleep(300)

    threading.Thread(target=loop, daemon=True).start()


if __name__ == "__main__":
    main()
