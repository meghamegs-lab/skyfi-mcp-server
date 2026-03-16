"""Golden Evals E-090 to E-095: End-to-End MCP Tool Flows.

These evals verify complete multi-step workflows combining
tokens, models, and the webhook store — the critical paths
an AI agent follows.
"""

from __future__ import annotations

import time

import pytest

from skyfi_mcp.api.models import (
    ArchiveOrderRequest,
    DeliveryDriver,
    FeasibilityRequest,
    GetArchivesRequest,
    PassPredictionRequest,
    PricingRequest,
    ProductType,
    TaskingOrderRequest,
)
from skyfi_mcp.auth.tokens import ConfirmationTokenManager
from skyfi_mcp.webhooks.store import WebhookEventStore


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def token_manager():
    return ConfirmationTokenManager(secret="e2e-test-secret", ttl_seconds=300)


@pytest.fixture
def webhook_store(temp_db_path):
    return WebhookEventStore(db_path=temp_db_path, ttl_days=30)


# ── E-090: Full Archive Order Flow ───────────────────────────────────────────


class TestE090FullArchiveOrderFlow:
    """E-090: geocode → search → details → pricing → confirm → order.

    Simulates the complete archive ordering path an agent follows.
    """

    def test_search_model_to_pricing_to_token(self, token_manager):
        """Validates the model + token chain for archive ordering."""
        # Step 1: Build a search request (agent geocoded → got WKT)
        aoi = "POLYGON((30 31, 33 31, 33 32, 30 32, 30 31))"
        search_req = GetArchivesRequest(aoi=aoi, from_date="2024-01-01")
        assert search_req.aoi == aoi

        # Step 2: Build a pricing request
        pricing_req = PricingRequest(aoi=aoi)
        assert pricing_req is not None

        # Step 3: Create a confirmation token (simulates pricing tool response)
        token = token_manager.create_token(
            "order",
            {
                "type": "pricing",
                "aoi": aoi,
                "archive_id": "arch-suez-001",
            },
        )
        assert token is not None

        # Step 4: Validate token (simulates order tool receiving it)
        valid, msg = token_manager.validate_token(token, "order")
        assert valid is True

        # Step 5: Build order request
        order_req = ArchiveOrderRequest(aoi=aoi, archive_id="arch-suez-001")
        assert order_req.archive_id == "arch-suez-001"

    def test_expired_token_blocks_order(self, token_manager):
        """An expired token must be rejected before order placement."""
        mgr = ConfirmationTokenManager(secret="e2e-test-secret", ttl_seconds=0)
        token = mgr.create_token("order", {"aoi": "POLYGON((0 0,1 0,1 1,0 1,0 0))"})
        time.sleep(0.1)
        valid, msg = mgr.validate_token(token, "order")
        assert valid is False
        assert "expired" in msg.lower() or "Expired" in msg


# ── E-091: Full Tasking Order Flow ───────────────────────────────────────────


class TestE091FullTaskingOrderFlow:
    """E-091: geocode → feasibility → pricing → confirm → order.

    Simulates the complete tasking ordering path.
    """

    def test_feasibility_to_pricing_to_tasking(self, token_manager):
        aoi = "POLYGON((10 20, 11 20, 11 21, 10 21, 10 20))"

        # Step 1: Build feasibility request
        feas_req = FeasibilityRequest(
            aoi=aoi,
            product_type=ProductType.DAY,
            resolution="1.0m",
            start_date="2024-07-01T00:00:00Z",
            end_date="2024-07-15T23:59:59Z",
        )
        assert feas_req.product_type == ProductType.DAY

        # Step 2: Get confirmation token from feasibility
        token = token_manager.create_token(
            "order",
            {
                "type": "feasibility",
                "aoi": aoi,
                "product_type": "DAY",
            },
        )

        # Step 3: Validate and place tasking order
        valid, msg = token_manager.validate_token(token, "order")
        assert valid is True

        order_req = TaskingOrderRequest(
            aoi=aoi,
            product_type=ProductType.DAY,
            resolution="1.0m",
            window_start="2024-07-01T00:00:00Z",
            window_end="2024-07-15T23:59:59Z",
            delivery_driver=DeliveryDriver.GS,
        )
        assert order_req.product_type == ProductType.DAY


# ── E-092: Monitoring Setup Flow ─────────────────────────────────────────────


