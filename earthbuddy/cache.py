"""The SQLite response cache: one table, one connection, one lock. Holds NASA POWER responses only."""
import json
import os
import sqlite3
import threading
import time
import zlib
from pathlib import Path

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _path() -> str:
    if os.environ.get("EB_OFFLINE") == "1":
        return ":memory:"            # synthetic payloads must never be cached under real NASA URLs
    if os.environ.get("EB_DB"):
        return os.environ["EB_DB"]
    if os.environ.get("VERCEL"):
        return "/tmp/eb/cache.sqlite"
    return str(Path(__file__).resolve().parent.parent / "data" / "cache.sqlite")


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        path = _path()
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(path, check_same_thread=False)
        _conn.execute("CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, payload BLOB, source TEXT, fetched_at REAL)")
    return _conn


def get(key: str, ttl_days: float) -> dict | None:
    with _lock:
        row = _db().execute("SELECT payload, fetched_at FROM cache WHERE key = ?", (key,)).fetchone()
    if row is None or time.time() - row[1] > ttl_days * 86400:
        return None
    return json.loads(zlib.decompress(row[0]))


def put(key: str, payload: dict, source: str) -> None:
    blob = zlib.compress(json.dumps(payload).encode())
    with _lock:
        _db().execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?, ?)", (key, blob, source, time.time()))
        _db().commit()


def stats() -> dict:
    with _lock:
        n, size = _db().execute("SELECT COUNT(*), COALESCE(SUM(LENGTH(payload)), 0) FROM cache").fetchone()
    return {"entries": n, "bytes": size}


def reset() -> None:
    """Tests: drop the connection so the next call reopens at the current EB_DB / EB_OFFLINE."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
