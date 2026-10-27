"""The backend: FastAPI under /api/v1 (and /api/health for the load balancer).

    local:  cd webapp/backend  then  python run.py      (or: uvicorn app.main:app --port 8000)
            both read webapp/backend/.env — settings.py loads it, whoever starts the app
    AWS:    the same app in the ECS container, behind CloudFront /api/* -> internal ALB

    start ─► STEP 1 settings checked and logged   .env used · supervisor and where its ARN came from ·
             │                                    signing key ready (AWS without SESSION_SECRET_ID: stop here)
             ├► STEP 2 store opened                creates the DynamoDB table on a first start (20-60 s)
             └► serving

WHAT THIS DOES NOT DO
    It never logs a key, a secret or a password — only where each setting came from.
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .routers import admin, auth, chat, conversations, feedback
from .settings import ENV_FILE, S, SUPERVISOR_ARN_SOURCE, session_secret
from .store import get_store

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger("backend")


def _check_settings() -> None:
    """STEP 1 — what this backend will use, said once at start; problems found now, not at the first click."""
    log.info("settings: %s", f"loaded {ENV_FILE}" if ENV_FILE else "no .env file (environment only)")
    if S.supervisor_arn:
        log.info("supervisor: %s (from %s)", S.supervisor_arn, SUPERVISOR_ARN_SOURCE)
    elif S.supervisor_url:
        log.info("supervisor: %s (local A2A server)", S.supervisor_url)
    else:
        log.warning("supervisor: NOT configured — questions will fail. Deploy agent/supervisor "
                    "(it writes agent/supervisor/deployment.json), or set SUPERVISOR_ARN in webapp/backend/.env")
    session_secret()                                   # AWS without SESSION_SECRET_ID raises here
    log.info("session key: %s", "Secrets Manager" if os.environ.get("SESSION_SECRET_ID")
             else "SESSION_SECRET" if os.environ.get("SESSION_SECRET") else "random (until restart)")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _check_settings()
    # STEP 2 — open the store BEFORE serving: on a first start it creates the DynamoDB table and
    # waits until it is active. Done here, the server is ready when it says so — not done here,
    # the first sign-in silently waits for the table instead.
    log.info("opening the store…")
    get_store()
    log.info("store ready — serving")
    yield


app = FastAPI(title="ecom NLQ web backend", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)
for r in (auth.router, conversations.router, chat.router, feedback.router, admin.router):
    app.include_router(r, prefix="/api/v1")


@app.get("/api/health")
def health():
    return {"status": "ok"}
