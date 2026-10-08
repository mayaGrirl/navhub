import ipaddress
import socket
import time
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings


BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml"}
SKIP_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".css", ".js", ".pdf", ".zip", ".mp4", ".ico", ".woff", ".woff2")


_proxies: list[str] = []
_proxies_at = 0.0
_good = ""


def _proxy_list() -> list[str]:
    global _proxies_at
    base = (settings.proxy_pool_url or "").rstrip("/")
    if not base:
        raise RuntimeError("代理池未配置")
    now = time.time()
    if _proxies and now - _proxies_at < 20:
        found = list(_proxies)
    else:
        try:
            response = httpx.get(f"{base}/alive", timeout=8)
            response.raise_for_status()
            items = response.json().get("items") or []
        except Exception as exc:
            raise RuntimeError("读取有效代理失败") from exc
        found = []
        for item in items:
            url = item.get("url") if isinstance(item, dict) else item
            if url and url not in found:
                found.append(url)
        if not found:
            raise RuntimeError("代理池里没有有效代理")
        _proxies[:] = found
        _proxies_at = now
    if _good in found:
        found.remove(_good)
        found.insert(0, _good)
    return found


def _get(url: str, proxy: str, follow: bool):
    with httpx.Client(timeout=6, follow_redirects=follow, max_redirects=4, headers=BROWSER, proxy=proxy) as client:
        return client.get(url)


def _open(url: str):
    global _good
    proxies = _proxy_list()
    last = "没有可用代理"
    targets = [url]
    parsed = urlparse(url)
    if parsed.scheme == "https":
        targets.append(parsed._replace(scheme="http").geturl())
    for target in targets:
        follow = target == url
        for proxy in proxies:
            try:
                response = _get(target, proxy, follow)
                if response.status_code < 400 and (response.text or "").strip():
                    _good = proxy
                    return response
                last = f"HTTP {response.status_code}"
            except Exception as exc:
                last = exc.__class__.__name__
    raise RuntimeError(f"{last}，已试完 {len(proxies)} 个有效代理")


def _public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("url must be http or https")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 80)}
    except socket.gaierror as exc:
        raise ValueError("could not resolve host") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("that address is not allowed")
    return url


