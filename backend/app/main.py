from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware

from app.security import rate_limit, rds

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.routers import admin, auth, public
from app.github_ranks import schedule_daily
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
        conn.execute(text("UPDATE users SET email = LOWER(TRIM(email))"))
    db = SessionLocal()
    try:
        gate = seed(db)
        print(f"Admin gate path: /{gate}")
    finally:
        db.close()
    schedule_daily()
    schedule_news()
    schedule_directory()
    from app.review import sweep_open

    sweep_open()
    yield


app = FastAPI(title="Nav API", lifespan=lifespan)
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
    return await call_next(request)


app.include_router(public.router)
app.include_router(auth.router)
app.include_router(admin.setup_router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"ok": True}
