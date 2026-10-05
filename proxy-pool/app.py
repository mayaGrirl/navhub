"""Separate proxy pool. The nav API calls GET /acquire only when PROXY_POOL_URL is set."""

from datetime import datetime

import httpx
from fastapi import FastAPI, HTTPException
from pydantic_settings import BaseSettings
from sqlalchemy import Boolean, DateTime, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Settings(BaseSettings):
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
    alive: Mapped[bool] = mapped_column(Boolean, default=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_url: Mapped[str] = mapped_column(String(500))


app = FastAPI(title="Proxy pool")
cursor = {"n": 0}


@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)


def _auth(token: str) -> None:
    if token != settings.token:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/acquire")
def acquire():
    db = SessionLocal()
    try:
        rows = db.scalars(select(Proxy).where(Proxy.alive.is_(True)).order_by(Proxy.id)).all()
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
        row = Proxy(url=payload["url"])
        db.add(row)
        db.commit()
        return {"id": row.id}
    finally:
        db.close()


@app.post("/check")
def check(payload: dict):
    _auth(payload.get("token", ""))
    db = SessionLocal()
    try:
        rows = db.scalars(select(Proxy)).all()
        for row in rows:
            try:
                httpx.get("https://example.com", proxy=row.url, timeout=5)
                row.alive = True
            except httpx.HTTPError:
                row.alive = False
            row.checked_at = datetime.utcnow()
        db.commit()
        return {"checked": len(rows)}
    finally:
        db.close()


@app.post("/refresh")
def refresh(payload: dict):
    _auth(payload.get("token", ""))
    db = SessionLocal()
    added = 0
    try:
        sources = db.scalars(select(Source)).all()
        for source in sources:
            try:
                text = httpx.get(source.list_url, timeout=10).text
            except httpx.HTTPError:
                continue
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if not line.startswith("http"):
                    line = f"http://{line}"
                if not db.scalar(select(Proxy).where(Proxy.url == line)):
                    db.add(Proxy(url=line, alive=False))
                    added += 1
        db.commit()
        return {"added": added}
    finally:
        db.close()


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
