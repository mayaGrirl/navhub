import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings


BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml"}
SKIP_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".css", ".js", ".pdf", ".zip", ".mp4", ".ico", ".woff", ".woff2")


def _proxy_list(limit: int = 16) -> list[str]:
    base = (settings.proxy_pool_url or "").rstrip("/")
    if not base:
        raise RuntimeError("代理池未配置")
    found = []
    for _ in range(limit * 2):
        try:
            response = httpx.get(f"{base}/acquire", timeout=3)
            proxy = response.json().get("proxy") if response.status_code == 200 else None
        except httpx.HTTPError:
            proxy = None
        if proxy and proxy not in found:
            found.append(proxy)
        if len(found) >= limit:
            break
    if not found:
        raise RuntimeError("代理池是空的")
    return found


def _open(url: str):
    last = "没有可用代理"
    for proxy in _proxy_list():
        try:
            with httpx.Client(timeout=8, follow_redirects=True, max_redirects=5, headers=BROWSER, proxy=proxy) as client:
                response = client.get(url)
            if response.status_code < 400 and response.text:
                return response
            last = f"HTTP {response.status_code}"
        except Exception as exc:
            last = exc.__class__.__name__
    raise RuntimeError(last)


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


def collect_page(url: str) -> list[dict]:
    url = _public_url(url)
    response = _open(url)
    soup = BeautifulSoup(response.text, "html.parser")
    found = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        title = " ".join(anchor.get_text(" ", strip=True).split())
        if not title or len(title) < 2 or len(title) > 80:
            continue
        href = urljoin(response.url, anchor["href"]).split("#")[0]
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            continue
        path = parsed.path.lower()
        if any(path.endswith(ext) for ext in SKIP_EXT):
            continue
        key = href.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        image = ""
        img = anchor.find("img")
        if img and img.get("src"):
            image = urljoin(response.url, img["src"])[:500]
        found.append({"title": title[:180], "url": href[:500], "description": "", "logo_url": image})
        if len(found) >= 40:
            break
    if not found:
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        if title:
            found.append({"title": title[:180], "url": str(response.url)[:500], "description": "", "logo_url": ""})
    return found


import threading
import time
from datetime import datetime, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import CrawlItem, CrawlJob, CrawlLog, Link

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
        _log(db, job_id, f"开始采集 {job.list_url}")
        if _stopped(job_id):
            job.status = "stopped"
            job.message = "已停止"
            _log(db, job_id, "已停止")
            db.commit()
            return
        try:
            pages = collect_page(job.list_url)
        except Exception as exc:
            job.status = "error"
            job.message = str(exc)[:500]
            job.last_run_at = datetime.utcnow()
            _log(db, job_id, f"打开失败：{job.message}")
            db.commit()
            return
        _log(db, job_id, f"页面已打开，识别到 {len(pages)} 个站点")
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
            job.status = "done" if found else "error"
            job.message = "" if found else "页面里没有可采集的站点名称"
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

    threading.Thread(target=loop, daemon=True).start()