def fetch_meta(url: str) -> dict:
    url = _public_url(url)
    response = _open(url)
    soup = BeautifulSoup(response.text, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    description = ""
    desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if desc and desc.get("content"):
        description = desc["content"].strip()
    image = ""
    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        image = urljoin(url, og["content"])
    return {"title": title[:180], "description": description[:500], "logo_url": image[:500], "url": url}


def _label(anchor) -> str:
    title = " ".join(anchor.get_text(" ", strip=True).split())
    if not title:
        title = (anchor.get("title") or anchor.get("aria-label") or "").strip()
    if not title:
        img = anchor.find("img")
        if img:
            title = (img.get("alt") or "").strip()
    return " ".join(title.split())


def _push(found, seen, title, href, image=""):
    parsed = urlparse(href)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        return
    if host in {"localhost"} or host.endswith(".local"):
        return
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return
    except ValueError:
        pass
    path = parsed.path.lower()
    if any(path.endswith(ext) for ext in SKIP_EXT):
        return
    key = href.rstrip("/")
    if key in seen or len(title) < 2 or len(title) > 80:
        return
    seen.add(key)
    found.append({"title": title[:180], "url": href[:500], "description": "", "logo_url": (image or "")[:500]})


def collect_page(url: str) -> list[dict]:
    url = _public_url(url)
    response = _open(url)
    text = response.text or ""
    soup = BeautifulSoup(text, "html.parser")
    found = []
    seen = set()
    if soup.find("item") or soup.find("entry"):
        for node in soup.find_all(["item", "entry"])[:40]:
            title = node.find("title")
            link = node.find("link")
            name = title.get_text(strip=True) if title else ""
            href = ""
            if link and link.get("href"):
                href = link["href"]
            elif link:
                href = link.get_text(strip=True)
            if name and href:
                _push(found, seen, name, urljoin(str(response.url), href))
        if found:
            return found
    for anchor in soup.find_all("a", href=True):
        title = _label(anchor)
        if not title:
            continue
        href = urljoin(str(response.url), anchor["href"]).split("#")[0]
        image = ""
        img = anchor.find("img")
        if img and img.get("src"):
            image = urljoin(str(response.url), img["src"])
        _push(found, seen, title, href, image)
        if len(found) >= 40:
            break
    if not found:
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        og = soup.find("meta", attrs={"property": "og:title"})
        if og and og.get("content"):
            title = og["content"].strip()
        if title:
            found.append({"title": title[:180], "url": str(response.url)[:500], "description": "", "logo_url": ""})
    return found


def search_web(keyword: str) -> list[dict]:
    query = keyword.strip()
    if not query:
        raise RuntimeError("请填写关键词或网址")
    pages = []
    seen_host = set()
    skip_hosts = ("duckduckgo.com", "bing.com", "microsoft.com", "google.com", "gstatic.com")

    def take(title, href):
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [""])[0])
        href = href.split("#")[0]
        if not href.startswith("http"):
            return
        host = (urlparse(href).hostname or "").lower()
        if not host or any(host.endswith(item) for item in skip_hosts) or host in seen_host:
            return
        seen_host.add(host)
        pages.append({"title": (title or host)[:180], "url": href[:500], "description": "", "logo_url": ""})

    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    response = _open(url)
    soup = BeautifulSoup(response.text, "html.parser")
    anchors = soup.select("a.result__a") or soup.select("a[href*='uddg=']")
    for anchor in anchors:
        take(" ".join(anchor.get_text(" ", strip=True).split()), anchor.get("href") or "")
        if len(pages) >= 40:
            return pages
    if not pages:
        response = _open(f"https://www.bing.com/search?q={quote_plus(query)}&count=30")
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.select("li.b_algo h2 a"):
            take(" ".join(anchor.get_text(" ", strip=True).split()), anchor.get("href") or "")
            if len(pages) >= 40:
                break
    if not pages:
        raise RuntimeError("没有搜到可收录的站点")
    return pages


import threading
import time
from datetime import datetime, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Category, CrawlItem, CrawlJob, CrawlLog, Link, Tab
from app.urls import norm_url

_lock = threading.Lock()
_running: set[int] = set()
_stops: dict[int, threading.Event] = {}


def start_job(job_id: int) -> bool:
    with _lock:
        if job_id in _running:
            return False
        _running.add(job_id)
        _stops[job_id] = threading.Event()
    threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return True


def stop_job(job_id: int) -> None:
    event = _stops.get(job_id)
    if event:
        event.set()


def _stopped(job_id: int) -> bool:
    event = _stops.get(job_id)
    return bool(event and event.is_set())


def _log(db, job_id: int, message: str) -> None:
    db.add(CrawlLog(job_id=job_id, message=message[:500]))
    db.commit()


