"""Storage backends for session idempotency and persistence."""

import json
import sqlite3
import time
from abc import ABC, abstractmethod
from typing import Optional


class BaseStorage(ABC):
    """Abstract storage interface."""

    @abstractmethod
    def get(self, key: str) -> Optional[dict]:
        """Get a stored record by key."""

    @abstractmethod
    def set(self, key: str, value: dict) -> None:
        """Store a record by key."""


class InMemoryStorage(BaseStorage):
    """In-memory storage for development/testing."""

    def __init__(self):
        self._store: dict[str, dict] = {}

    def get(self, key: str) -> Optional[dict]:
        return self._store.get(key)

    def set(self, key: str, value: dict) -> None:
        self._store[key] = value


class SQLiteStorage(BaseStorage):
    """SQLite-based storage for persistence across restarts."""

    def __init__(self, db_path: str = "sessions.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                ts REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def get(self, key: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT value, ts FROM sessions WHERE key = ?",
            (key,),
        ).fetchone()
        if not row:
            return None
        value, ts = row
        return {"response": json.loads(value), "ts": ts}

    def set(self, key: str, value: dict) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO sessions (key, value, ts) VALUES (?, ?, ?)",
            (key, json.dumps(value["response"]), value["ts"]),
        )
        self._conn.commit()
