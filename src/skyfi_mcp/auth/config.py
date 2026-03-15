"""Authentication configuration for local and cloud deployment modes.

Local mode: reads API key from ~/.skyfi/config.json or SKYFI_API_KEY env var.
Cloud mode: extracts API key from request Authorization header.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AuthConfig:
    """Resolved authentication configuration."""

    api_key: str
    base_url: str = "https://app.skyfi.com/platform-api"

    @property
    def headers(self) -> dict[str, str]:
        return {"X-Skyfi-Api-Key": self.api_key}


def load_local_config() -> AuthConfig | None:
    """Load credentials from local config file or environment.

    Resolution order:
    1. SKYFI_API_KEY environment variable
    2. ~/.skyfi/config.json file
    3. Returns None if no credentials found
    """
    # Check environment variable first
    api_key = os.environ.get("SKYFI_API_KEY")
    base_url = os.environ.get("SKYFI_BASE_URL", "https://app.skyfi.com/platform-api")

    if api_key:
        return AuthConfig(api_key=api_key, base_url=base_url)

    # Check config file
    config_path = Path.home() / ".skyfi" / "config.json"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text())
            key = data.get("api_key") or data.get("apiKey")
            url = data.get("base_url") or data.get("baseUrl") or base_url
            if key:
                return AuthConfig(api_key=key, base_url=url)
        except (json.JSONDecodeError, OSError):
            pass

    return None


def extract_cloud_auth(headers: dict[str, str]) -> AuthConfig | None:
    """Extract API key from request headers for cloud multi-user mode.

    Supports:
    - Authorization: Bearer <api-key>
    - X-Skyfi-Api-Key: <api-key>
    """
    # Check Authorization header
    auth_header = headers.get("authorization") or headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        api_key = auth_header[7:].strip()
        if api_key:
            return AuthConfig(api_key=api_key)

    # Check direct API key header
    api_key = headers.get("x-skyfi-api-key") or headers.get("X-Skyfi-Api-Key", "")
    if api_key:
        return AuthConfig(api_key=api_key)

    return None