def _run_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(CrawlJob, job_id)
        if not job:
            return
        job.status = "running"
        job.message = ""
        db.commit()
        _log(db, job_id, f"开始采集 {job.keyword or job.list_url or job.name}")
        if _stopped(job_id):
            job.status = "stopped"
            job.message = "已停止"
            _log(db, job_id, "已停止")
            db.commit()
            return
        try:
            if (job.list_url or "").strip():
                _log(db, job_id, f"按网址采集 {job.list_url}")
                pages = collect_page(job.list_url)
            else:
                _log(db, job_id, f"按关键词全网采集 {job.keyword or job.name}")
                pages = search_web(job.keyword or job.name)
        except Exception as exc:
            job.status = "error"
            job.message = str(exc)[:500]
            job.last_run_at = datetime.utcnow()
            _log(db, job_id, f"打开失败：{job.message}")
            db.commit()
            return
        _log(db, job_id, f"识别到 {len(pages)} 个站点")
        found = 0
        for page in pages:
            if _stopped(job_id):
                job.status = "stopped"
                job.message = "已停止"
                _log(db, job_id, "已停止")
                break
            link = page["url"]
            exists = db.scalar(select(CrawlItem.id).where(CrawlItem.url == link)) or db.scalar(select(Link.id).where(Link.url == link))
            if exists:
                _log(db, job_id, f"已有，跳过 {page['title']}")
                continue
            db.add(CrawlItem(
                job_id=job.id,
                category_id=job.category_id,
                title=page["title"] or link,
                url=link,
                description=page["description"],
                logo_url=page["logo_url"],
            ))
            found += 1
            _log(db, job_id, f"收录待审 {page['title']}")
        else:
            job.status = "done"
            job.message = "" if found else "没有新的站点，已有记录都跳过了"
            if not found:
                _log(db, job_id, job.message)
        job.found_count = (job.found_count or 0) + found
        job.last_run_at = datetime.utcnow()
        if job.status == "done":
            _log(db, job_id, f"完成，新增 {found} 条")
        db.commit()
    finally:
        with _lock:
            _running.discard(job_id)
            _stops.pop(job_id, None)
        db.close()


def crawl_open_tabs() -> None:
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        due = None
        rows = db.scalars(select(Tab).where(Tab.auto_crawl.is_(True), Tab.kind == "links").order_by(Tab.id)).all()
        for row in rows:
            if not row.crawled_at or row.crawled_at + timedelta(hours=24) <= now:
                due = row.id
                break
    finally:
        db.close()
    if due:
        _crawl_tab(due)


def _crawl_tab(tab_id: int) -> None:
    db = SessionLocal()
    try:
        tab = db.get(Tab, tab_id)
        if not tab or not tab.auto_crawl or tab.kind != "links":
            return
        categories = db.scalars(
            select(Category).where(Category.tab_id == tab.id, Category.visible.is_(True)).order_by(Category.sort, Category.id)
        ).all()
        added = 0
        searched = False
        for category in categories[:8]:
            current = db.get(Tab, tab_id)
            if not current or not current.auto_crawl:
                break
            keyword = f"{tab.title_zh or tab.title_en} {category.title_zh or category.title_en}".strip()
            try:
                pages = search_web(keyword)
                searched = True
            except Exception as exc:
                print("tab search failed", tab.slug, exc.__class__.__name__)
                continue
            for page in pages[:8]:
                key = norm_url(page["url"])
                if not key or db.scalar(select(Link.id).where(Link.norm_url == key)):
                    continue
                db.add(Link(
                    category_id=category.id,
                    title_en=(page["title"] or page["url"])[:160],
                    title_zh=(page["title"] or page["url"])[:160],
                    description_en="",
                    description_zh="",
                    url=page["url"][:500],
                    norm_url=key[:500],
                    logo_url=(page.get("logo_url") or "")[:500],
                    status="published",
                    source="crawl",
                    counts_ready=True,
                    clicks_ready=True,
                ))
                added += 1
        current = db.get(Tab, tab_id)
        if current:
            current.crawled_at = datetime.utcnow() if searched or not categories else datetime.utcnow() - timedelta(hours=23)
        db.commit()
        if added:
            from app.routers.public import drop_public_cache
            drop_public_cache()
        print("tab crawl", tab_id, added)
    finally:
        db.close()


def schedule_jobs() -> None:
    def loop():
        while True:
            time.sleep(60)
            db = SessionLocal()
            try:
                now = datetime.utcnow()
                rows = db.scalars(select(CrawlJob).where(CrawlJob.enabled.is_(True), CrawlJob.status != "running")).all()
                due = []
                for row in rows:
                    gap = timedelta(minutes=max(1, row.interval_minutes or 1440))
                    if not row.last_run_at or row.last_run_at + gap <= now:
                        due.append(row.id)
                for job_id in due:
                    start_job(job_id)
            finally:
                db.close()
            try:
                crawl_open_tabs()
            except Exception as exc:
                print("tab crawl failed", exc.__class__.__name__)

    threading.Thread(target=loop, daemon=True).start()
