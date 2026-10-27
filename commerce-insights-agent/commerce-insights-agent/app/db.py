from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from .config import settings

class Database:
    """Minimal adapter for fixed analytics queries. Model text is never passed as SQL."""
    def __init__(self, url: str | None = None): self.url = url or settings.database_url
    @contextmanager
    def connection(self):
        if self.url.startswith("sqlite:"):
            raw = self.url.removeprefix("sqlite:///")
            path = raw if raw == ":memory:" else (raw if raw.startswith("/") else str(Path(raw)))
            conn = sqlite3.connect(path, timeout=settings.query_timeout_seconds)
            conn.row_factory = sqlite3.Row
            conn.execute(f"PRAGMA busy_timeout={settings.query_timeout_seconds * 1000}")
            try: yield conn
            finally: conn.close()
        elif self.url.startswith(("postgresql://", "postgres://")):
            try: import psycopg
            except ImportError as exc: raise RuntimeError("Install psycopg[binary] for PostgreSQL support") from exc
            with psycopg.connect(self.url, connect_timeout=settings.query_timeout_seconds, options=f"-c statement_timeout={settings.query_timeout_seconds * 1000}") as conn: yield conn
        else: raise ValueError("DATABASE_URL must use sqlite:/// or postgresql://")
    def rows(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connection() as conn:
            cur = conn.execute(sql, params)
            names = [d[0] for d in cur.description or []]
            rows = cur.fetchall()
            out=[]
            for row in rows:
                item = dict(row) if isinstance(row, sqlite3.Row) else dict(zip(names, row))
                out.append({k: float(v) if hasattr(v, "as_tuple") else (v.isoformat() if hasattr(v, "isoformat") else v) for k,v in item.items()})
            return out
_db: Database | None = None
def get_db() -> Database:
    global _db
    if _db is None: _db = Database()
    return _db
def set_db_for_tests(db: Database | None) -> None:
    global _db
    _db = db
