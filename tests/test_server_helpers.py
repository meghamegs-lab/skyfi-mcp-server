"""Unit tests for server.py helper functions and tool structure.

Tests the refactored 12-tool server's internal helpers and verifies
tool registration, annotations, and the WKT detection logic.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from skyfi_mcp.server import _format_error, _format_search_results, _is_wkt, mcp
from skyfi_mcp.api.client import SkyFiAPIError
from skyfi_mcp.api.models import ApiProvider, ProductType


class TestIsWkt:
    """Tests for WKT detection helper."""

    def test_polygon_wkt(self):
        assert _is_wkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))") is True

    def test_polygon_lowercase(self):
        assert _is_wkt("polygon((0 0, 1 0, 1 1, 0 1, 0 0))") is True

    def test_multipolygon_wkt(self):
        assert _is_wkt("MULTIPOLYGON(((0 0, 1 0, 1 1, 0 1, 0 0)))") is True

    def test_point_wkt(self):
        assert _is_wkt("POINT(10.5 20.3)") is True

    def test_linestring_wkt(self):
        assert _is_wkt("LINESTRING(0 0, 1 1, 2 2)") is True

    def test_geometrycollection_wkt(self):
        assert _is_wkt("GEOMETRYCOLLECTION(POINT(1 1), LINESTRING(0 0, 1 1))") is True

    def test_place_name(self):
        assert _is_wkt("Tokyo") is False

    def test_place_name_multiword(self):
        assert _is_wkt("New York City") is False

    def test_place_with_polygon_substring(self):
        """Place name containing WKT keyword should not match (no parens)."""
        assert _is_wkt("The Polygon Building, London") is False

    def test_empty_string(self):
        assert _is_wkt("") is False

    def test_whitespace_padding(self):
        assert _is_wkt("  POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))  ") is True

    def test_mixed_case(self):
        assert _is_wkt("Polygon((0 0, 1 0, 1 1, 0 1, 0 0))") is True


class TestFormatError:
    """Tests for error formatting helper."""

    def test_skyfi_api_error(self):
        error = SkyFiAPIError(404, "Archive not found")
        result = _format_error(error)
        parsed = json.loads(result)
        assert "error" in parsed
        assert "404" in parsed["error"]
        assert "Archive not found" in parsed["error"]

    def test_generic_exception(self):
        error = ValueError("Something went wrong")
        result = _format_error(error)
        parsed = json.loads(result)
        assert "error" in parsed
        assert "Something went wrong" in parsed["error"]


class TestFormatSearchResults:
    """Tests for search result formatting helper."""

    @staticmethod
    def _make_archive(**overrides):
        """Create a mock archive object with realistic defaults."""
        defaults = {
            "archive_id": "arch-123",
            "provider": ApiProvider.SIWEI,
            "constellation": "SIWEI-1",
            "product_type": ProductType.DAY,
            "resolution": "1.5m",
            "capture_timestamp": "2025-03-14T10:30:00Z",
            "cloud_coverage_percent": 5.2,
            "gsd": 1.5,
            "price_per_sq_km": 50.0,
            "price_full_scene": 2500.0,
            "total_area_sq_km": 25.0,
            "overlap_ratio": 0.85,
            "overlap_sq_km": 21.0,
            "open_data": False,
            "thumbnail_urls": {"small": "https://example.com/thumb.jpg"},
            "delivery_time_hours": 24,
        }
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    @staticmethod
    def _make_response(archives, total=None, next_page=None):
        """Create a mock GetArchivesResponse-like object."""
        return SimpleNamespace(
            archives=archives,
            total=total if total is not None else len(archives),
            next_page=next_page,
        )

    def test_empty_archives(self):
        response = self._make_response([], total=0, next_page=None)
        result = _format_search_results(response)
        parsed = json.loads(result)
        assert parsed["total_results"] == 0
        assert parsed["archives"] == []
        assert parsed["next_page"] is None

    def test_single_archive(self):
        archives = [self._make_archive()]
        response = self._make_response(archives, total=1)
        result = _format_search_results(response)
        parsed = json.loads(result)
        assert parsed["total_results"] == 1
        assert len(parsed["archives"]) == 1
        assert parsed["archives"][0]["archive_id"] == "arch-123"
        assert parsed["archives"][0]["provider"] == "SIWEI"

    def test_with_next_page(self):
        archives = [self._make_archive(archive_id=f"arch-{i}") for i in range(10)]
        response = self._make_response(archives, total=50, next_page="cursor-abc")
        result = _format_search_results(response)
        parsed = json.loads(result)
        assert parsed["total_results"] == 50
        assert parsed["next_page"] == "cursor-abc"
        assert parsed["page_size"] == 10

    def test_with_location_info(self):
        archives = [self._make_archive()]
        response = self._make_response(archives, total=1)
        location_info = {"geocoded_name": "Tokyo, Japan", "lat": 35.68, "lon": 139.76}
        result = _format_search_results(response, location_info=location_info)
        parsed = json.loads(result)
        assert "location" in parsed
        assert parsed["location"]["geocoded_name"] == "Tokyo, Japan"

    def test_with_aoi_wkt(self):
        archives = [self._make_archive()]
        response = self._make_response(archives, total=1)
        aoi = "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        result = _format_search_results(response, aoi=aoi)
        parsed = json.loads(result)
        assert "aoi_wkt" in parsed
        assert parsed["aoi_wkt"] == aoi


import asyncio

_loop = asyncio.new_event_loop()


def _get_tools_dict():
    """Get registered tools dict from FastMCP using its public API.

    Uses mcp.list_tools() (async) to get all registered tool names,
    then mcp.get_tool(name) to retrieve each tool object.
    Returns a dict of {name: tool_object}.
    """
    tool_list = _loop.run_until_complete(mcp.list_tools())
    return {t.name: t for t in tool_list}


def _get_tool(name):
    """Get a single tool by name using FastMCP's public API."""
    return _loop.run_until_complete(mcp.get_tool(name))


