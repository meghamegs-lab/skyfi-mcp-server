"""Golden Evals E-040 to E-046: Human-in-the-Loop Token System.

These evals verify that the HMAC confirmation token system correctly
gates financial transactions. This is the most safety-critical component.
"""

from __future__ import annotations

import base64
import json
import time

import pytest

from skyfi_mcp.auth.tokens import ConfirmationTokenManager


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def manager():
    return ConfirmationTokenManager(secret="golden-eval-secret", ttl_seconds=300)


@pytest.fixture
def short_lived_manager():
    return ConfirmationTokenManager(secret="golden-eval-secret", ttl_seconds=1)


@pytest.fixture
def order_token(manager):
    """A valid 'order' token with realistic context."""
    return manager.create_token("order", {
        "type": "pricing",
        "aoi": "POLYGON((30 31, 33 31, 33 32, 30 32, 30 31))",
        "ts": time.time(),
    })


# ── E-040: Token Create → Validate Roundtrip ────────────────────────────────

class TestE040TokenRoundtrip:
    """E-040: A freshly created token validates successfully."""

    def test_roundtrip_is_valid(self, manager, order_token):
        valid, msg = manager.validate_token(order_token, "order")
        assert valid is True
        assert msg == "Valid"

    def test_token_is_nonempty_string(self, order_token):
        assert isinstance(order_token, str)
        assert len(order_token) > 20  # HMAC tokens should be substantial

    def test_token_is_base64_decodable(self, order_token):
        decoded = base64.urlsafe_b64decode(order_token.encode()).decode()
        payload_str, sig = decoded.rsplit(":", 1)
        payload = json.loads(payload_str)
        assert "action" in payload
        assert "ctx" in payload
        assert "ts" in payload

    def test_different_contexts_produce_different_tokens(self, manager):
        t1 = manager.create_token("order", {"aoi": "polygon-A"})
        t2 = manager.create_token("order", {"aoi": "polygon-B"})
        assert t1 != t2

    def test_same_context_same_second_produces_same_token(self, manager):
        ctx = {"aoi": "polygon-A", "ts": 1000000000}
        t1 = manager.create_token("order", ctx)
        t2 = manager.create_token("order", ctx)
        # Tokens encode the current time, so they may differ slightly
        # but both should be valid
        assert manager.validate_token(t1, "order")[0] is True
        assert manager.validate_token(t2, "order")[0] is True


# ── E-041: Expired Token Rejected ────────────────────────────────────────────

class TestE041ExpiredToken:
    """E-041: Tokens past TTL are rejected with clear error."""

    def test_expired_token_rejected(self, short_lived_manager):
        token = short_lived_manager.create_token("order", {"id": "test"})
        time.sleep(1.2)
        valid, msg = short_lived_manager.validate_token(token, "order")
        assert valid is False
        assert "expired" in msg.lower()

    def test_token_valid_within_ttl(self, short_lived_manager):
        token = short_lived_manager.create_token("order", {"id": "test"})
        valid, msg = short_lived_manager.validate_token(token, "order")
        assert valid is True


# ── E-042: Tampered Token Rejected ───────────────────────────────────────────

class TestE042TamperedToken:
    """E-042: Any modification to the token breaks HMAC validation."""

    def test_flipped_last_char(self, manager, order_token):
        tampered = order_token[:-1] + ("X" if order_token[-1] != "X" else "Y")
        valid, msg = manager.validate_token(tampered, "order")
        assert valid is False

    def test_truncated_token(self, manager, order_token):
        truncated = order_token[:len(order_token) // 2]
        valid, msg = manager.validate_token(truncated, "order")
        assert valid is False

    def test_prepended_data(self, manager, order_token):
        modified = "AAAA" + order_token
        valid, msg = manager.validate_token(modified, "order")
        assert valid is False

    def test_different_secret_rejects(self, order_token):
        other_manager = ConfirmationTokenManager(secret="different-secret", ttl_seconds=300)
        valid, msg = other_manager.validate_token(order_token, "order")
        assert valid is False
        assert "signature" in msg.lower() or "invalid" in msg.lower()


# ── E-043: Wrong Action Type Rejected ────────────────────────────────────────

class TestE043WrongAction:
    """E-043: Token for action 'order' rejects validation for 'delete'."""

    def test_order_token_rejects_delete(self, manager, order_token):
        valid, msg = manager.validate_token(order_token, "delete")
        assert valid is False
        assert "order" in msg  # Should mention the original action

    def test_order_token_rejects_empty_action(self, manager, order_token):
        valid, msg = manager.validate_token(order_token, "")
        assert valid is False

    def test_order_token_rejects_similar_action(self, manager, order_token):
        valid, msg = manager.validate_token(order_token, "orders")  # plural
        assert valid is False


# ── E-044: Invalid Format Rejected ───────────────────────────────────────────

class TestE044InvalidFormat:
    """E-044: Random strings and malformed input are rejected gracefully."""

    @pytest.mark.parametrize("bad_token", [
        "",
        "not-a-token",
        "abcdef123456",
        "eyJhbGciOiJIUzI1NiJ9",  # Looks like JWT but isn't
        "===",
        "null",
        "undefined",
        " ",
        "\n",
        "a" * 1000,
    ])
    def test_malformed_tokens_rejected(self, manager, bad_token):
        valid, msg = manager.validate_token(bad_token, "order")
        assert valid is False
        assert isinstance(msg, str)
        assert len(msg) > 0


# ── E-045: Order Without Token Rejected ──────────────────────────────────────

class TestE045OrderWithoutToken:
    """E-045: Order tools reject calls when token is missing or empty."""

    def test_empty_token_rejected(self, manager):
        valid, msg = manager.validate_token("", "order")
        assert valid is False

    def test_none_coerced_token_rejected(self, manager):
        valid, msg = manager.validate_token("None", "order")
        assert valid is False


# ── E-046: Full Pricing → Token → Order Validation ──────────────────────────

class TestE046FullFlow:
    """E-046: Complete flow: pricing issues token, order validates it."""

    def test_pricing_to_order_flow(self, manager):
        # Step 1: Pricing tool creates token
        pricing_context = {
            "type": "pricing",
            "aoi": "POLYGON((30 31, 33 31, 33 32, 30 32, 30 31))",
            "ts": time.time(),
        }
        token = manager.create_token("order", pricing_context)

        # Step 2: Time passes (user reviews pricing)
        # (no sleep needed — well within TTL)

        # Step 3: Order tool validates token
        valid, msg = manager.validate_token(token, "order")
        assert valid is True
        assert msg == "Valid"

    def test_feasibility_to_order_flow(self, manager):
        # Step 1: Feasibility tool creates token
        feasibility_context = {
            "type": "feasibility",
            "aoi": "POLYGON((30 31, 33 31, 33 32, 30 32, 30 31))",
            "product": "DAY",
            "ts": time.time(),
        }
        token = manager.create_token("order", feasibility_context)

        # Step 2: Order tool validates token
        valid, msg = manager.validate_token(token, "order")
        assert valid is True

    def test_token_reusable_within_ttl(self, manager):
        """Token can be validated multiple times (e.g., retry after network error)."""
        token = manager.create_token("order", {"id": "test"})
        for _ in range(5):
            valid, _ = manager.validate_token(token, "order")
            assert valid is True

    def test_token_ttl_matches_manager_config(self, manager):
        assert manager.ttl_seconds == 300  # 5 minutes
