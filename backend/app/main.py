from contextlib import asynccontextmanager

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
            "ALTER TABLE crawl_jobs ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'idle'",
            "ALTER TABLE crawl_jobs ADD COLUMN message VARCHAR(500) NOT NULL DEFAULT ''",
            "ALTER TABLE crawl_jobs ADD COLUMN found_count INT NOT NULL DEFAULT 0",
            "ALTER TABLE crawl_jobs ADD COLUMN keyword VARCHAR(120) NOT NULL DEFAULT ''",
            "CREATE TABLE IF NOT EXISTS crawl_logs (id INT PRIMARY KEY AUTO_INCREMENT, job_id INT NOT NULL, message VARCHAR(500) NOT NULL DEFAULT '', created_at DATETIME NULL, INDEX ix_crawl_logs_job (job_id))",
        ):
            try:
                conn.execute(text(column))
            except Exception:
                pass
        try:
            conn.execute(text("UPDATE crawl_jobs SET status = 'stopped' WHERE status = 'running'"))
        except Exception:
            pass
        for statement in (
            "CREATE INDEX ix_news_pub ON news_items (published_at, category, id)",
            "CREATE INDEX ix_links_cat ON links (category_id, status, sort, id)",
            "CREATE INDEX ix_links_fav ON links (status, favorite_count)",
            "CREATE INDEX ix_links_rec ON links (status, recommend_count)",
            "CREATE INDEX ix_links_clk ON links (status, click_count)",
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
