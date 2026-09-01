from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db_init import initialize_database
from .routers import auth, foods, recommendations, users

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_create_schema:
        await initialize_database()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "UMD dining hall nutrition menus, food logging, favorites, goals, and "
        "explainable macro recommendations."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "testfoodo-api", "version": "1.0.0"}


app.include_router(auth.router, prefix="/api/v1")
app.include_router(foods.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