class TestToolRegistration:
    """Tests that verify all 12 tools are registered with proper annotations."""

    def test_tool_count(self):
        """Verify exactly 12 tools are registered."""
        tools = _get_tools_dict()
        assert len(tools) == 12, f"Expected 12 tools, got {len(tools)}: {list(tools.keys())}"

    def test_expected_tool_names(self):
        """Verify all expected tool names are registered."""
        expected = {
            "search_satellite_imagery",
            "check_feasibility",
            "get_pricing_overview",
            "preview_order",
            "confirm_order",
            "check_order_status",
            "get_download_url",
            "setup_area_monitoring",
            "check_new_images",
            "geocode_location",
            "search_nearby_pois",
            "get_account_info",
        }
        tools = _get_tools_dict()
        actual = set(tools.keys())
        assert actual == expected, f"Missing: {expected - actual}, Extra: {actual - expected}"

    def test_confirm_order_is_destructive(self):
        """confirm_order should be marked as destructive."""
        tool = _get_tool("confirm_order")
        annotations = tool.annotations
        assert annotations is not None
        assert annotations.destructiveHint is True
        assert annotations.readOnlyHint is False

    def test_search_tools_are_readonly(self):
        """Search and read tools should be marked read-only."""
        readonly_tools = [
            "search_satellite_imagery",
            "check_feasibility",
            "get_pricing_overview",
            "preview_order",
            "check_order_status",
            "get_download_url",
            "check_new_images",
            "geocode_location",
            "search_nearby_pois",
            "get_account_info",
        ]
        for name in readonly_tools:
            tool = _get_tool(name)
            annotations = tool.annotations
            assert annotations is not None, f"{name} has no annotations"
            assert annotations.readOnlyHint is True, f"{name} should be readOnly"

    def test_setup_area_monitoring_not_readonly(self):
        """setup_area_monitoring should NOT be read-only (creates/deletes monitors)."""
        tool = _get_tool("setup_area_monitoring")
        annotations = tool.annotations
        assert annotations is not None
        assert annotations.readOnlyHint is False

    def test_check_new_images_not_open_world(self):
        """check_new_images reads from local SQLite, not external API."""
        tool = _get_tool("check_new_images")
        annotations = tool.annotations
        assert annotations is not None
        assert annotations.openWorldHint is False

    def test_all_tools_have_annotations(self):
        """Every tool should have annotations set."""
        tools = _get_tools_dict()
        for name, tool in tools.items():
            assert tool.annotations is not None, f"{name} missing annotations"

    def test_all_tools_have_descriptions(self):
        """Every tool should have a docstring description."""
        tools = _get_tools_dict()
        for name, tool in tools.items():
            assert tool.description, f"{name} missing description"
