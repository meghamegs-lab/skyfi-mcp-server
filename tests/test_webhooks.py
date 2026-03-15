"""Unit tests for webhook event store."""

from __future__ import annotations

import time

from skyfi_mcp.webhooks.store import WebhookEvent, WebhookEventStore


class TestWebhookEventStore:
    """Tests for webhook event storage and retrieval."""

    def test_store_event(self, temp_db_path):
        """Test storing a webhook event."""
        store = WebhookEventStore(db_path=temp_db_path, ttl_days=30)

        payload = {
            "notification_id": "notif-123",
            "archive_id": "arch-456",
            "match_score": 0.95,
        }
        event_id = store.store_event("notif-123", payload)

        assert event_id > 0
        assert isinstance(event_id, int)

    def test_get_unread_events(self, temp_db_path):
        """Test retrieving unread events."""
        store = WebhookEventStore(db_path=temp_db_path, ttl_days=30)

        payload1 = {"archive_id": "arch-123", "scene": "scene-1"}
        payload2 = {"archive_id": "arch-456", "scene": "scene-2"}

        event_id1 = store.store_event("notif-123", payload1)
        event_id2 = store.store_event("notif-123", payload2)

        events = store.get_unread_events()
        assert len(events) == 2
        assert events[0].id == event_id2  # Most recent first
        assert events[1].id == event_id1

    def test_get_unread_events_filtered_by_notification_id(self, temp_db_path):
        """Test filtering unread events by notification_id."""
        store = WebhookEventStore(db_path=temp_db_path, ttl_days=30)

        payload1 = {"archive_id": "arch-123"}
        payload2 = {"archive_id": "arch-456"}
        payload3 = {"archive_id": "arch-789"}

        store.store_event("notif-123", payload1)
        store.store_event("notif-456", payload2)
        store.store_event("notif-123", payload3)

        events_notif123 = store.get_unread_events(notification_id="notif-123")
        events_notif456 = store.get_unread_events(notification_id="notif-456")

        assert len(events_notif123) == 2
        assert len(events_notif456) == 1
        assert all(e.notification_id == "notif-123" for e in events_notif123)
        assert all(e.notification_id == "notif-456" for e in events_notif456)

    def test_mark_read(self, temp_db_path):
        """Test marking events as read."""
        store = WebhookEventStore(db_path=temp_db_path, ttl_days=30)

        payload1 = {"scene": "scene-1"}
        payload2 = {"scene": "scene-2"}
        payload3 = {"scene": "scene-3"}

        event_id1 = store.store_event("notif-123", payload1)
        event_id2 = store.store_event("notif-123", payload2)
        event_id3 = store.store_event("notif-123", payload3)

        # Mark some events as read
        store.mark_read([event_id1, event_id3])

        # Verify unread events
        unread_events = store.get_unread_events()
        assert len(unread_events) == 1
        assert unread_events[0].id == event_id2
        assert unread_events[0].read is False

    def test_mark_read_empty_list(self, temp_db_path):
        """Test marking empty list of events as read (should not error)."""
        store = WebhookEventStore(db_path=temp_db_path, ttl_days=30)

        payload = {"scene": "scene-1"}
        store.store_event("notif-123", payload)

        # Should not raise exception
        store.mark_read([])

        events = store.get_unread_events()
        assert len(events) == 1

    def test_get_recent_events(self, temp_db_path):
        """Test retrieving events from the last N hours."""
        store = WebhookEventStore(db_path=temp_db_path, ttl_days=30)

        payload = {"scene": "recent"}
        store.store_event("notif-123", payload)

        recent_events = store.get_recent_events(hours=1)
        assert len(recent_events) == 1
        assert recent_events[0].payload["scene"] == "recent"

    def test_get_recent_events_filtered_by_notification_id(self, temp_db_path):
        """Test filtering recent events by notification_id."""
        store = WebhookEventStore(db_path=temp_db_path, ttl_days=30)

        store.store_event("notif-123", {"scene": "a"})
        store.store_event("notif-456", {"scene": "b"})
        store.store_event("notif-123", {"scene": "c"})

        recent_123 = store.get_recent_events(notification_id="notif-123", hours=1)
        recent_456 = store.get_recent_events(notification_id="notif-456", hours=1)

        assert len(recent_123) == 2
        assert len(recent_456) == 1
        assert all(e.notification_id == "notif-123" for e in recent_123)

    def test_ttl_cleanup(self, temp_db_path):
        """Test that old events are cleaned up."""
        # Use very short TTL for testing (1 second)
        store = WebhookEventStore(db_path=temp_db_path, ttl_days=0)
        store.ttl_seconds = 1  # Override to 1 second

        payload = {"scene": "old"}
        store.store_event("notif-123", payload)

        # Verify event is stored
        events = store.get_unread_events()
        assert len(events) == 1

        # Wait for TTL to expire
        time.sleep(1.1)

        # Store another event (triggers cleanup)
        store.store_event("notif-123", {"scene": "new"})

        # Old event should be gone
        events = store.get_unread_events()
        assert len(events) == 1
        assert events[0].payload["scene"] == "new"

    def test_event_payload_preservation(self, temp_db_path):
        """Test that event payloads are stored and retrieved correctly."""
        store = WebhookEventStore(db_path=temp_db_path, ttl_days=30)

        complex_payload = {
            "notification_id": "notif-789",
            "archive_data": {
                "id": "arch-123",
                "provider": "SIWEI",
                "footprint": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            },
            "match_score": 0.92,
            "captured_at": "2025-03-14T10:30:00Z",
            "metadata": {
                "cloud_coverage": 5.2,
                "off_nadir": 15.0,
            },
        }

        store.store_event("notif-789", complex_payload)
        events = store.get_unread_events()

        assert len(events) == 1
        assert events[0].payload == complex_payload
        assert events[0].payload["archive_data"]["provider"] == "SIWEI"

    def test_event_timestamp_tracking(self, temp_db_path):
        """Test that event timestamps are correctly recorded."""
        store = WebhookEventStore(db_path=temp_db_path, ttl_days=30)

        before_time = time.time()
        store.store_event("notif-123", {"scene": "1"})
        after_time = time.time()

        events = store.get_unread_events()
        assert len(events) == 1
        assert before_time <= events[0].received_at <= after_time

    def test_limit_parameter(self, temp_db_path):
        """Test that limit parameter works correctly."""
        store = WebhookEventStore(db_path=temp_db_path, ttl_days=30)

        # Store 10 events
        for i in range(10):
            store.store_event("notif-123", {"scene": f"scene-{i}"})

        # Retrieve with limit
        events = store.get_unread_events(limit=5)
        assert len(events) == 5

        # Default limit should be 50
        events_all = store.get_unread_events()
        assert len(events_all) == 10

    def test_multiple_stores_same_db(self, temp_db_path):
        """Test that multiple store instances can access the same database."""
        store1 = WebhookEventStore(db_path=temp_db_path, ttl_days=30)
        store2 = WebhookEventStore(db_path=temp_db_path, ttl_days=30)

        payload = {"scene": "shared"}
        store1.store_event("notif-123", payload)

        # Should be readable from store2
        events = store2.get_unread_events()
        assert len(events) == 1
        assert events[0].payload["scene"] == "shared"

    def test_webhook_event_dataclass(self, temp_db_path):
        """Test WebhookEvent dataclass."""
        store = WebhookEventStore(db_path=temp_db_path, ttl_days=30)

        payload = {"test": "data"}
        store.store_event("notif-456", payload)

        events = store.get_unread_events()
        event = events[0]

        assert isinstance(event, WebhookEvent)
        assert isinstance(event.id, int)
        assert event.notification_id == "notif-456"
        assert event.payload == payload
        assert isinstance(event.received_at, float)
        assert event.read is False

    def test_consecutive_mark_read_calls(self, temp_db_path):
        """Test that consecutive mark_read calls work correctly."""
        store = WebhookEventStore(db_path=temp_db_path, ttl_days=30)

        event_id1 = store.store_event("notif-123", {"scene": "1"})
        event_id2 = store.store_event("notif-123", {"scene": "2"})
        event_id3 = store.store_event("notif-123", {"scene": "3"})

        # Mark in batches
        store.mark_read([event_id1])
        store.mark_read([event_id2, event_id3])

        unread = store.get_unread_events()
        assert len(unread) == 0
