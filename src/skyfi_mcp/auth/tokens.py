"""HMAC-signed confirmation tokens for human-in-the-loop order safety.

Flow:
1. pricing/feasibility tools return a confirmation_token
2. order tools require a valid, non-expired confirmation_token
3. tokens are HMAC-signed so the server doesn't need to store state
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time


class ConfirmationTokenManager:
    """Create and validate HMAC-signed confirmation tokens.

    Tokens encode: {action, context_hash, timestamp} signed with a secret.
    This is stateless — any server instance can validate tokens.
    """

    def __init__(self, secret: str | None = None, ttl_seconds: int = 300):
        default_secret = os.environ.get("SKYFI_TOKEN_SECRET", "skyfi-mcp-default-secret")
        self.secret = (secret or default_secret).encode()
        self.ttl_seconds = ttl_seconds

    def create_token(self, action: str, context: dict) -> str:
        """Create a signed token for an action.

        Args:
            action: Type of action this authorizes (e.g., "archive_order", "tasking_order")
            context: Relevant context (e.g., archive_id, pricing info) to bind the token to.

        Returns:
            Base64-encoded signed token string.
        """
        context_hash = hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()[:16]

        payload = json.dumps(
            {
                "action": action,
                "ctx": context_hash,
                "ts": int(time.time()),
            }
        )

        sig = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()[:32]
        # Simple encoding: payload:signature
        import base64

        token = base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()
        return token

    def validate_token(self, token: str, action: str) -> tuple[bool, str]:
        """Validate a confirmation token.

        Args:
            token: The token string to validate.
            action: Expected action type.

        Returns:
            Tuple of (is_valid, error_message).
        """
        try:
            import base64

            decoded = base64.urlsafe_b64decode(token.encode()).decode()
            payload_str, sig = decoded.rsplit(":", 1)
        except Exception:
            return False, "Invalid token format"

        # Verify signature
        expected_sig = hmac.new(self.secret, payload_str.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected_sig):
            return False, "Invalid token signature"

        # Parse payload
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError:
            return False, "Corrupted token payload"

        # Check action type
        if payload.get("action") != action:
            return False, f"Token is for '{payload.get('action')}', expected '{action}'"

        # Check expiration
        token_time = payload.get("ts", 0)
        if time.time() - token_time > self.ttl_seconds:
            return False, f"Token expired (valid for {self.ttl_seconds}s)"

        return True, "Valid"
