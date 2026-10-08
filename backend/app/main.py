import os
import socket
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.security import rate_limit, rds

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.routers import admin, auth, public
from app.github_ranks import schedule_daily
from app.crawl import schedule_jobs
from fetch_news import schedule_news
from fill_daily import schedule_directory
from app.seed import seed


def _local_pool_port() -> int | None:
    raw = (settings.proxy_pool_url or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return None
    return parsed.port or (443 if parsed.scheme == "https" else 80)


def _port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def ensure_proxy_pool() -> None:
    port = _local_pool_port()
    if not port or _port_open(port):
        return
    root = Path(__file__).resolve().parents[2]
    log_path = root / ".run" / "pool.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = open(log_path, "ab", buffering=0)
    kwargs = {
        "cwd": root / "proxy-pool",
        "stdout": log,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
        **kwargs,
    )
    log.close()
    print(f"Proxy pool starting on 127.0.0.1:{port}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN display_name VARCHAR(80) NOT NULL DEFAULT ''"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN proxy_token VARCHAR(80) NOT NULL DEFAULT ''"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN proxy_unlimited TINYINT(1) NOT NULL DEFAULT 0"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN proxy_limit INT NULL"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN points INT NOT NULL DEFAULT 0"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE links ADD COLUMN norm_url VARCHAR(500) NOT NULL DEFAULT ''"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE levels MODIFY level INT NOT NULL"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE links ADD COLUMN favorite_count INT NOT NULL DEFAULT 0"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE links ADD COLUMN recommend_count INT NOT NULL DEFAULT 0"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE links ADD COLUMN counts_ready TINYINT(1) NOT NULL DEFAULT 0"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE links ADD COLUMN click_count INT NOT NULL DEFAULT 0"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE links ADD COLUMN clicks_ready TINYINT(1) NOT NULL DEFAULT 0"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN banned TINYINT(1) NOT NULL DEFAULT 0"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN last_ip VARCHAR(64) NOT NULL DEFAULT ''"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE links ADD COLUMN review_note VARCHAR(200) NOT NULL DEFAULT ''"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE links ADD COLUMN client_ip VARCHAR(64) NOT NULL DEFAULT ''"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE links ADD COLUMN points_awarded TINYINT(1) NOT NULL DEFAULT 0"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN totp_confirmed TINYINT(1) NOT NULL DEFAULT 0"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE announcements ADD COLUMN image_url VARCHAR(500) NOT NULL DEFAULT ''"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE announcements ADD COLUMN popup TINYINT(1) NOT NULL DEFAULT 0"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE announcements ADD COLUMN created_at DATETIME NULL"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE ads ADD COLUMN show_placeholder TINYINT(1) NOT NULL DEFAULT 1"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE ads ADD COLUMN updated_at DATETIME NULL"))
        except Exception:
            pass
        for column in (
            "ALTER TABLE tabs ADD COLUMN auto_crawl TINYINT(1) NOT NULL DEFAULT 0",
            "ALTER TABLE tabs ADD COLUMN crawled_at DATETIME NULL",
            "ALTER TABLE crawl_jobs ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'idle'",
            "ALTER TABLE crawl_jobs ADD COLUMN message VARCHAR(500) NOT NULL DEFAULT ''",
            "ALTER TABLE crawl_jobs ADD COLUMN found_count INT NOT NULL DEFAULT 0",
            "ALTER TABLE crawl_jobs ADD COLUMN keyword VARCHAR(120) NOT NULL DEFAULT ''",
            "CREATE TABLE IF NOT EXISTS crawl_logs (id INT PRIMARY KEY AUTO_INCREMENT, job_id INT NOT NULL, message VARCHAR(500) NOT NULL DEFAULT '', created_at DATETIME NULL, INDEX ix_crawl_logs_job (job_id))",
            "ALTER TABLE mail_settings ADD COLUMN gmail_host VARCHAR(120) NOT NULL DEFAULT ''",
            "ALTER TABLE mail_settings ADD COLUMN gmail_port INT NOT NULL DEFAULT 0",
            "ALTER TABLE mail_settings ADD COLUMN gmail_user VARCHAR(200) NOT NULL DEFAULT ''",
            "ALTER TABLE mail_settings ADD COLUMN gmail_pass VARCHAR(200) NOT NULL DEFAULT ''",
            "ALTER TABLE mail_settings ADD COLUMN gmail_from VARCHAR(200) NOT NULL DEFAULT ''",
            "ALTER TABLE mail_settings ADD COLUMN gmail_from_name VARCHAR(80) NOT NULL DEFAULT ''",
            "ALTER TABLE mail_settings ADD COLUMN netease_host VARCHAR(120) NOT NULL DEFAULT ''",
            "ALTER TABLE mail_settings ADD COLUMN netease_port INT NOT NULL DEFAULT 0",
            "ALTER TABLE mail_settings ADD COLUMN netease_user VARCHAR(200) NOT NULL DEFAULT ''",
            "ALTER TABLE mail_settings ADD COLUMN netease_pass VARCHAR(200) NOT NULL DEFAULT ''",
            "ALTER TABLE mail_settings ADD COLUMN netease_from VARCHAR(200) NOT NULL DEFAULT ''",
            "ALTER TABLE mail_settings ADD COLUMN netease_from_name VARCHAR(80) NOT NULL DEFAULT ''",
            "ALTER TABLE mail_settings ADD COLUMN sendgrid_key VARCHAR(300) NOT NULL DEFAULT ''",
            "ALTER TABLE mail_settings ADD COLUMN sendgrid_from VARCHAR(200) NOT NULL DEFAULT ''",
            "ALTER TABLE mail_settings ADD COLUMN sendgrid_from_name VARCHAR(80) NOT NULL DEFAULT ''",
            "ALTER TABLE mail_settings ADD COLUMN mailgun_key VARCHAR(300) NOT NULL DEFAULT ''",
            "ALTER TABLE mail_settings ADD COLUMN mailgun_domain VARCHAR(200) NOT NULL DEFAULT ''",
            "ALTER TABLE mail_settings ADD COLUMN mailgun_region VARCHAR(20) NOT NULL DEFAULT ''",
            "ALTER TABLE mail_settings ADD COLUMN mailgun_from VARCHAR(200) NOT NULL DEFAULT ''",
            "ALTER TABLE mail_settings ADD COLUMN mailgun_from_name VARCHAR(80) NOT NULL DEFAULT ''",
        ):
            try:
                conn.execute(text(column))
            except Exception:
                pass
        try:
            conn.execute(text("UPDATE crawl_jobs SET status = 'stopped' WHERE status = 'running'"))
        except Exception:
            pass
        try:
            conn.execute(text(
                "DELETE m1 FROM link_marks m1 INNER JOIN link_marks m2 "
                "ON m1.user_id = m2.user_id AND m1.link_id = m2.link_id AND m1.kind = m2.kind AND m1.id > m2.id"
            ))
        except Exception:
            pass
        for statement in (
            "CREATE INDEX ix_news_pub ON news_items (published_at, category, id)",
            "CREATE INDEX ix_links_cat ON links (category_id, status, sort, id)",
            "CREATE INDEX ix_links_fav ON links (status, favorite_count)",
            "CREATE INDEX ix_links_rec ON links (status, recommend_count)",
            "CREATE INDEX ix_links_clk ON links (status, click_count)",
            "CREATE UNIQUE INDEX ux_link_marks ON link_marks (user_id, link_id, kind)",
        ):
            try:
                conn.execute(text(statement))
            except Exception:
                pass
        conn.execute(text("UPDATE users SET email = LOWER(TRIM(email))"))
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET totp_confirmed = 1 WHERE totp_enabled = 1"))
        conn.execute(text("UPDATE users SET totp_secret = '' WHERE totp_confirmed = 0"))
    db = SessionLocal()
    try:
        gate = seed(db)
        print(f"Admin gate path: /{gate}")
    finally:
        db.close()
    schedule_daily()
    schedule_news()
    schedule_jobs()
    from app.mailer import schedule_mail
    schedule_mail()
    schedule_directory()
    from app.review import sweep_open

    sweep_open()
    ensure_proxy_pool()
    yield


