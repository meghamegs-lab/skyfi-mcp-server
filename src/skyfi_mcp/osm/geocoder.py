"""OpenStreetMap Nominatim integration for geocoding and POI search.

Uses httpx for async requests to the OSM Nominatim API.
Converts results to WKT polygons suitable for SkyFi API AOI parameters.
"""

from __future__ import annotations

import httpx
from shapely.geometry import box, shape
from shapely import wkt as shapely_wkt

NOMINATIM_URL = "https://nominatim.openstreetmap.org"
USER_AGENT = "SkyFi-MCP-Server/0.1.0 (https://github.com/skyfi/skyfi-mcp-server)"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


async def geocode_to_wkt(
    location_name: str,
    buffer_km: float = 1.0,
) -> dict:
    """Convert a place name to a WKT polygon for use as a SkyFi AOI.

    Args:
        location_name: Human-readable place name (e.g., "Suez Canal", "LAX Airport").
        buffer_km: Buffer in km around the point to create a bounding box (default 1km).

    Returns:
        Dict with keys: wkt, lat, lon, display_name, bbox, osm_type
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{NOMINATIM_URL}/search",
            params={
                "q": location_name,
                "format": "json",
                "limit": 1,
                "polygon_geojson": 1,
                "addressdetails": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=15.0,
        )
        resp.raise_for_status()
        results = resp.json()

    if not results:
        return {"error": f"No results found for '{location_name}'"}

    result = results[0]
    lat = float(result["lat"])
    lon = float(result["lon"])
    display_name = result.get("display_name", location_name)

    # Use the returned geometry if available, otherwise create a bounding box
    geojson = result.get("geojson")
    if geojson and geojson.get("type") in ("Polygon", "MultiPolygon"):
        geom = shape(geojson)
        wkt_str = shapely_wkt.dumps(geom, rounding_precision=6)
    elif "boundingbox" in result:
        bb = result["boundingbox"]  # [south, north, west, east]
        south, north, west, east = float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])
        geom = box(west, south, east, north)
        wkt_str = shapely_wkt.dumps(geom, rounding_precision=6)
    else:
        # Create buffer around point (approximate degrees from km)
        deg_buffer = buffer_km / 111.0
        geom = box(lon - deg_buffer, lat - deg_buffer, lon + deg_buffer, lat + deg_buffer)
        wkt_str = shapely_wkt.dumps(geom, rounding_precision=6)

    return {
        "wkt": wkt_str,
        "lat": lat,
        "lon": lon,
        "display_name": display_name,
        "bbox": result.get("boundingbox"),
        "osm_type": result.get("osm_type"),
    }


async def reverse_geocode(lat: float, lon: float) -> dict:
    """Convert coordinates to a human-readable place name.

    Args:
        lat: Latitude.
        lon: Longitude.

    Returns:
        Dict with keys: display_name, address, osm_type
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{NOMINATIM_URL}/reverse",
            params={
                "lat": lat,
                "lon": lon,
                "format": "json",
                "addressdetails": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=15.0,
        )
        resp.raise_for_status()
        result = resp.json()

    if "error" in result:
        return {"error": result["error"]}

    return {
        "display_name": result.get("display_name", "Unknown"),
        "address": result.get("address", {}),
        "osm_type": result.get("osm_type"),
        "lat": float(result.get("lat", lat)),
        "lon": float(result.get("lon", lon)),
    }


async def search_nearby_features(
    lat: float,
    lon: float,
    feature_type: str = "aeroway",
    radius_km: float = 50.0,
    limit: int = 10,
) -> dict:
    """Search for points of interest near a location using Overpass API.

    Args:
        lat: Center latitude.
        lon: Center longitude.
        feature_type: OSM feature key (e.g., 'aeroway', 'port', 'building',
            'amenity', 'natural', 'waterway', 'military', 'power', 'industrial').
        radius_km: Search radius in kilometers (default 50km).
        limit: Maximum number of results.

    Returns:
        Dict with keys: features (list), count, query_center
    """
    radius_m = radius_km * 1000

    # Build Overpass QL query
    query = f"""
    [out:json][timeout:25];
    (
      node["{feature_type}"](around:{radius_m},{lat},{lon});
      way["{feature_type}"](around:{radius_m},{lat},{lon});
      relation["{feature_type}"](around:{radius_m},{lat},{lon});
    );
    out center body {limit};
    """

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            OVERPASS_URL,
            data={"data": query},
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

    features = []
    for element in data.get("elements", []):
        feature = {
            "osm_id": element.get("id"),
            "type": element.get("type"),
            "tags": element.get("tags", {}),
            "name": element.get("tags", {}).get("name", "Unnamed"),
        }

        # Get coordinates (center for ways/relations)
        if element.get("type") == "node":
            feature["lat"] = element.get("lat")
            feature["lon"] = element.get("lon")
        elif "center" in element:
            feature["lat"] = element["center"].get("lat")
            feature["lon"] = element["center"].get("lon")

        if feature.get("lat") is not None:
            features.append(feature)

    return {
        "features": features[:limit],
        "count": len(features),
        "query_center": {"lat": lat, "lon": lon},
        "radius_km": radius_km,
        "feature_type": feature_type,
    }
