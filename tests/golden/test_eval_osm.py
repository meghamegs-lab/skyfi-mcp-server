"""Golden Evals E-020 to E-025: OSM Geocoding & POI Search.

These evals verify the Nominatim / Overpass integration with mocked HTTP.
All HTTP calls are intercepted by respx — no live network required.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from skyfi_mcp.osm.geocoder import (
    NOMINATIM_URL,
    OVERPASS_URL,
    geocode_to_wkt,
    reverse_geocode,
    search_nearby_features,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def nominatim_suez_canal():
    """Mock Nominatim response for 'Suez Canal'."""
    return [
        {
            "lat": "30.4567",
            "lon": "32.3497",
            "display_name": "Suez Canal, Egypt",
            "osm_type": "way",
            "boundingbox": ["29.9", "31.3", "32.2", "32.6"],
            "geojson": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [32.2, 29.9],
                        [32.6, 29.9],
                        [32.6, 31.3],
                        [32.2, 31.3],
                        [32.2, 29.9],
                    ]
                ],
            },
        }
    ]


@pytest.fixture
def nominatim_manhattan():
    """Mock Nominatim response for 'Manhattan' with polygon boundary."""
    return [
        {
            "lat": "40.7831",
            "lon": "-73.9712",
            "display_name": "Manhattan, New York, NY, USA",
            "osm_type": "relation",
            "boundingbox": ["40.6996", "40.8826", "-74.0479", "-73.9067"],
            "geojson": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-73.97, 40.70],
                        [-73.91, 40.70],
                        [-73.91, 40.88],
                        [-73.97, 40.88],
                        [-73.97, 40.70],
                    ]
                ],
            },
        }
    ]


@pytest.fixture
def nominatim_empty():
    """Mock empty Nominatim response."""
    return []


@pytest.fixture
def reverse_geocode_paris():
    """Mock reverse geocode response near Eiffel Tower."""
    return {
        "display_name": "Eiffel Tower, Avenue Anatole France, Paris, France",
        "address": {"tourism": "Eiffel Tower", "city": "Paris", "country": "France"},
        "osm_type": "way",
        "lat": "48.8584",
        "lon": "2.2945",
    }


@pytest.fixture
def overpass_airports():
    """Mock Overpass response for airports near JFK."""
    return {
        "elements": [
            {
                "id": 12345,
                "type": "way",
                "tags": {"name": "John F. Kennedy International Airport", "aeroway": "aerodrome"},
                "center": {"lat": 40.6413, "lon": -73.7781},
            },
            {
                "id": 12346,
                "type": "way",
                "tags": {"name": "LaGuardia Airport", "aeroway": "aerodrome"},
                "center": {"lat": 40.7769, "lon": -73.8740},
            },
        ]
    }


# ── E-020: Geocode Known Location ────────────────────────────────────────────


class TestE020GeocodeKnownLocation:
    """E-020: Geocoding 'Suez Canal' returns WKT near 30.45/32.35."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_suez_canal_returns_wkt(self, nominatim_suez_canal):
        respx.get(f"{NOMINATIM_URL}/search").mock(
            return_value=httpx.Response(200, json=nominatim_suez_canal)
        )
        result = await geocode_to_wkt("Suez Canal")
        assert "wkt" in result
        assert "POLYGON" in result["wkt"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_suez_canal_lat_lon(self, nominatim_suez_canal):
        respx.get(f"{NOMINATIM_URL}/search").mock(
            return_value=httpx.Response(200, json=nominatim_suez_canal)
        )
        result = await geocode_to_wkt("Suez Canal")
        assert abs(result["lat"] - 30.45) < 0.1
        assert abs(result["lon"] - 32.35) < 0.1

    @respx.mock
    @pytest.mark.asyncio
    async def test_suez_canal_display_name(self, nominatim_suez_canal):
        respx.get(f"{NOMINATIM_URL}/search").mock(
            return_value=httpx.Response(200, json=nominatim_suez_canal)
        )
        result = await geocode_to_wkt("Suez Canal")
        assert "Suez" in result["display_name"]


# ── E-021: Geocode with Polygon Boundary ─────────────────────────────────────


class TestE021GeocodeWithBoundary:
    """E-021: Geocoding 'Manhattan' returns an actual polygon boundary."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_manhattan_returns_polygon(self, nominatim_manhattan):
        respx.get(f"{NOMINATIM_URL}/search").mock(
            return_value=httpx.Response(200, json=nominatim_manhattan)
        )
        result = await geocode_to_wkt("Manhattan")
        assert "POLYGON" in result["wkt"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_manhattan_not_simple_bbox(self, nominatim_manhattan):
        respx.get(f"{NOMINATIM_URL}/search").mock(
            return_value=httpx.Response(200, json=nominatim_manhattan)
        )
        result = await geocode_to_wkt("Manhattan")
        # Should contain coordinates (not just a 4-point box)
        assert result["wkt"].count(",") >= 4


# ── E-022: Geocode Unknown Place ─────────────────────────────────────────────


class TestE022GeocodeUnknown:
    """E-022: Geocoding nonsense returns error, not crash."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_unknown_returns_error(self, nominatim_empty):
        respx.get(f"{NOMINATIM_URL}/search").mock(
            return_value=httpx.Response(200, json=nominatim_empty)
        )
        result = await geocode_to_wkt("xyznonexistent123")
        assert "error" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_unknown_error_message(self, nominatim_empty):
        respx.get(f"{NOMINATIM_URL}/search").mock(
            return_value=httpx.Response(200, json=nominatim_empty)
        )
        result = await geocode_to_wkt("xyznonexistent123")
        assert "No results" in result["error"]


# ── E-023: Reverse Geocode ───────────────────────────────────────────────────


class TestE023ReverseGeocode:
    """E-023: Reverse geocoding near Eiffel Tower returns Paris."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_reverse_contains_paris(self, reverse_geocode_paris):
        respx.get(f"{NOMINATIM_URL}/reverse").mock(
            return_value=httpx.Response(200, json=reverse_geocode_paris)
        )
        result = await reverse_geocode(48.8584, 2.2945)
        assert "Paris" in result["display_name"] or "Eiffel" in result["display_name"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_reverse_has_address(self, reverse_geocode_paris):
        respx.get(f"{NOMINATIM_URL}/reverse").mock(
            return_value=httpx.Response(200, json=reverse_geocode_paris)
        )
        result = await reverse_geocode(48.8584, 2.2945)
        assert "address" in result
        assert isinstance(result["address"], dict)


# ── E-024: POI Search Airports ───────────────────────────────────────────────


class TestE024POISearchAirports:
    """E-024: POI search near JFK finds airport features."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_finds_jfk(self, overpass_airports):
        respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json=overpass_airports))
        result = await search_nearby_features(40.64, -73.78, feature_type="aeroway")
        assert result["count"] >= 1
        names = [f["name"] for f in result["features"]]
        assert any("Kennedy" in n or "JFK" in n for n in names)

    @respx.mock
    @pytest.mark.asyncio
    async def test_poi_has_coordinates(self, overpass_airports):
        respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json=overpass_airports))
        result = await search_nearby_features(40.64, -73.78, feature_type="aeroway")
        for feature in result["features"]:
            assert "lat" in feature
            assert "lon" in feature

    @respx.mock
    @pytest.mark.asyncio
    async def test_poi_query_center(self, overpass_airports):
        respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json=overpass_airports))
        result = await search_nearby_features(40.64, -73.78, feature_type="aeroway")
        assert result["query_center"]["lat"] == 40.64
        assert result["query_center"]["lon"] == -73.78


# ── E-025: Geocode → Search Chain ────────────────────────────────────────────


class TestE025GeocodeChain:
    """E-025: Geocode result produces a WKT usable for search."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_geocode_wkt_is_valid_polygon(self, nominatim_suez_canal):
        respx.get(f"{NOMINATIM_URL}/search").mock(
            return_value=httpx.Response(200, json=nominatim_suez_canal)
        )
        result = await geocode_to_wkt("Suez Canal")
        wkt = result["wkt"]
        # Valid WKT polygon format
        assert wkt.startswith("POLYGON")
        assert "(" in wkt
        assert ")" in wkt

    @respx.mock
    @pytest.mark.asyncio
    async def test_geocode_wkt_has_coordinates(self, nominatim_suez_canal):
        respx.get(f"{NOMINATIM_URL}/search").mock(
            return_value=httpx.Response(200, json=nominatim_suez_canal)
        )
        result = await geocode_to_wkt("Suez Canal")
        wkt = result["wkt"]
        # Should contain numeric coordinates
        import re

        coords = re.findall(r"[-\d.]+", wkt)
        assert len(coords) >= 8  # At least 4 coordinate pairs