app = FastAPI(title="Nav API", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(GZipMiddleware, minimum_size=800)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in settings.cors_origins.split(",") if item.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
OPEN_API = ("/api/guard", "/api/proxy", "/api/health")
BOTS = ("scrapy", "python-requests", "aiohttp", "httpclient", "okhttp", "go-http-client", "java/", "libwww", "wget", "phantom", "headless", "selenium", "puppeteer")


@app.middleware("http")
async def anti_scrape(request, call_next):
    path = request.url.path
    if path.startswith("/api") and not path.startswith(OPEN_API):
        ua = (request.headers.get("user-agent") or "").lower()
        if not ua or any(bot in ua for bot in BOTS):
            return JSONResponse({"detail": "blocked"}, status_code=403)
        ip = request.client.host if request.client else "0"
        limit = 40 if path.startswith("/api/search") else 120
        if not rate_limit(f"scrape:{ip}", limit, 60):
            return JSONResponse({"detail": "slow down"}, status_code=429)
        token = request.cookies.get("nav_pass")
        if not token or not rds.get(f"pass:{token}"):
            return JSONResponse({"detail": "guard"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-XSS-Protection"] = "0"
    return response


app.include_router(public.router)
app.include_router(auth.router)
app.include_router(admin.setup_router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"ok": True}
