"""Separate proxy pool. The nav API calls GET /acquire only when PROXY_POOL_URL is set."""

import ipaddress
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import httpx
from fastapi import FastAPI, HTTPException
from pydantic_settings import BaseSettings
from sqlalchemy import DateTime, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from sources import LISTS


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "extra": "ignore"}

    database_url: str = "mysql+pymysql://nav:navpass@127.0.0.1:3306/navproxy?charset=utf8mb4"
    token: str = "change-pool-token"


settings = Settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Proxy(Base):
    __tablename__ = "proxies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(300), unique=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_url: Mapped[str] = mapped_column(String(500))


app = FastAPI(title="Proxy pool")
cursor = {"n": 0}
_lock = threading.Lock()


PROXY_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b")


def public_http(url: str) -> bool:
    host = url.split("://", 1)[-1].split(":", 1)[0]
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified)


def alive(url: str) -> bool:
    if not public_http(url):
        return False
    try:
        response = httpx.get("http://example.com", proxy=url, timeout=4)
        return 200 <= response.status_code < 400
    except httpx.HTTPError:
        return False


def maintain() -> dict:
    if not _lock.acquire(blocking=False):
        return {"busy": True}
    db = SessionLocal()
    added = 0
    removed = 0
    try:
        allowed = list(dict.fromkeys(LISTS))
        allowed_set = set(allowed)
        seen = set()
        for row in list(db.scalars(select(Source)).all()):
            if row.list_url not in allowed_set or row.list_url in seen:
                db.delete(row)
                continue
            seen.add(row.list_url)
        for url in allowed:
            if url not in seen:
                db.add(Source(list_url=url))
        db.commit()
        candidates = []
        for source in db.scalars(select(Source)).all():
            try:
                text = httpx.get(source.list_url, timeout=12, follow_redirects=True).text
            except httpx.HTTPError:
                continue
            candidates.extend(f"http://{item}" for item in PROXY_RE.findall(text))
        known = set(db.scalars(select(Proxy.url)).all())
        fresh = [item for item in dict.fromkeys(candidates) if item not in known and public_http(item)]
        random.shuffle(fresh)
        batch = fresh[:200]
        with ThreadPoolExecutor(max_workers=40) as pool:
            ok = [url for url, good in zip(batch, pool.map(alive, batch)) if good]
        for url in ok:
            db.add(Proxy(url=url, checked_at=datetime.utcnow()))
            added += 1
        stored = list(db.scalars(select(Proxy)).all())
        with ThreadPoolExecutor(max_workers=40) as pool:
            still = list(pool.map(alive, [row.url for row in stored]))
        for row, good in zip(stored, still):
            if good:
                row.checked_at = datetime.utcnow()
            else:
                db.delete(row)
                removed += 1
        db.commit()
        count = len(db.scalars(select(Proxy)).all())
        print("proxy pool", "added", added, "removed", removed, "kept", count, "sources", len(allowed))
        return {"added": added, "removed": removed, "kept": count}
    finally:
        db.close()
        _lock.release()


def schedule() -> None:
    def loop():
        time.sleep(15)
        while True:
            try:
                maintain()
            except Exception as exc:
                print("proxy pool failed", exc.__class__.__name__)
            time.sleep(180)

    threading.Thread(target=loop, daemon=True).start()


@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    schedule()


def _auth(token: str) -> None:
    if token != settings.token:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/acquire")
def acquire():
    db = SessionLocal()
    try:
        rows = db.scalars(select(Proxy).order_by(Proxy.id)).all()
        if not rows:
            return {"proxy": None}
        cursor["n"] = (cursor["n"] + 1) % len(rows)
        return {"proxy": rows[cursor["n"]].url}
    finally:
        db.close()


@app.post("/proxies")
def add_proxy(payload: dict):
    _auth(payload.get("token", ""))
    db = SessionLocal()
    try:
        url = str(payload.get("url") or "")
        if not alive(url):
            raise HTTPException(status_code=400, detail="proxy is not usable")
        row = Proxy(url=url, checked_at=datetime.utcnow())
        db.add(row)
        db.commit()
        return {"id": row.id}
    finally:
        db.close()


@app.get("/sources")
def list_sources():
    db = SessionLocal()
    try:
        rows = db.scalars(select(Source).order_by(Source.id)).all()
        return {"count": len(rows), "items": [{"id": row.id, "url": row.list_url} for row in rows]}
    finally:
        db.close()


@app.delete("/proxies")
def remove_proxy(url: str):
    db = SessionLocal()
    try:
        row = db.scalar(select(Proxy).where(Proxy.url == url))
        if row:
            db.delete(row)
            db.commit()
        return {"ok": True}
    finally:
        db.close()


@app.delete("/sources")
def remove_source(url: str):
    db = SessionLocal()
    try:
        row = db.scalar(select(Source).where(Source.list_url == url))
        if row:
            db.delete(row)
            db.commit()
        return {"ok": True}
    finally:
        db.close()


@app.get("/alive")
def list_alive():
    db = SessionLocal()
    try:
        rows = db.scalars(select(Proxy).order_by(Proxy.checked_at.desc())).all()
        return {
            "count": len(rows),
            "sources": len(LISTS),
            "items": [{"url": row.url, "checked_at": row.checked_at.isoformat() if row.checked_at else None} for row in rows],
        }
    finally:
        db.close()


@app.post("/refresh")
def refresh(payload: dict):
    _auth(payload.get("token", ""))
    return maintain()


@app.post("/sources")
def add_source(payload: dict):
    _auth(payload.get("token", ""))
    db = SessionLocal()
    try:
        row = Source(list_url=payload["list_url"])
        db.add(row)
        db.commit()
        return {"id": row.id}
    finally:
        db.close()
