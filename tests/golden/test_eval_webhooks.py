"""Golden Evals E-060 to E-068: AOI Monitoring & Webhook Event Store.

These evals verify the full webhook lifecycle: receive → store → poll → read/unread.
"""

from __future__ import annotations

import time

import pytest

from skyfi_mcp.webhooks.store import WebhookEvent, WebhookEventStore


@pytest.fixture
def store(temp_db_path):
    return WebhookEventStore(db_path=temp_db_path, ttl_days=30)


@pytest.fixture
def store_with_events(store):
    """Store pre-populated with 3 events across 2 notification IDs."""
    store.store_event("notif-AAA", {
        "archive_id": "arch-001",
        "provider": "PLANET",
        "capture_date": "2025-03-10T08:00:00Z",
    })
    store.store_event("notif-BBB", {
        "archive_id": "arch-002",
        "provider": "UMBRA",
        "capture_date": "2025-03-11T12:00:00Z",
    })
    store.store_event("notif-AAA", {
        "archive_id": "arch-003",
        "provider": "SATELLOGIC",
        "capture_date": "2025-03-12T16:00:00Z",
    })
    return store


# ── E-064: Webhook POST Stores Event ─────────────────────────────────────────

class TestE064WebhookStore:
    """E-064: Incoming webhook payload is stored and retrievable."""

    def test_store_returns_positive_id(self, store):
        event_id = store.store_event("notif-123", {"test": True})
        assert isinstance(event_id, int)
        assert event_id > 0

    def test_stored_event_has_correct_notification_id(self, store):
        store.store_event("notif-XYZ", {"data": "payload"})
        events = store.get_unread_events()
        assert len(events) == 1
        assert events[0].notification_id == "notif-XYZ"

    def test_stored_event_preserves_complex_payload(self, store):
        payload = {
            "notification_id": "notif-789",
            "archive_data": {
                "id": "arch-456",
                "provider": "PLANET",
                "footprint": "POLYGON((10 20, 11 20, 11 21, 10 21, 10 20))",
                "metadata": {"cloud_coverage": 3.5, "gsd_cm": 50},
            },
            "match_score": 0.97,
        }
        store.store_event("notif-789", payload)
        events = store.get_unread_events()
        assert events[0].payload == payload
        assert events[0].payload["archive_data"]["provider"] == "PLANET"

    def test_stored_event_has_timestamp(self, store):
        before = time.time()
        store.store_event("notif-123", {"ts": "now"})
        after = time.time()
        events = store.get_unread_events()
        assert before <= events[0].received_at <= after

    def test_sequential_stores_get_incrementing_ids(self, store):
        id1 = store.store_event("n", {"seq": 1})
        id2 = store.store_event("n", {"seq": 2})
        id3 = store.store_event("n", {"seq": 3})
        assert id1 < id2 < id3


# ── E-065: check_new_images Returns Unread and Marks Read ────────────────────

class TestE065CheckNewImages:
    """E-065: Unread events are returned and can be marked as read."""

    def test_unread_events_returned(self, store_with_events):
        events = store_with_events.get_unread_events()
        assert len(events) == 3

    def test_mark_read_removes_from_unread(self, store_with_events):
        events = store_with_events.get_unread_events()
        ids = [e.id for e in events]
        store_with_events.mark_read(ids)
        remaining = store_with_events.get_unread_events()
        assert len(remaining) == 0

    def test_partial_mark_read(self, store_with_events):
        events = store_with_events.get_unread_events()
        # Mark only the first one
        store_with_events.mark_read([events[0].id])
        remaining = store_with_events.get_unread_events()
        assert len(remaining) == 2

    def test_event_is_webhook_event_dataclass(self, store_with_events):
        events = store_with_events.get_unread_events()
        for e in events:
            assert isinstance(e, WebhookEvent)
            assert isinstance(e.id, int)
            assert isinstance(e.notification_id, str)
            assert isinstance(e.payload, dict)
            assert isinstance(e.received_at, float)
            assert e.read is False


# ── E-066: Filtered by Notification ID ───────────────────────────────────────

class TestE066FilteredByNotification:
    """E-066: Events can be filtered by notification_id."""

    def test_filter_returns_only_matching(self, store_with_events):
        aaa = store_with_events.get_unread_events(notification_id="notif-AAA")
        bbb = store_with_events.get_unread_events(notification_id="notif-BBB")
        assert len(aaa) == 2
        assert len(bbb) == 1
        assert all(e.notification_id == "notif-AAA" for e in aaa)
        assert all(e.notification_id == "notif-BBB" for e in bbb)

    def test_filter_nonexistent_returns_empty(self, store_with_events):
        events = store_with_events.get_unread_events(notification_id="notif-NONE")
        assert len(events) == 0

    def test_recent_events_also_filterable(self, store_with_events):
        recent = store_with_events.get_recent_events(
            notification_id="notif-BBB", hours=1
        )
        assert len(recent) == 1
        assert recent[0].notification_id == "notif-BBB"


# ── E-067: Re-check After Read Returns Empty ─────────────────────────────────

class TestE067ReCheckAfterRead:
    """E-067: After marking all events read, unread returns empty."""

    def test_recheck_returns_zero(self, store_with_events):
        # First call — get all unread
        events = store_with_events.get_unread_events()
        assert len(events) == 3

        # Mark all as read
        store_with_events.mark_read([e.id for e in events])

        # Second call — should be empty
        events_again = store_with_events.get_unread_events()
        assert len(events_again) == 0

    def test_new_event_after_read_shows_up(self, store_with_events):
        # Mark all existing as read
        events = store_with_events.get_unread_events()
        store_with_events.mark_read([e.id for e in events])

        # Add new event
        store_with_events.store_event("notif-AAA", {"archive_id": "arch-NEW"})

        # Should see only the new one
        new_events = store_with_events.get_unread_events()
        assert len(new_events) == 1
        assert new_events[0].payload["archive_id"] == "arch-NEW"

    def test_read_events_still_in_recent(self, store_with_events):
        """Read events should still appear in get_recent_events."""
        events = store_with_events.get_unread_events()
        store_with_events.mark_read([e.id for e in events])

        # Recent should still return them (it doesn't filter by read status)
        recent = store_with_events.get_recent_events(hours=1)
        assert len(recent) == 3


# ── E-068: TTL Cleanup ───────────────────────────────────────────────────────

class TestE068TTLCleanup:
    """E-068: Events older than TTL are cleaned up automatically."""

    def test_old_events_cleaned_on_store(self, temp_db_path):
        store = WebhookEventStore(db_path=temp_db_path, ttl_days=0)
        store.ttl_seconds = 1  # 1 second TTL

        store.store_event("notif-OLD", {"data": "old"})
        assert len(store.get_unread_events()) == 1

        time.sleep(1.2)

        # Storing triggers cleanup
        store.store_event("notif-NEW", {"data": "new"})
        events = store.get_unread_events()
        assert len(events) == 1
        assert events[0].payload["data"] == "new"

    def test_ttl_default_is_30_days(self, temp_db_path):
        store = WebhookEventStore(db_path=temp_db_path)
        assert store.ttl_seconds == 30 * 86400
