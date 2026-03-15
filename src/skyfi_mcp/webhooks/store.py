"""SQLite-based webhook event storage.

Stores incoming webhook events from SkyFi notifications for later retrieval
by the check_new_images MCP tool.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass


@dataclass
class WebhookEvent:
    """A stored webhook event."""

    id: int
    notification_id: str
    payload: dict
    received_at: float
    read: bool = False


class WebhookEventStore:
    """SQLite store for webhook events with TTL-based cleanup."""

    def __init__(self, db_path: str | None = None, ttl_days: int = 30):
        data_dir = os.environ.get("SKYFI_MCP_DATA_DIR", ".")
        self.db_path = db_path or os.path.join(data_dir, "webhook_events.db")
        self.ttl_seconds = ttl_days * 86400
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS webhook_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notification_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    received_at REAL NOT NULL,
                    read INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_notification_id
                ON webhook_events(notification_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_received_at
                ON webhook_events(received_at)
            """)

    def store_event(self, notification_id: str, payload: dict) -> int:
        """Store a webhook event. Returns the event ID."""
        self._cleanup()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO webhook_events (notification_id, payload, received_at) VALUES (?, ?, ?)",
                (notification_id, json.dumps(payload), time.time()),
            )
            return cursor.lastrowid or 0

    def get_unread_events(
        self, notification_id: str | None = None, limit: int = 50
    ) -> list[WebhookEvent]:
        """Get unread events, optionally filtered by notification_id."""
        with sqlite3.connect(self.db_path) as conn:
            if notification_id:
                rows = conn.execute(
                    "SELECT id, notification_id, payload, received_at, read "
                    "FROM webhook_events WHERE read = 0 AND notification_id = ? "
                    "ORDER BY received_at DESC LIMIT ?",
                    (notification_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, notification_id, payload, received_at, read "
                    "FROM webhook_events WHERE read = 0 "
                    "ORDER BY received_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()

        return [
            WebhookEvent(
                id=row[0],
                notification_id=row[1],
                payload=json.loads(row[2]),
                received_at=row[3],
                read=bool(row[4]),
            )
            for row in rows
        ]

    def mark_read(self, event_ids: list[int]):
        """Mark events as read."""
        if not event_ids:
            return
        placeholders = ",".join("?" for _ in event_ids)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE webhook_events SET read = 1 WHERE id IN ({placeholders})",
                event_ids,
            )

    def get_recent_events(
        self, notification_id: str | None = None, hours: int = 24, limit: int = 50
    ) -> list[WebhookEvent]:
        """Get events from the last N hours."""
        since = time.time() - (hours * 3600)
        with sqlite3.connect(self.db_path) as conn:
            if notification_id:
                rows = conn.execute(
                    "SELECT id, notification_id, payload, received_at, read "
                    "FROM webhook_events WHERE received_at > ? AND notification_id = ? "
                    "ORDER BY received_at DESC LIMIT ?",
                    (since, notification_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, notification_id, payload, received_at, read "
                    "FROM webhook_events WHERE received_at > ? "
                    "ORDER BY received_at DESC LIMIT ?",
                    (since, limit),
                ).fetchall()

        return [
            WebhookEvent(
                id=row[0],
                notification_id=row[1],
                payload=json.loads(row[2]),
                received_at=row[3],
                read=bool(row[4]),
            )
            for row in rows
        ]

    def _cleanup(self):
        """Remove events older than TTL."""
        cutoff = time.time() - self.ttl_seconds
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM webhook_events WHERE received_at < ?", (cutoff,))
