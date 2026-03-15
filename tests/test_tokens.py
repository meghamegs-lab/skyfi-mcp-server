"""Unit tests for confirmation tokens."""

from __future__ import annotations

import time

import pytest

from skyfi_mcp.auth.tokens import ConfirmationTokenManager


class TestConfirmationTokenManager:
    """Tests for token creation and validation."""

    def test_token_creation(self, mock_token_secret):
        """Test basic token creation."""
        manager = ConfirmationTokenManager(secret=mock_token_secret, ttl_seconds=300)
        token = manager.create_token("archive_order", {"archive_id": "arch-123"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_validation_success(self, mock_token_secret):
        """Test successful token validation."""
        manager = ConfirmationTokenManager(secret=mock_token_secret, ttl_seconds=300)
        context = {"archive_id": "arch-123", "aoi": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"}
        token = manager.create_token("archive_order", context)

        is_valid, message = manager.validate_token(token, "archive_order")
        assert is_valid is True
        assert message == "Valid"

    def test_token_validation_wrong_action(self, mock_token_secret):
        """Test token validation rejects wrong action type."""
        manager = ConfirmationTokenManager(secret=mock_token_secret, ttl_seconds=300)
        token = manager.create_token("archive_order", {"archive_id": "arch-123"})

        is_valid, message = manager.validate_token(token, "tasking_order")
        assert is_valid is False
        assert "expected 'tasking_order'" in message

    def test_token_validation_expired(self, mock_token_secret):
        """Test token validation rejects expired tokens."""
        manager = ConfirmationTokenManager(secret=mock_token_secret, ttl_seconds=1)
        token = manager.create_token("archive_order", {"archive_id": "arch-123"})

        # Sleep past TTL
        time.sleep(1.1)

        is_valid, message = manager.validate_token(token, "archive_order")
        assert is_valid is False
        assert "expired" in message.lower()

    def test_token_validation_tampered_signature(self, mock_token_secret):
        """Test token validation rejects tampered tokens."""
        manager = ConfirmationTokenManager(secret=mock_token_secret, ttl_seconds=300)
        token = manager.create_token("archive_order", {"archive_id": "arch-123"})

        # Tamper with token by changing last character
        tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

        is_valid, message = manager.validate_token(tampered, "archive_order")
        assert is_valid is False
        assert "signature" in message.lower() or "invalid" in message.lower()

    def test_token_validation_invalid_format(self, mock_token_secret):
        """Test token validation rejects malformed tokens."""
        manager = ConfirmationTokenManager(secret=mock_token_secret, ttl_seconds=300)

        is_valid, message = manager.validate_token("invalid-token-format", "archive_order")
        assert is_valid is False
        assert "format" in message.lower() or "invalid" in message.lower()

    def test_token_validation_empty_token(self, mock_token_secret):
        """Test token validation rejects empty tokens."""
        manager = ConfirmationTokenManager(secret=mock_token_secret, ttl_seconds=300)

        is_valid, message = manager.validate_token("", "archive_order")
        assert is_valid is False

    def test_token_context_binding(self, mock_token_secret):
        """Test that tokens are bound to their context."""
        manager = ConfirmationTokenManager(secret=mock_token_secret, ttl_seconds=300)

        context1 = {"archive_id": "arch-123"}
        context2 = {"archive_id": "arch-456"}

        token1 = manager.create_token("archive_order", context1)
        token2 = manager.create_token("archive_order", context2)

        # Both tokens should validate with their respective action
        is_valid1, _ = manager.validate_token(token1, "archive_order")
        is_valid2, _ = manager.validate_token(token2, "archive_order")

        assert is_valid1 is True
        assert is_valid2 is True

        # Tokens are different
        assert token1 != token2

    def test_token_multiple_validations(self, mock_token_secret):
        """Test that tokens can be validated multiple times."""
        manager = ConfirmationTokenManager(secret=mock_token_secret, ttl_seconds=300)
        token = manager.create_token("tasking_order", {"window": "april-2025"})

        # Validate multiple times
        for _ in range(5):
            is_valid, message = manager.validate_token(token, "tasking_order")
            assert is_valid is True
            assert message == "Valid"

    def test_token_with_complex_context(self, mock_token_secret):
        """Test token creation with complex nested context."""
        manager = ConfirmationTokenManager(secret=mock_token_secret, ttl_seconds=300)
        context = {
            "aoi": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "window_start": "2025-04-01T00:00:00Z",
            "window_end": "2025-04-30T23:59:59Z",
            "sar_params": {
                "polarisation": "VV",
                "grazing_angle_min": 20.0,
            },
            "delivery_config": {
                "driver": "S3",
                "bucket": "imagery-bucket",
            },
        }
        token = manager.create_token("tasking_order", context)
        is_valid, _ = manager.validate_token(token, "tasking_order")
        assert is_valid is True

    def test_token_different_secrets(self):
        """Test tokens created with different secrets don't validate."""
        context = {"order_id": "order-123"}

        manager1 = ConfirmationTokenManager(secret="secret-1", ttl_seconds=300)
        manager2 = ConfirmationTokenManager(secret="secret-2", ttl_seconds=300)

        token = manager1.create_token("archive_order", context)

        # Should fail validation with different secret
        is_valid, message = manager2.validate_token(token, "archive_order")
        assert is_valid is False
        assert "signature" in message.lower() or "invalid" in message.lower()

    def test_token_default_secret_from_env(self, monkeypatch):
        """Test token manager uses environment secret if none provided."""
        env_secret = "env-secret-value"
        monkeypatch.setenv("SKYFI_TOKEN_SECRET", env_secret)

        manager = ConfirmationTokenManager()
        token = manager.create_token("archive_order", {"id": "123"})
        is_valid, _ = manager.validate_token(token, "archive_order")
        assert is_valid is True

    def test_token_custom_ttl(self, mock_token_secret):
        """Test token manager with custom TTL."""
        manager = ConfirmationTokenManager(secret=mock_token_secret, ttl_seconds=2)
        token = manager.create_token("archive_order", {"id": "123"})

        # Should be valid immediately
        is_valid, _ = manager.validate_token(token, "archive_order")
        assert is_valid is True

        # Should be expired after TTL
        time.sleep(2.1)
        is_valid, message = manager.validate_token(token, "archive_order")
        assert is_valid is False
        assert "expired" in message.lower()
