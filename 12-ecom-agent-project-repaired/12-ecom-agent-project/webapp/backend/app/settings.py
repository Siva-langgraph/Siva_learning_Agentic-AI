"""Backend settings — read once, from the environment and webapp/backend/.env.

    STEP 0  webapp/backend/.env is loaded HERE, at import   (a variable already set wins)
            so every way of starting the backend reads it:
            python run.py · uvicorn app.main:app · a PyCharm run configuration
    STEP 1  Settings — the values below
    STEP 2  supervisor: SUPERVISOR_ARN, else SUPERVISOR_URL, else agent/supervisor/deployment.json
    STEP 3  session_secret() — the cookie-signing key (see WHERE THE SIGNING KEY COMES FROM)

    SUPERVISOR_ARN      deployed supervisor (AgentCore, SigV4). Unset: read from
                        agent/supervisor/deployment.json, which supervisor/deploy.py writes
    SUPERVISOR_URL      a local supervisor A2A server (http://localhost:9000/) instead
    APP_STORE           dynamodb (default) | memory (tests)
    APP_TABLE           DynamoDB table name (created on first start if missing)
    ADMIN_USERS         who sees /admin: unset or "*" = EVERY user (the default); "a,b" = only those
    MODEL_PRICES        JSON, USD per 1M tokens per model — unset: costs show "—"
    PINECONE_API_KEY / PINECONE_SECRET_ID   the KB browser (admin)
    OPENAI_API_KEY / OPENAI_SECRET_ID       the KB browser's "search by meaning" (optional)
    SESSION_SECRET_ID   Secrets Manager id of the cookie-signing key (AWS)
    SESSION_SECRET      the key itself (optional locally)
    COOKIE_SECURE       true behind HTTPS (CloudFront); false for http://localhost
    APP_ENV_FILE        another .env to load, or "none" to load none (tests)

WHERE THE SIGNING KEY COMES FROM

    SESSION_SECRET_ID set     Secrets Manager       AWS: every backend task signs with the same key
    SESSION_SECRET set        that value            local: sign-ins survive a restart
    neither, on your machine  a random key          sign-ins last until the backend restarts;
                                                    users and conversations are in DynamoDB either way
    neither, on AWS (ECS)     the backend refuses to START, saying which variable is missing

    Before this, a missing key was found only at the first sign-in, as a 500:
    "SESSION_SECRET (local) or SESSION_SECRET_ID (AWS) must be set" — usually
    because the backend was started with uvicorn, which never read .env.

WHY AWS MAY NOT USE A RANDOM KEY
    Up to two backend tasks run behind the load balancer. Each would generate
    its own key, a cookie signed by one would fail on the other, and users
    would be signed out at random.

WHAT THIS DOES NOT DO
    It never prints a key or a secret. It does not create the Secrets Manager
    secret — the AWS deploy does.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

log = logging.getLogger("backend.settings")

BACKEND = Path(__file__).resolve().parent.parent                      # webapp/backend
# Locally this file is <project>/webapp/backend/app/settings.py: the project is 3 folders up.
# In the container it is /app/app/settings.py, with fewer parents — guarded, not indexed,
# because an IndexError here would stop the deployed backend from starting at all.
_PARENTS = Path(__file__).resolve().parents
SUPERVISOR_DEPLOYMENT = (_PARENTS[3] if len(_PARENTS) > 3 else _PARENTS[-1]) / "agent" / "supervisor" / "deployment.json"


def _load_env_file() -> str:
    """STEP 0 — KEY=VALUE lines into os.environ; quotes stripped; set variables win. Returns what was loaded."""
    choice = os.environ.get("APP_ENV_FILE", "")
    if choice.lower() == "none":
        return ""
    path = Path(choice) if choice else BACKEND / ".env"
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return str(path)


ENV_FILE = _load_env_file()
ON_AWS = bool(os.environ.get("ECS_CONTAINER_METADATA_URI_V4") or os.environ.get("ECS_CONTAINER_METADATA_URI"))


def _supervisor_arn() -> tuple[str, str]:
    """STEP 2 — (arn, where it came from). A local SUPERVISOR_URL wins over the deployment file."""
    if os.environ.get("SUPERVISOR_ARN"):
        return os.environ["SUPERVISOR_ARN"], "SUPERVISOR_ARN"
    if os.environ.get("SUPERVISOR_URL"):
        return "", ""
    try:
        arn = json.loads(SUPERVISOR_DEPLOYMENT.read_text(encoding="utf-8")).get("runtime_arn", "")
    except (OSError, ValueError):
        arn = ""
    return (arn, str(SUPERVISOR_DEPLOYMENT)) if arn else ("", "")


SUPERVISOR_ARN, SUPERVISOR_ARN_SOURCE = _supervisor_arn()


@dataclass(frozen=True)
class Settings:
    region: str = os.environ.get("AWS_REGION", "us-east-1")
    supervisor_arn: str = SUPERVISOR_ARN
    supervisor_url: str = os.environ.get("SUPERVISOR_URL", "")
    store: str = os.environ.get("APP_STORE", "dynamodb")
    table: str = os.environ.get("APP_TABLE", "ecom-webapp")
    cookie_name: str = "ecom_session"
    cookie_secure: bool = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
    session_days: int = int(os.environ.get("SESSION_DAYS", 7))
    history_messages: int = int(os.environ.get("HISTORY_MESSAGES", 10))
    keepalive_s: float = float(os.environ.get("KEEPALIVE_S", 5))
    turn_timeout_s: int = int(os.environ.get("TURN_TIMEOUT_S", 600))
    # USD per 1M tokens, per model: {"gpt-6-sol": {"input": 0.0, "output": 0.0}}. Unset -> cost shown as "—".
    model_prices: dict = field(default_factory=lambda: json.loads(os.environ.get("MODEL_PRICES") or "{}"))
    agent_model: str = os.environ.get("AGENT_MODEL", "gpt-6-sol")
    pinecone_index: str = os.environ.get("PINECONE_INDEX", "ecom-kb")
    embed_model: str = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
    admin_users: tuple = field(default_factory=lambda: tuple(
        u.strip().lower() for u in (os.environ.get("ADMIN_USERS") or "*").split(",") if u.strip()))


S = Settings()


@lru_cache(maxsize=None)
def api_key(env_var: str, secret_env: str) -> str | None:
    """A key from Secrets Manager ({"api_key": …}) or the environment; None when neither is set."""
    if os.environ.get(secret_env):
        import boto3
        raw = boto3.client("secretsmanager", region_name=S.region).get_secret_value(SecretId=os.environ[secret_env])
        return json.loads(raw["SecretString"])["api_key"]
    return os.environ.get(env_var) or None


@lru_cache(maxsize=1)
def session_secret() -> bytes:
    """STEP 3 — the cookie-signing key. See WHERE THE SIGNING KEY COMES FROM."""
    if os.environ.get("SESSION_SECRET_ID"):
        import boto3
        raw = boto3.client("secretsmanager", region_name=S.region).get_secret_value(
            SecretId=os.environ["SESSION_SECRET_ID"])["SecretString"]
        try:
            return json.loads(raw)["key"].encode()
        except (ValueError, KeyError):
            return raw.encode()
    if os.environ.get("SESSION_SECRET"):
        return os.environ["SESSION_SECRET"].encode()
    if ON_AWS:
        raise RuntimeError("SESSION_SECRET_ID is not set on the backend task: every task must sign cookies "
                           "with the same key from Secrets Manager — redeploy the web app stack")
    log.warning("SESSION_SECRET not set — using a random key: sign-ins last until the backend restarts "
                "(set SESSION_SECRET in webapp/backend/.env to keep them)")
    return secrets.token_bytes(32)
