"""BloodBridge FastAPI application."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import init_db
from .routers import (
    account, admin, assistant, auth, donors, referrals, requests, rewards, whatsapp,
)
from .services.compatibility import DISCOVERY_NOTICE

log = logging.getLogger("bloodbridge")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=("BloodBridge - AI-assisted blood donor discovery, matching, "
                 "community rewards and referrals. Matching supports preliminary "
                 "donor discovery only and is not medical clearance."),
    lifespan=lifespan,
)

def _cors_origins() -> list[str]:
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        settings.app_base_url,
    ]
    origins += [o.strip() for o in settings.extra_cors_origins.split(",") if o.strip()]
    # De-duplicate while keeping order.
    return list(dict.fromkeys(origins))


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    log.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": "BloodBridge",
        "assistant_mode": "ai_enhanced" if settings.gemini_api_key else "deterministic_demo",
        "whatsapp_mode": "cloud_api" if settings.whatsapp_access_token else "demo",
        "compatibility_notice": DISCOVERY_NOTICE,
    }


app.include_router(auth.router)
app.include_router(donors.router)
app.include_router(requests.router)
app.include_router(assistant.router)
app.include_router(whatsapp.router)
app.include_router(rewards.router)
app.include_router(referrals.router)
app.include_router(account.router)
app.include_router(admin.router)
