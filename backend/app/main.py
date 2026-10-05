from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.routers import admin, auth, public
from app.seed import seed


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        gate = seed(db)
        print(f"Admin gate path: /{gate}")
    finally:
        db.close()
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
