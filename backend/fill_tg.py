"""Import public Telegram channels, groups, and bots into the TG tab."""
import re

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Category, Link, Tab

HEADERS = {"User-Agent": "Mozilla/5.0"}
SKIP = ("色情", "成人", "黄色", "开车", "幼女", "萝莉", "裸聊", "约炮", "黄网", "福利姬", "nsfw", "搜片")

CATS = {
    "blog": "blog",
    "搜索机器人": "搜索机器人",
    "搜索群组": "搜索群组",
    "电报本报": "电报本报",
    "电报相关": "电报相关",
    "电报机器人": "电报机器人",
    "币圈相关": "币圈相关",
    "软件黑科技": "软件黑科技",
    "新闻资讯": "新闻资讯",
    "网络资源": "网络资源",
    "节点推荐": "节点推荐",
    "科技玩家": "科技玩家",
    "软件App": "软件App",
    "趣味分享": "趣味分享",
}


def slug_of(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "tg"


def blocked(text: str) -> bool:
    low = text.lower()
    return any(word in low for word in SKIP)


def clean_tme(url: str) -> str:
    url = url.split("?")[0].rstrip("/")
    match = re.match(r"https?://t\.me/([A-Za-z0-9_]{3,})", url)
    if not match:
        return ""
    name = match.group(1)
    if name.lower() in {"share", "joinchat", "addstickers", "boost", "s"}:
        return ""
    return f"https://t.me/{name}"


def get(url: str) -> str:
    response = httpx.get(url, timeout=60, follow_redirects=True, headers=HEADERS)
    response.raise_for_status()
    return response.text


def from_dianbao() -> list[tuple[str, str, str]]:
    soup = BeautifulSoup(get("https://dianbaodaohang.com/"), "html.parser")
    rows = []
    for card in soup.select(".content-card"):
        title_el = card.select_one("h4.tab-title, .tab-title")
        title = title_el.get_text(strip=True) if title_el else ""
        if title not in CATS:
            continue
        for article in card.select("article"):
            name_el = article.select_one(".item-title")
            name = name_el.get_text(strip=True) if name_el else ""
            link = article.select_one('a[href*="t.me"]')
            url = clean_tme(link.get("href")) if link else ""
            if name and url and not blocked(name):
                rows.append((title, name[:160], url))
    return rows


def from_github() -> list[tuple[str, str, str]]:
    text = get("https://raw.githubusercontent.com/AZeC4/TelegramGroup/master/README.md")
    rows = []
    section = "电报相关"
    for line in text.splitlines():
        if line.startswith("#"):
            head = re.sub(r"^#+\s*", "", line)
            if any(word in head for word in ("搜索机器人", "索引机器人")):
                section = "搜索机器人"
            elif any(word in head for word in ("机器人", "Bot")):
                section = "电报机器人"
            elif any(word in head for word in ("币", "金融", "交易所")):
                section = "币圈相关"
            elif any(word in head for word in ("机场", "VPN", "翻墙", "代理")):
                section = "节点推荐"
            elif any(word in head for word in ("新闻", "资讯", "媒体")):
                section = "新闻资讯"
            elif any(word in head for word in ("软件", "应用")):
                section = "软件App"
            elif any(word in head for word in ("社群", "群组")):
                section = "搜索群组"
            elif any(word in head for word in ("教程", "官方", "设置")):
                section = "电报相关"
            elif any(word in head for word in ("网络", "VPS", "主机")):
                section = "科技玩家"
            continue
        if blocked(line):
            continue
        for url in re.findall(r"https?://t\.me/[A-Za-z0-9_]+", line):
            url = clean_tme(url)
            if not url:
                continue
            name = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
            name = re.sub(r"https?://\S+", "", name)
            name = re.sub(r"^[\s\-\*\d\.\)]+", "", name).strip(" -|：:")
            rows.append((section, (name or url.rsplit("/", 1)[-1])[:160], url))
    return rows


TGNAV = {
    "资讯新闻": "新闻资讯",
    "影音资源": "网络资源",
    "资源分享": "网络资源",
    "ios资源": "软件App",
    "软件综合": "软件App",
    "知识学习": "科技玩家",
    "搞笑趣味": "趣味分享",
    "书报刊漫": "网络资源",
    "博客杂谈": "blog",
    "壁纸图片": "网络资源",
    "机场测试": "节点推荐",
    "兴趣社群": "搜索群组",
    "软件社群": "科技玩家",
    "消息收发": "电报机器人",
    "群组管理": "电报机器人",
}


def from_tgnav() -> list[tuple[str, str, str]]:
    rows = []
    for kind in ("channel", "group", "robot"):
        index = BeautifulSoup(get(f"https://www.tgnav.org/{kind}/"), "html.parser")
        pages = []
        for anchor in index.select("a"):
            href = anchor.get("href") or ""
            match = re.search(rf"/{kind}/([^/#]+)/", href)
            if match:
                pages.append(match.group(1))
        for name in dict.fromkeys(pages):
            target = TGNAV.get(name)
            if not target:
                continue
            soup = BeautifulSoup(get(f"https://www.tgnav.org/{kind}/{name}/"), "html.parser")
            for card in soup.select(".md-card"):
                title_el = card.select_one(".md-card-title")
                title = title_el.get("title") or title_el.get_text(strip=True) if title_el else ""
                if blocked(title):
                    continue
                body = card.get_text(" ", strip=True)
                found = re.search(r"https?://t\.me/([A-Za-z0-9_]{3,})", body)
                if found:
                    url = clean_tme(f"https://t.me/{found.group(1)}")
                else:
                    detail = card.select_one('a[href^="/detail/"]')
                    slug = detail.get("href").strip("/").split("/")[-1] if detail else ""
                    url = clean_tme(f"https://t.me/{slug}") if re.fullmatch(r"[A-Za-z0-9_]{3,}", slug) else ""
                if url:
                    rows.append((target, (title or url.rsplit("/", 1)[-1])[:160], url))
    return rows


def main() -> None:
    buckets = {}
    for name, loader in (("dianbao", from_dianbao), ("github", from_github), ("tgnav", from_tgnav)):
        try:
            buckets[name] = loader()
        except Exception as exc:
            print("skip", name, exc.__class__.__name__)
            buckets[name] = []
    db = SessionLocal()
    tab = db.scalar(select(Tab).where(Tab.slug == "telegram"))
    order = max([row.sort for row in db.scalars(select(Category).where(Category.tab_id == tab.id))] or [0]) + 1
    added = 0
    for source, items in buckets.items():
        print(source, len(items))
        for title, name, url in items:
            row = db.scalar(select(Category).where(Category.tab_id == tab.id, Category.title_zh == title))
            if not row:
                row = Category(
                    tab_id=tab.id,
                    slug=slug_of(title) or "tg",
                    title_en=title,
                    title_zh=title,
                    sort=order,
                    visible=True,
                )
                db.add(row)
                db.flush()
                order += 1
            if db.scalar(select(Link).where(Link.category_id == row.id, Link.url == url)):
                continue
            db.add(
                Link(
                    category_id=row.id,
                    title_en=name,
                    title_zh=name,
                    url=url,
                    logo_url="https://www.google.com/s2/favicons?domain=t.me&sz=64",
                    status="published",
                    source="crawl",
                )
            )
            added += 1
    db.commit()
    print("added", added)


if __name__ == "__main__":
    main()