class TestE092MonitoringSetupFlow:
    """E-092: create notification → webhook fires → check_new_images.

    Simulates setting up monitoring and receiving imagery notifications.
    """

    def test_webhook_receive_and_check(self, webhook_store):
        # Step 1: Simulate webhook firing (SkyFi sends POST /webhook)
        event_id = webhook_store.store_event(
            "notif-monitor-001",
            {
                "notification_id": "notif-monitor-001",
                "archive_id": "arch-new-img-001",
                "provider": "PLANET",
                "capture_date": "2025-03-15T10:00:00Z",
            },
        )
        assert event_id > 0

        # Step 2: Agent calls check_new_images (polls unread)
        unread = webhook_store.get_unread_events()
        assert len(unread) == 1
        assert unread[0].payload["archive_id"] == "arch-new-img-001"

        # Step 3: Agent marks as read
        webhook_store.mark_read([unread[0].id])
        assert len(webhook_store.get_unread_events()) == 0

    def test_multiple_webhooks_for_same_notification(self, webhook_store):
        webhook_store.store_event("notif-aoi-X", {"image": "img-1"})
        webhook_store.store_event("notif-aoi-X", {"image": "img-2"})
        webhook_store.store_event("notif-aoi-Y", {"image": "img-3"})

        x_events = webhook_store.get_unread_events(notification_id="notif-aoi-X")
        assert len(x_events) == 2

        y_events = webhook_store.get_unread_events(notification_id="notif-aoi-Y")
        assert len(y_events) == 1


# ── E-093: Research Agent Flow ───────────────────────────────────────────────


class TestE093ResearchAgentFlow:
    """E-093: Place name → geocode → search → feasibility → pass prediction → brief.

    Validates that all model types compose correctly for a research workflow.
    """

    def test_research_models_compose(self):
        # Simulating: geocoded "LAX" → got WKT
        aoi = "POLYGON((-118.42 33.93, -118.38 33.93, -118.38 33.95, -118.42 33.95, -118.42 33.93))"

        # Build search request
        search = GetArchivesRequest(
            aoi=aoi, from_date="2024-01-01", product_types=[ProductType.DAY]
        )
        assert search.aoi == aoi

        # Build feasibility request
        feas = FeasibilityRequest(
            aoi=aoi,
            product_type=ProductType.DAY,
            resolution="0.5m",
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-01-31T23:59:59Z",
        )
        assert feas.aoi == aoi

        # Build pass prediction request
        passes = PassPredictionRequest(
            aoi=aoi,
            from_date="2024-01-01T00:00:00Z",
            to_date="2024-01-31T23:59:59Z",
        )
        assert passes.aoi == aoi

        # Build pricing request
        pricing = PricingRequest(aoi=aoi)
        assert pricing is not None


# ── E-094: Multi-Step Token Safety ───────────────────────────────────────────


class TestE094MultiStepTokenSafety:
    """E-094: Verify token safety across various attack scenarios."""

    def test_token_from_different_manager_rejected(self):
        """Tokens from different secrets are rejected."""
        mgr1 = ConfirmationTokenManager(secret="secret-A")
        mgr2 = ConfirmationTokenManager(secret="secret-B")
        token = mgr1.create_token("order", {"test": True})
        valid, msg = mgr2.validate_token(token, "order")
        assert valid is False

    def test_token_action_mismatch_rejected(self, token_manager):
        """Token for 'order' cannot be used for 'delete'."""
        token = token_manager.create_token("order", {"test": True})
        valid, msg = token_manager.validate_token(token, "delete")
        assert valid is False

    def test_token_not_replayable_with_different_action(self, token_manager):
        """Same token cannot be replayed for a different action type."""
        token = token_manager.create_token("order", {"ctx": "archive"})
        valid_order, _ = token_manager.validate_token(token, "order")
        valid_tasking, _ = token_manager.validate_token(token, "tasking")
        assert valid_order is True
        assert valid_tasking is False


# ── E-095: Order Rejection Flow ──────────────────────────────────────────────


class TestE095OrderRejectionFlow:
    """E-095: Try order without pricing step → token rejection."""

    def test_empty_token_rejected(self, token_manager):
        valid, msg = token_manager.validate_token("", "order")
        assert valid is False

    def test_garbage_token_rejected(self, token_manager):
        valid, msg = token_manager.validate_token("not-a-real-token", "order")
        assert valid is False

    def test_none_token_rejected(self, token_manager):
        valid, msg = token_manager.validate_token("None", "order")
        assert valid is False

    def test_valid_flow_works_after_rejection(self, token_manager):
        """After a rejection, the correct flow still works."""
        # First: fail with bad token
        valid, _ = token_manager.validate_token("bad", "order")
        assert valid is False

        # Then: proper flow
        token = token_manager.create_token("order", {"recovery": True})
        valid, _ = token_manager.validate_token(token, "order")
        assert valid is True
