"""Shared test fixtures and configuration."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_db_path() -> str:
    """Provide a temporary database path for tests.

    Automatically cleans up after the test.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    if Path(db_path).exists():
        os.unlink(db_path)


@pytest.fixture
def temp_data_dir(monkeypatch) -> Path:
    """Provide a temporary data directory and set environment variable.

    Automatically cleans up after the test.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)
        monkeypatch.setenv("SKYFI_MCP_DATA_DIR", str(temp_path))
        yield temp_path


@pytest.fixture
def mock_token_secret(monkeypatch) -> str:
    """Provide and set a mock token secret for tests."""
    secret = "test-secret-key-12345"
    monkeypatch.setenv("SKYFI_TOKEN_SECRET", secret)
    return secret
