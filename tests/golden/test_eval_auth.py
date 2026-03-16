"""Golden Evals E-070 to E-076: Authentication.

These evals verify dual auth (local + cloud), resolution order, and error handling.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from skyfi_mcp.auth.config import AuthConfig, extract_cloud_auth, load_local_config


# ── E-070: Local Auth from Env Var ────────────────────────────────────────────


class TestE070LocalAuthFromEnv:
    """E-070: SKYFI_API_KEY env var produces a valid AuthConfig."""

    def test_env_var_returns_auth_config(self, monkeypatch):
        monkeypatch.setenv("SKYFI_API_KEY", "sk-test-env-key")
        config = load_local_config()
        assert config is not None
        assert isinstance(config, AuthConfig)
        assert config.api_key == "sk-test-env-key"

    def test_env_var_default_base_url(self, monkeypatch):
        monkeypatch.setenv("SKYFI_API_KEY", "sk-test")
        monkeypatch.delenv("SKYFI_BASE_URL", raising=False)
        config = load_local_config()
        assert config.base_url == "https://app.skyfi.com/platform-api"

    def test_env_var_custom_base_url(self, monkeypatch):
        monkeypatch.setenv("SKYFI_API_KEY", "sk-test")
        monkeypatch.setenv("SKYFI_BASE_URL", "https://custom.api.com")
        config = load_local_config()
        assert config.base_url == "https://custom.api.com"

    def test_headers_contain_api_key(self, monkeypatch):
        monkeypatch.setenv("SKYFI_API_KEY", "sk-test-header")
        config = load_local_config()
        assert config.headers == {"X-Skyfi-Api-Key": "sk-test-header"}


# ── E-071: Local Auth from Config File ────────────────────────────────────────


class TestE071LocalAuthFromFile:
    """E-071: ~/.skyfi/config.json with api_key produces AuthConfig."""

    def test_config_file_snake_case(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SKYFI_API_KEY", raising=False)
        config_dir = tmp_path / ".skyfi"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({"api_key": "sk-from-file"}))
        with patch.object(Path, "home", return_value=tmp_path):
            config = load_local_config()
        assert config is not None
        assert config.api_key == "sk-from-file"

    def test_config_file_camel_case(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SKYFI_API_KEY", raising=False)
        config_dir = tmp_path / ".skyfi"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({"apiKey": "sk-camel-key"}))
        with patch.object(Path, "home", return_value=tmp_path):
            config = load_local_config()
        assert config is not None
        assert config.api_key == "sk-camel-key"

    def test_config_file_with_base_url(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SKYFI_API_KEY", raising=False)
        monkeypatch.delenv("SKYFI_BASE_URL", raising=False)
        config_dir = tmp_path / ".skyfi"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "api_key": "sk-file",
                    "base_url": "https://staging.skyfi.com/api",
                }
            )
        )
        with patch.object(Path, "home", return_value=tmp_path):
            config = load_local_config()
        assert config.base_url == "https://staging.skyfi.com/api"

    def test_invalid_json_returns_none(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SKYFI_API_KEY", raising=False)
        config_dir = tmp_path / ".skyfi"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text("not valid json {{{")
        with patch.object(Path, "home", return_value=tmp_path):
            config = load_local_config()
        assert config is None


# ── E-072: Env Var Overrides Config File ──────────────────────────────────────


class TestE072EnvOverridesFile:
    """E-072: When both env var and config file exist, env var wins."""

    def test_env_overrides_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SKYFI_API_KEY", "sk-from-env")
        config_dir = tmp_path / ".skyfi"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({"api_key": "sk-from-file"}))
        with patch.object(Path, "home", return_value=tmp_path):
            config = load_local_config()
        assert config.api_key == "sk-from-env"


# ── E-073: Cloud Auth with Bearer Header ─────────────────────────────────────


class TestE073CloudAuthBearer:
    """E-073: Authorization: Bearer header extracts correctly."""

    def test_bearer_header(self):
        headers = {"Authorization": "Bearer sk-cloud-bearer"}
        config = extract_cloud_auth(headers)
        assert config is not None
        assert config.api_key == "sk-cloud-bearer"

    def test_bearer_lowercase(self):
        headers = {"authorization": "Bearer sk-lower"}
        config = extract_cloud_auth(headers)
        assert config is not None
        assert config.api_key == "sk-lower"

    def test_bearer_with_whitespace(self):
        headers = {"Authorization": "Bearer   sk-with-spaces  "}
        config = extract_cloud_auth(headers)
        assert config is not None
        assert config.api_key == "sk-with-spaces"

    def test_non_bearer_scheme_ignored(self):
        headers = {"Authorization": "Basic c2stdGVzdA=="}
        config = extract_cloud_auth(headers)
        assert config is None


# ── E-074: Cloud Auth with X-Skyfi-Api-Key Header ────────────────────────────


class TestE074CloudAuthApiKeyHeader:
    """E-074: X-Skyfi-Api-Key header extracts correctly."""

    def test_api_key_header(self):
        headers = {"X-Skyfi-Api-Key": "sk-direct-header"}
        config = extract_cloud_auth(headers)
        assert config is not None
        assert config.api_key == "sk-direct-header"

    def test_api_key_header_lowercase(self):
        headers = {"x-skyfi-api-key": "sk-lower-header"}
        config = extract_cloud_auth(headers)
        assert config is not None
        assert config.api_key == "sk-lower-header"

    def test_bearer_takes_precedence_over_api_key(self):
        """If both headers present, Bearer is checked first."""
        headers = {
            "Authorization": "Bearer sk-bearer-wins",
            "X-Skyfi-Api-Key": "sk-api-key-loses",
        }
        config = extract_cloud_auth(headers)
        assert config.api_key == "sk-bearer-wins"


# ── E-075: No Auth Available ─────────────────────────────────────────────────


class TestE075NoAuthAvailable:
    """E-075: When no credentials exist, load_local_config returns None."""

    def test_no_env_no_file(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SKYFI_API_KEY", raising=False)
        with patch.object(Path, "home", return_value=tmp_path):
            config = load_local_config()
        assert config is None

    def test_empty_headers(self):
        config = extract_cloud_auth({})
        assert config is None

    def test_empty_bearer(self):
        config = extract_cloud_auth({"Authorization": "Bearer "})
        assert config is None

    def test_empty_api_key_header(self):
        config = extract_cloud_auth({"X-Skyfi-Api-Key": ""})
        assert config is None


# ── E-076: AuthConfig Properties ─────────────────────────────────────────────


class TestE076AuthConfigProperties:
    """E-076: AuthConfig dataclass has correct properties."""

    def test_default_base_url(self):
        config = AuthConfig(api_key="sk-test")
        assert config.base_url == "https://app.skyfi.com/platform-api"

    def test_headers_property(self):
        config = AuthConfig(api_key="sk-my-key")
        assert config.headers == {"X-Skyfi-Api-Key": "sk-my-key"}

    def test_custom_base_url(self):
        config = AuthConfig(api_key="sk-test", base_url="https://custom.api")
        assert config.base_url == "https://custom.api"
