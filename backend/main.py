"""Local Chess Arena - FastAPI application (http://127.0.0.1:8000)."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import ai, games, puzzles, saved_games, statistics
from .database import init_db

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="Local Chess Arena", version="1.0.0", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "Local Chess Arena"}


for r in (games.router, saved_games.router, puzzles.router, statistics.router, ai.router):
    app.include_router(r, prefix="/api")


@app.middleware("http")
async def no_cache(request, call_next):
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-store"
    return resp


app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
