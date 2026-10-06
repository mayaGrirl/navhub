from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware

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
    yield


app = FastAPI(title="Nav API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in settings.cors_origins.split(",") if item.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(public.router)
app.include_router(auth.router)
app.include_router(admin.setup_router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"ok": True}
