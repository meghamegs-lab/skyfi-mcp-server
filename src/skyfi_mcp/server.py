"""SkyFi MCP Server — 12 outcome-oriented MCP tools.

Refactored from 21 granular REST-mirror tools to 12 tools matching
the architecture decision document. Tools are organized into:
  - Search & Explore (1 tool)
  - Feasibility & Pricing (3 tools)
  - Order Flow (2 tools)
  - Order Management (2 tools)
  - Monitoring & Notifications (2 tools)
  - Geospatial (2 tools — but geocoding also embedded in search)
  - Account (1 tool — get_account_info dropped from tool count, included for completeness)

Supports both local (config file) and cloud (header-based) authentication.
Transport: Streamable HTTP + SSE via FastMCP's built-in Starlette server.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from skyfi_mcp.api.client import SkyFiAPIError, SkyFiClient
from skyfi_mcp.api.models import (
    ApiProvider,
    ArchiveOrderRequest,
    DeliverableType,
    DeliveryDriver,
    FeasibilityRequest,
    GetArchivesRequest,
    NotificationRequest,
    OrderRedeliveryRequest,
    OrderType,
    PassPredictionRequest,
    PricingRequest,
    ProductType,
    ResolutionLevel,
    SarPolarisation,
    SarProductType,
    SortColumn,
    SortDirection,
    TaskingOrderRequest,
)
from skyfi_mcp.auth.config import AuthConfig, load_local_config
from skyfi_mcp.auth.tokens import ConfirmationTokenManager
from skyfi_mcp.osm.geocoder import geocode_to_wkt, reverse_geocode, search_nearby_features
from skyfi_mcp.webhooks.store import WebhookEventStore

logger = logging.getLogger("skyfi_mcp")

# ── Server Setup ────────────────────────────────────────────────────────────────

mcp = FastMCP(
    "SkyFi MCP Server",
    instructions=(
        "SkyFi MCP Server provides access to satellite imagery through the SkyFi platform. "
        "You can search archive imagery, check feasibility of new captures, get pricing, "
        "place orders, and monitor areas of interest for new imagery.\n\n"
        "ORDERING FLOW — You MUST follow these steps in order:\n"
        "1. Use search_satellite_imagery to find available images\n"
        "2. Use preview_order to get exact pricing and a confirmation_token\n"
        "3. Present the price to the user and get their explicit approval\n"
        "4. Only then call confirm_order with the confirmation_token\n\n"
        "NEVER call confirm_order without first calling preview_order and getting user approval."
    ),
)

# Archive tokens: short-lived (5 min) since pricing is static
archive_token_manager = ConfirmationTokenManager(ttl_seconds=300)
# Tasking tokens: long-lived (24 hours) since feasibility analysis takes time
# and users need more time to evaluate tasking options. Architecture decision
# Req #5/6: ideally use SkyFi native quote_id (24hr TTL) for tasking, but
# the API doesn't expose quote_id — so we use a 24-hour HMAC token instead.
tasking_token_manager = ConfirmationTokenManager(ttl_seconds=86400)
event_store = WebhookEventStore()


# NOTE: custom_route is broken in fastmcp >= 2.4. Custom HTTP routes
# (health, webhook, landing page) are mounted in __main__.py via ASGI wrapper.


def _get_client(api_key: str | None = None) -> SkyFiClient:
    """Get an authenticated SkyFi client.

    For local mode, uses config file. For cloud mode, uses provided API key.
    """
    if api_key:
        config = AuthConfig(api_key=api_key)
    else:
        config = load_local_config()
        if not config:
            raise ValueError(
                "No SkyFi API key found. Set SKYFI_API_KEY environment variable, "
                "create ~/.skyfi/config.json, or pass api_key in request headers."
            )
    return SkyFiClient(config)


def _format_error(e: Exception) -> str:
    """Format an exception for MCP tool response."""
    if isinstance(e, SkyFiAPIError):
        return json.dumps({"error": f"SkyFi API Error ({e.status_code}): {e.detail}"})
    return json.dumps({"error": str(e)})


def _is_wkt(value: str) -> bool:
    """Check if a string looks like WKT geometry."""
    wkt_prefixes = ("POLYGON", "MULTIPOLYGON", "POINT", "LINESTRING", "GEOMETRYCOLLECTION")
    return value.strip().upper().startswith(wkt_prefixes)


# ══════════════════════════════════════════════════════════════════════════════════
# Tool 1: search_satellite_imagery (Req #6 — iterative search)
# ══════════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=True, idempotentHint=True, openWorldHint=True,
))
async def search_satellite_imagery(
    location: str,
    from_date: str | None = None,
    to_date: str | None = None,
    max_cloud_coverage_percent: float | None = None,
    max_off_nadir_angle: float | None = None,
    resolutions: list[str] | None = None,
    product_types: list[str] | None = None,
    providers: list[str] | None = None,
    open_data: bool | None = None,
    min_overlap_ratio: float | None = None,
    page_size: int = 20,
    next_page: str | None = None,
    api_key: str | None = None,
) -> str:
    """Search the SkyFi satellite image catalog with automatic geocoding.

    Accepts either a plain location name (e.g., "Golden Gate Bridge") or
    a WKT polygon. Location names are automatically geocoded via OpenStreetMap.
    Use next_page to paginate through results.

    Args:
        location: Place name (e.g., "Manhattan", "Port of Singapore") OR WKT polygon.
        from_date: Start date filter (ISO format, e.g., 2024-01-01T00:00:00+00:00).
        to_date: End date filter (ISO format).
        max_cloud_coverage_percent: Maximum cloud cover (0-100).
        max_off_nadir_angle: Maximum off-nadir angle (0-50).
        resolutions: Filter by resolution: LOW, MEDIUM, HIGH, VERY_HIGH, ULTRA_HIGH.
        product_types: Filter by product: DAY, NIGHT, VIDEO, SAR, HYPERSPECTRAL, MULTISPECTRAL, STEREO.
        providers: Filter by provider: PLANET, UMBRA, SATELLOGIC, etc.
        open_data: If true, only return free open data imagery (e.g., Sentinel-2).
        min_overlap_ratio: Minimum overlap between image and AOI (0-1).
        page_size: Number of results per page (default 20, max 100).
        next_page: Pagination cursor from a previous search response. Pass this to get the next page.
        api_key: SkyFi API key (for cloud mode; optional for local mode).

    Returns:
        JSON with archives list, total count, location info, and next_page cursor for pagination.
    """
    try:
        # Handle pagination shortcut
        if next_page:
            async with _get_client(api_key) as client:
                response = await client.search_archives_next_page(next_page)
            return _format_search_results(response, location_info=None)

        # Geocode if location is a place name, not WKT
        location_info = None
        if _is_wkt(location):
            aoi = location
        else:
            geo_result = await geocode_to_wkt(location)
            if "error" in geo_result:
                return json.dumps({
                    "error": f"Could not geocode '{location}': {geo_result['error']}",
                    "suggestion": "Try a more specific location name or provide a WKT polygon directly.",
                })
            aoi = geo_result["wkt"]
            location_info = {
                "geocoded_name": geo_result["display_name"],
                "lat": geo_result["lat"],
                "lon": geo_result["lon"],
            }

        request = GetArchivesRequest(
            aoi=aoi,
            fromDate=from_date,
            toDate=to_date,
            maxCloudCoveragePercent=max_cloud_coverage_percent,
            maxOffNadirAngle=max_off_nadir_angle,
            resolutions=[ResolutionLevel(r) for r in resolutions] if resolutions else None,
            productTypes=[ProductType(p) for p in product_types] if product_types else None,
            providers=[ApiProvider(p) for p in providers] if providers else None,
            openData=open_data,
            minOverlapRatio=min_overlap_ratio,
            pageSize=min(page_size, 100),
        )

        async with _get_client(api_key) as client:
            response = await client.search_archives(request)

        return _format_search_results(response, location_info, aoi)

    except Exception as e:
        return _format_error(e)


def _format_search_results(
    response, location_info: dict | None = None, aoi: str | None = None
) -> str:
    """Format archive search results into a clean JSON response."""
    archives = []
    for a in response.archives:
        archives.append({
            "archive_id": a.archive_id,
            "provider": a.provider.value,
            "constellation": a.constellation,
            "product_type": a.product_type.value,
            "resolution": a.resolution,
            "capture_date": a.capture_timestamp,
            "cloud_coverage_percent": a.cloud_coverage_percent,
            "gsd_cm": a.gsd,
            "price_per_sq_km_usd": a.price_per_sq_km,
            "price_full_scene_usd": a.price_full_scene,
            "total_area_sq_km": a.total_area_sq_km,
            "overlap_ratio": a.overlap_ratio,
            "overlap_sq_km": a.overlap_sq_km,
            "open_data": a.open_data,
            "thumbnail_urls": a.thumbnail_urls,
            "delivery_time_hours": a.delivery_time_hours,
        })

    result = {
        "total_results": response.total,
        "page_size": len(archives),
        "next_page": response.next_page,
        "archives": archives,
    }
    if location_info:
        result["location"] = location_info
    if aoi:
        result["aoi_wkt"] = aoi

    return json.dumps(result, indent=2)


# ══════════════════════════════════════════════════════════════════════════════════
# Tool 2: check_feasibility (Req #8 — explore feasibility)
# ══════════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=True, idempotentHint=True, openWorldHint=True,
))
async def check_feasibility(
    location: str,
    product_type: str,
    resolution: str,
    start_date: str,
    end_date: str,
    max_cloud_coverage_percent: float | None = None,
    priority_item: bool | None = None,
    required_provider: str | None = None,
    api_key: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Check feasibility of a new satellite image capture — read-only exploration.

    Use this to investigate whether a capture is possible before committing to order.
    Returns feasibility score, weather outlook, and provider availability.
    Does NOT return a confirmation token — use preview_order when ready to order.

    Accepts a plain location name or WKT polygon.

    Args:
        location: Place name (e.g., "Cairo, Egypt") OR WKT polygon.
        product_type: Product type (DAY, NIGHT, SAR, MULTISPECTRAL, HYPERSPECTRAL, etc.).
        resolution: Resolution level string.
        start_date: Start of capture window (ISO format with timezone).
        end_date: End of capture window (ISO format with timezone).
        max_cloud_coverage_percent: Maximum acceptable cloud cover.
        priority_item: Request priority processing.
        required_provider: Require a specific provider (PLANET or UMBRA).
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with feasibility score, weather forecast, provider availability, and capture windows.
    """
    try:
        # Geocode if needed
        if _is_wkt(location):
            aoi = location
        else:
            geo_result = await geocode_to_wkt(location)
            if "error" in geo_result:
                return json.dumps({"error": f"Could not geocode '{location}': {geo_result['error']}"})
            aoi = geo_result["wkt"]

        request = FeasibilityRequest(
            aoi=aoi,
            productType=product_type,
            resolution=resolution,
            startDate=start_date,
            endDate=end_date,
            maxCloudCoveragePercent=max_cloud_coverage_percent,
            priorityItem=priority_item,
            requiredProvider=required_provider,
        )

        async with _get_client(api_key) as client:
            response = await client.check_feasibility(request)

            # Auto-poll for up to 30 seconds with progress streaming
            feasibility_id = response.id
            result = None

            if response.overall_score:
                result = response
            else:
                max_polls = 10
                for i in range(max_polls):
                    if ctx:
                        await ctx.report_progress(i + 1, max_polls)
                    await asyncio.sleep(3)
                    poll_data = await client.get_feasibility_result(feasibility_id)
                    if poll_data.get("overallScore") or poll_data.get("status") in ("COMPLETE", "ERROR"):
                        result = poll_data
                        if ctx:
                            await ctx.report_progress(max_polls, max_polls)
                        break

        if result and isinstance(result, dict):
            output = {
                "feasibility_id": feasibility_id,
                "status": "complete",
                "result": result,
            }
        elif result:
            score = result.overall_score
            output = {
                "feasibility_id": feasibility_id,
                "status": "complete",
                "valid_until": result.valid_until,
                "overall_feasibility_score": score.feasibility if score else None,
                "weather_score": score.weather_score.weather_score if score and score.weather_score else None,
                "provider_score": score.provider_score.score if score and score.provider_score else None,
            }
        else:
            output = {
                "feasibility_id": feasibility_id,
                "status": "pending",
                "message": "Feasibility check still processing. Try again in a few seconds.",
            }

        output["note"] = "This is a read-only feasibility check. Use preview_order when ready to order."
        return json.dumps(output, indent=2, default=str)

    except Exception as e:
        return _format_error(e)


# ══════════════════════════════════════════════════════════════════════════════════
# Tool 3: get_pricing_overview (Req #9 — explore pricing)
# ══════════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=True, idempotentHint=True, openWorldHint=True,
))
async def get_pricing_overview(
    location: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get a broad pricing overview across all SkyFi product types and resolutions.

    Use this for general pricing questions like "how much does satellite imagery cost?"
    For exact pricing of a specific image, use preview_order instead.

    Args:
        location: Optional place name or WKT polygon for area-specific pricing.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with pricing matrix by product type and resolution level.
    """
    try:
        aoi = None
        if location:
            if _is_wkt(location):
                aoi = location
            else:
                geo_result = await geocode_to_wkt(location)
                if "error" not in geo_result:
                    aoi = geo_result["wkt"]

        async with _get_client(api_key) as client:
            pricing = await client.get_pricing(aoi)

        return json.dumps({
            "pricing": pricing,
            "note": "These are general pricing tiers. Use preview_order for exact pricing on a specific image or tasking request.",
        }, indent=2)

    except Exception as e:
        return _format_error(e)


# ══════════════════════════════════════════════════════════════════════════════════
# Tool 4: preview_order (Reqs #3, #5 — price confirmation + feasibility)
# ══════════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=True, idempotentHint=True, openWorldHint=True,
))
async def preview_order(
    order_type: str,
    location: str,
    archive_id: str | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
    product_type: str | None = None,
    resolution: str | None = None,
    max_cloud_coverage_percent: float | None = None,
    priority_item: bool | None = None,
    required_provider: str | None = None,
    api_key: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Preview an order with exact pricing and feasibility check. Returns a confirmation_token.

    MUST be called before confirm_order. Present the results to the user and get
    their explicit approval before proceeding.

    For ARCHIVE orders: provide archive_id from search results.
    For TASKING orders: provide capture window, product_type, and resolution.
    Tasking orders automatically include a feasibility check.

    Args:
        order_type: "ARCHIVE" or "TASKING".
        location: Place name or WKT polygon (the area of interest).
        archive_id: Required for ARCHIVE orders. The archive image UUID from search results.
        window_start: Required for TASKING. Capture window start (ISO format).
        window_end: Required for TASKING. Capture window end (ISO format).
        product_type: Required for TASKING. Product type (DAY, NIGHT, SAR, etc.).
        resolution: Required for TASKING. Resolution level string.
        max_cloud_coverage_percent: For TASKING. Maximum acceptable cloud cover.
        priority_item: For TASKING. Request priority processing.
        required_provider: For TASKING. Require a specific provider.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with exact pricing, feasibility (for tasking), and a confirmation_token.
        The confirmation_token is REQUIRED to call confirm_order.
    """
    try:
        # Geocode if needed
        if _is_wkt(location):
            aoi = location
        else:
            geo_result = await geocode_to_wkt(location)
            if "error" in geo_result:
                return json.dumps({"error": f"Could not geocode '{location}': {geo_result['error']}"})
            aoi = geo_result["wkt"]

        order_type_upper = order_type.upper()

        if order_type_upper == "ARCHIVE":
            if not archive_id:
                return json.dumps({"error": "archive_id is required for ARCHIVE orders."})
            return await _preview_archive_order(aoi, archive_id, api_key)

        elif order_type_upper == "TASKING":
            if not all([window_start, window_end, product_type, resolution]):
                return json.dumps({
                    "error": "window_start, window_end, product_type, and resolution are all required for TASKING orders."
                })
            return await _preview_tasking_order(
                aoi, window_start, window_end, product_type, resolution,
                max_cloud_coverage_percent, priority_item, required_provider, api_key, ctx,
            )
        else:
            return json.dumps({"error": f"Invalid order_type '{order_type}'. Must be ARCHIVE or TASKING."})

    except Exception as e:
        return _format_error(e)


async def _preview_archive_order(aoi: str, archive_id: str, api_key: str | None) -> str:
    """Preview an archive order: get pricing and generate confirmation token."""
    async with _get_client(api_key) as client:
        # Get archive details for pricing
        archive = await client.get_archive_details(archive_id)
        pricing = await client.get_pricing(aoi)

    ctx = {
        "type": "archive_order",
        "archive_id": archive_id,
        "aoi": aoi[:100],
        "ts": time.time(),
    }
    confirmation_token = archive_token_manager.create_token("order", ctx)

    return json.dumps({
        "order_type": "ARCHIVE",
        "archive_id": archive_id,
        "provider": archive.provider.value,
        "constellation": archive.constellation,
        "product_type": archive.product_type.value,
        "resolution": archive.resolution,
        "capture_date": archive.capture_timestamp,
        "cloud_coverage_percent": archive.cloud_coverage_percent,
        "price_per_sq_km_usd": archive.price_per_sq_km,
        "price_full_scene_usd": archive.price_full_scene,
        "min_area_sq_km": archive.min_sq_km,
        "delivery_time_hours": archive.delivery_time_hours,
        "pricing_matrix": pricing,
        "confirmation_token": confirmation_token,
        "token_valid_for_seconds": archive_token_manager.ttl_seconds,
        "instructions": (
            "Present this pricing to the user. If they approve, call confirm_order "
            "with the confirmation_token, order_type='ARCHIVE', and the archive_id."
        ),
    }, indent=2)


async def _preview_tasking_order(
    aoi: str,
    window_start: str,
    window_end: str,
    product_type: str,
    resolution: str,
    max_cloud_coverage_percent: float | None,
    priority_item: bool | None,
    required_provider: str | None,
    api_key: str | None,
    ctx: Context | None = None,
) -> str:
    """Preview a tasking order: run feasibility check, get pricing, generate token."""
    # Run feasibility check
    request = FeasibilityRequest(
        aoi=aoi,
        productType=product_type,
        resolution=resolution,
        startDate=window_start,
        endDate=window_end,
        maxCloudCoveragePercent=max_cloud_coverage_percent,
        priorityItem=priority_item,
        requiredProvider=required_provider,
    )

    async with _get_client(api_key) as client:
        feas_response = await client.check_feasibility(request)

        # Auto-poll feasibility with progress streaming
        feasibility_id = feas_response.id
        feas_result = None
        if feas_response.overall_score:
            feas_result = feas_response
        else:
            max_polls = 10
            for i in range(max_polls):
                if ctx:
                    await ctx.report_progress(i + 1, max_polls)
                await asyncio.sleep(3)
                poll_data = await client.get_feasibility_result(feasibility_id)
                if poll_data.get("overallScore") or poll_data.get("status") in ("COMPLETE", "ERROR"):
                    feas_result = poll_data
                    if ctx:
                        await ctx.report_progress(max_polls, max_polls)
                    break

        # Get pricing
        pricing = await client.get_pricing(aoi)

    # Build feasibility summary
    feasibility_summary = {"feasibility_id": feasibility_id, "status": "pending"}
    if feas_result and isinstance(feas_result, dict):
        feasibility_summary = {
            "feasibility_id": feasibility_id,
            "status": "complete",
            "details": feas_result,
        }
    elif feas_result:
        score = feas_result.overall_score
        feasibility_summary = {
            "feasibility_id": feasibility_id,
            "status": "complete",
            "overall_score": score.feasibility if score else None,
            "weather_score": score.weather_score.weather_score if score and score.weather_score else None,
            "provider_score": score.provider_score.score if score and score.provider_score else None,
        }

    ctx = {
        "type": "tasking_order",
        "aoi": aoi[:100],
        "product": product_type,
        "window_start": window_start,
        "ts": time.time(),
    }
    confirmation_token = tasking_token_manager.create_token("order", ctx)

    return json.dumps({
        "order_type": "TASKING",
        "product_type": product_type,
        "resolution": resolution,
        "window_start": window_start,
        "window_end": window_end,
        "feasibility": feasibility_summary,
        "pricing_matrix": pricing,
        "confirmation_token": confirmation_token,
        "token_valid_for_seconds": tasking_token_manager.ttl_seconds,
        "token_note": "Tasking tokens are valid for 24 hours to allow time for feasibility review.",
        "instructions": (
            "Present the feasibility results and pricing to the user. "
            "If they approve, call confirm_order with the confirmation_token and order_type='TASKING'."
        ),
    }, indent=2, default=str)


# ══════════════════════════════════════════════════════════════════════════════════
# Tool 5: confirm_order (Reqs #2, #4 — place order + human confirmation)
# ══════════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True,
))
async def confirm_order(
    confirmation_token: str,
    order_type: str,
    location: str,
    # Archive-specific
    archive_id: str | None = None,
    # Tasking-specific
    window_start: str | None = None,
    window_end: str | None = None,
    product_type: str | None = None,
    resolution: str | None = None,
    priority_item: bool = False,
    max_cloud_coverage_percent: int = 20,
    max_off_nadir_angle: int = 30,
    required_provider: str | None = None,
    # SAR optional params
    sar_product_types: list[str] | None = None,
    sar_polarisation: str | None = None,
    sar_grazing_angle_min: float | None = None,
    sar_grazing_angle_max: float | None = None,
    sar_azimuth_angle_min: float | None = None,
    sar_azimuth_angle_max: float | None = None,
    sar_number_of_looks: int | None = None,
    provider_window_id: str | None = None,
    # Delivery
    delivery_driver: str = "NONE",
    delivery_params: dict | None = None,
    label: str = "MCP Order",
    webhook_url: str | None = None,
    metadata: dict | None = None,
    api_key: str | None = None,
) -> str:
    """Place a satellite imagery order. CHARGES THE USER'S ACCOUNT.

    REQUIRES a confirmation_token from preview_order. You MUST have presented
    the price to the user and received their explicit approval before calling this.

    Args:
        confirmation_token: Token from preview_order. Required.
        order_type: "ARCHIVE" or "TASKING".
        location: Place name or WKT polygon (area of interest).
        archive_id: Required for ARCHIVE orders. The archive image UUID.
        window_start: Required for TASKING. Capture window start (ISO format).
        window_end: Required for TASKING. Capture window end (ISO format).
        product_type: Required for TASKING. Product type (DAY, NIGHT, SAR, etc.).
        resolution: Required for TASKING. Resolution level.
        priority_item: For TASKING. Request priority processing.
        max_cloud_coverage_percent: For TASKING. Max cloud cover (0-100, default 20).
        max_off_nadir_angle: For TASKING. Max off-nadir angle (0-45, default 30).
        required_provider: For TASKING. Specific provider to use.
        sar_product_types: SAR product types (GEC, SICD, SIDD, CPHD).
        sar_polarisation: SAR polarisation (HH or VV).
        sar_grazing_angle_min: SAR min grazing angle (10-80).
        sar_grazing_angle_max: SAR max grazing angle (10-80).
        sar_azimuth_angle_min: SAR min azimuth angle (0-360).
        sar_azimuth_angle_max: SAR max azimuth angle (0-360).
        sar_number_of_looks: SAR number of looks.
        provider_window_id: Specific provider window ID from pass prediction.
        delivery_driver: Where to deliver: NONE, S3, GS, AZURE (default NONE).
        delivery_params: Driver-specific params (bucket_id, region, keys, etc.).
        label: Label for this order.
        webhook_url: Webhook URL for order status updates.
        metadata: Custom metadata to attach.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with order confirmation, cost, and delivery status.
    """
    # Validate confirmation token — try both managers (archive=5min, tasking=24hr)
    # We try the appropriate manager first based on order_type for better error messages
    order_type_upper = order_type.upper()
    if order_type_upper == "ARCHIVE":
        valid, msg = archive_token_manager.validate_token(confirmation_token, "order")
    elif order_type_upper == "TASKING":
        valid, msg = tasking_token_manager.validate_token(confirmation_token, "order")
    else:
        valid, msg = False, f"Invalid order_type '{order_type}'"

    if not valid:
        return json.dumps({
            "error": f"Order rejected: {msg}",
            "instructions": (
                "You must call preview_order first, present the results to the user, "
                "get their confirmation, then use the confirmation_token from that response."
            ),
        })

    try:
        # Geocode if needed
        if _is_wkt(location):
            aoi = location
        else:
            geo_result = await geocode_to_wkt(location)
            if "error" in geo_result:
                return json.dumps({"error": f"Could not geocode '{location}': {geo_result['error']}"})
            aoi = geo_result["wkt"]

        if order_type_upper == "ARCHIVE":
            if not archive_id:
                return json.dumps({"error": "archive_id is required for ARCHIVE orders."})

            request = ArchiveOrderRequest(
                aoi=aoi,
                archiveId=archive_id,
                deliveryDriver=delivery_driver,
                deliveryParams=delivery_params,
                label=label,
                webhookUrl=webhook_url,
                metadata=metadata,
            )
            async with _get_client(api_key) as client:
                response = await client.create_archive_order(request)

            return json.dumps({
                "status": "order_placed",
                "order_type": "ARCHIVE",
                "order_id": response.order_id,
                "order_code": response.order_code,
                "order_cost_cents": response.order_cost,
                "order_cost_usd": response.order_cost / 100,
                "delivery_status": response.status.value,
                "aoi_sq_km": response.aoi_sq_km,
                "download_image_url": response.download_image_url,
                "download_payload_url": response.download_payload_url,
                "created_at": response.created_at,
            }, indent=2)

        elif order_type_upper == "TASKING":
            if not all([window_start, window_end, product_type, resolution]):
                return json.dumps({
                    "error": "window_start, window_end, product_type, and resolution are all required for TASKING orders."
                })

            request = TaskingOrderRequest(
                aoi=aoi,
                windowStart=window_start,
                windowEnd=window_end,
                productType=product_type,
                resolution=resolution,
                deliveryDriver=delivery_driver,
                deliveryParams=delivery_params,
                label=label,
                webhookUrl=webhook_url,
                metadata=metadata,
                priorityItem=priority_item,
                maxCloudCoveragePercent=max_cloud_coverage_percent,
                maxOffNadirAngle=max_off_nadir_angle,
                requiredProvider=ApiProvider(required_provider) if required_provider else None,
                sarProductTypes=[SarProductType(s) for s in sar_product_types] if sar_product_types else None,
                sarPolarisation=SarPolarisation(sar_polarisation) if sar_polarisation else None,
                sarGrazingAngleMin=sar_grazing_angle_min,
                sarGrazingAngleMax=sar_grazing_angle_max,
                sarAzimuthAngleMin=sar_azimuth_angle_min,
                sarAzimuthAngleMax=sar_azimuth_angle_max,
                sarNumberOfLooks=sar_number_of_looks,
                providerWindowId=provider_window_id,
            )
            async with _get_client(api_key) as client:
                response = await client.create_tasking_order(request)

            return json.dumps({
                "status": "order_placed",
                "order_type": "TASKING",
                "order_id": response.order_id,
                "order_code": response.order_code,
                "order_cost_cents": response.order_cost,
                "order_cost_usd": response.order_cost / 100,
                "delivery_status": response.status.value,
                "window_start": response.window_start,
                "window_end": response.window_end,
                "product_type": response.product_type.value,
                "resolution": response.resolution,
                "aoi_sq_km": response.aoi_sq_km,
                "created_at": response.created_at,
            }, indent=2)

        else:
            return json.dumps({"error": f"Invalid order_type '{order_type}'. Must be ARCHIVE or TASKING."})

    except Exception as e:
        return _format_error(e)


# ══════════════════════════════════════════════════════════════════════════════════
# Tool 6: check_order_status (Req #7 — explore previous orders)
# ══════════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=True, idempotentHint=True, openWorldHint=True,
))
async def check_order_status(
    order_id: str | None = None,
    order_type: str | None = None,
    page_number: int = 0,
    page_size: int = 25,
    sort_by: str = "created_at",
    sort_direction: str = "desc",
    api_key: str | None = None,
) -> str:
    """Check status of a specific order, or list your previous orders.

    Without order_id: lists recent orders with pagination and filtering.
    With order_id: returns full details including event timeline and download URLs.

    Args:
        order_id: Specific order UUID. If omitted, lists recent orders.
        order_type: Filter by type: ARCHIVE or TASKING. Only used when listing.
        page_number: Page number for listing (0-indexed).
        page_size: Orders per page (default 25).
        sort_by: Sort column: created_at, last_modified, customer_item_cost, status.
        sort_direction: Sort direction: asc or desc.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with order details or paginated order list.
    """
    try:
        async with _get_client(api_key) as client:
            if order_id:
                # Get specific order details
                result = await client.get_order_status(order_id)
                return json.dumps(result, indent=2, default=str)
            else:
                # List orders
                response = await client.list_orders(
                    order_type=OrderType(order_type) if order_type else None,
                    page_number=page_number,
                    page_size=page_size,
                    sort_columns=[SortColumn(sort_by)],
                    sort_directions=[SortDirection(sort_direction)],
                )

                orders = []
                for o in response.orders:
                    info = o.order_info
                    orders.append({
                        "order_id": info.order_id,
                        "order_code": info.order_code,
                        "order_type": info.order_type.value,
                        "status": info.status.value,
                        "cost_cents": info.order_cost,
                        "cost_usd": info.order_cost / 100,
                        "aoi_sq_km": info.aoi_sq_km,
                        "created_at": info.created_at,
                        "download_image_url": info.download_image_url,
                        "download_payload_url": info.download_payload_url,
                        "download_cog_url": getattr(info, "download_cog_url", None),
                        "latest_event": {
                            "status": o.event.status.value,
                            "timestamp": o.event.timestamp,
                            "message": o.event.message,
                        },
                    })

                return json.dumps({
                    "total": response.total,
                    "page_number": page_number,
                    "page_size": len(orders),
                    "orders": orders,
                }, indent=2)

    except Exception as e:
        return _format_error(e)


# ══════════════════════════════════════════════════════════════════════════════════
# Tool 7: get_download_url (Req #7 — fetch ordered images)
# ══════════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=True, idempotentHint=True, openWorldHint=True,
))
async def get_download_url(
    order_id: str,
    deliverable_type: str = "image",
    api_key: str | None = None,
) -> str:
    """Get a time-limited download URL for an order's deliverable.

    Args:
        order_id: The UUID of the order.
        deliverable_type: Type of deliverable: image, payload, cog.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with the signed download URL.
    """
    try:
        async with _get_client(api_key) as client:
            url = await client.get_download_url(order_id, DeliverableType(deliverable_type))
        return json.dumps({
            "download_url": url,
            "deliverable_type": deliverable_type,
            "order_id": order_id,
            "note": "This URL is time-limited. Download promptly.",
        })
    except Exception as e:
        return _format_error(e)


# ══════════════════════════════════════════════════════════════════════════════════
# Tool 8: setup_area_monitoring (Req #10 — AOI monitoring)
# ══════════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True,
))
async def setup_area_monitoring(
    action: str,
    location: str | None = None,
    webhook_url: str | None = None,
    notification_id: str | None = None,
    gsd_min: int | None = None,
    gsd_max: int | None = None,
    product_type: str | None = None,
    page_number: int = 0,
    page_size: int = 10,
    api_key: str | None = None,
) -> str:
    """Manage AOI (Area of Interest) monitoring for automated new imagery alerts.

    Actions:
    - "create": Set up a new monitor (requires location + webhook_url)
    - "list": List all active monitors
    - "history": Get trigger history for a monitor (requires notification_id)
    - "delete": Remove a monitor (requires notification_id)

    Args:
        action: One of: create, list, history, delete.
        location: Place name or WKT polygon. Required for "create".
        webhook_url: URL to receive webhook notifications. Required for "create".
        notification_id: Monitor UUID. Required for "history" and "delete".
        gsd_min: For "create": minimum ground sample distance filter.
        gsd_max: For "create": maximum ground sample distance filter.
        product_type: For "create": filter by product type (DAY, SAR, etc.).
        page_number: For "list": page number (0-indexed).
        page_size: For "list": monitors per page.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with action result (created monitor, monitor list, history, or deletion status).
    """
    try:
        action_lower = action.lower()

        if action_lower == "create":
            if not location or not webhook_url:
                return json.dumps({"error": "Both 'location' and 'webhook_url' are required for create action."})

            # Geocode if needed
            if _is_wkt(location):
                aoi = location
            else:
                geo_result = await geocode_to_wkt(location)
                if "error" in geo_result:
                    return json.dumps({"error": f"Could not geocode '{location}': {geo_result['error']}"})
                aoi = geo_result["wkt"]

            request = NotificationRequest(
                aoi=aoi,
                webhookUrl=webhook_url,
                gsdMin=gsd_min,
                gsdMax=gsd_max,
                productType=ProductType(product_type) if product_type else None,
            )
            async with _get_client(api_key) as client:
                response = await client.create_notification(request)

            return json.dumps({
                "action": "created",
                "notification_id": response.id,
                "aoi": response.aoi,
                "webhook_url": response.webhook_url,
                "gsd_min": response.gsd_min,
                "gsd_max": response.gsd_max,
                "product_type": response.product_type.value if response.product_type else None,
                "created_at": response.created_at,
                "status": "active",
            }, indent=2)

        elif action_lower == "list":
            async with _get_client(api_key) as client:
                response = await client.list_notifications(page_number, page_size)

            notifications = []
            for n in response.notifications:
                notifications.append({
                    "notification_id": n.id,
                    "aoi": n.aoi,
                    "webhook_url": n.webhook_url,
                    "gsd_min": n.gsd_min,
                    "gsd_max": n.gsd_max,
                    "product_type": n.product_type.value if n.product_type else None,
                    "created_at": n.created_at,
                })

            return json.dumps({
                "action": "list",
                "total": response.total,
                "notifications": notifications,
            }, indent=2)

        elif action_lower == "history":
            if not notification_id:
                return json.dumps({"error": "notification_id is required for history action."})

            async with _get_client(api_key) as client:
                response = await client.get_notification_history(notification_id)

            return json.dumps({
                "action": "history",
                "notification_id": response.id,
                "aoi": response.aoi,
                "webhook_url": response.webhook_url,
                "created_at": response.created_at,
                "history_events": [e.model_dump() for e in response.history],
            }, indent=2, default=str)

        elif action_lower == "delete":
            if not notification_id:
                return json.dumps({"error": "notification_id is required for delete action."})

            async with _get_client(api_key) as client:
                result = await client.delete_notification(notification_id)

            return json.dumps({
                "action": "deleted",
                "notification_id": notification_id,
                "status": result.status,
            })

        else:
            return json.dumps({
                "error": f"Invalid action '{action}'. Must be one of: create, list, history, delete."
            })

    except Exception as e:
        return _format_error(e)


# ══════════════════════════════════════════════════════════════════════════════════
# Tool 9: check_new_images (Req #11 — webhook notifications)
# ══════════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=True, idempotentHint=True, openWorldHint=False,
))
async def check_new_images(
    notification_id: str | None = None,
    hours: int = 24,
    mark_as_read: bool = True,
) -> str:
    """Check for new satellite images from your AOI monitoring webhooks.

    Reads from the local webhook event store. Events are stored when SkyFi
    sends webhook notifications for your active monitors.

    Args:
        notification_id: Filter by monitor ID. None for all monitors.
        hours: Look back this many hours (default 24).
        mark_as_read: Mark returned events as read (default true).

    Returns:
        JSON with new image notifications.
    """
    try:
        if mark_as_read:
            events = event_store.get_unread_events(notification_id)
        else:
            events = event_store.get_recent_events(notification_id, hours)

        results = []
        event_ids = []
        for e in events:
            results.append({
                "event_id": e.id,
                "notification_id": e.notification_id,
                "received_at": e.received_at,
                "payload": e.payload,
            })
            event_ids.append(e.id)

        if mark_as_read and event_ids:
            event_store.mark_read(event_ids)

        return json.dumps({
            "total_new_events": len(results),
            "events": results,
        }, indent=2, default=str)

    except Exception as e:
        return _format_error(e)


# ══════════════════════════════════════════════════════════════════════════════════
# Tool 10: geocode_location (Req #17 — standalone OSM geocoding)
# ══════════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=True, idempotentHint=True, openWorldHint=True,
))
async def geocode_location(
    location_name: str,
    buffer_km: float = 1.0,
) -> str:
    """Convert a place name to WKT coordinates.

    Use this for standalone geocoding when you need coordinates or a WKT polygon
    without searching for imagery. For imagery search, use search_satellite_imagery
    instead — it handles geocoding automatically.

    Args:
        location_name: Human-readable place name (e.g., "Suez Canal", "LAX Airport").
        buffer_km: Buffer in km around point locations (default 1km).

    Returns:
        JSON with WKT polygon, coordinates, and display name.
    """
    try:
        result = await geocode_to_wkt(location_name, buffer_km)
        return json.dumps(result, indent=2)
    except Exception as e:
        return _format_error(e)


# ══════════════════════════════════════════════════════════════════════════════════
# Tool 11: search_nearby_pois (Req #17 — OSM POI search)
# ══════════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=True, idempotentHint=True, openWorldHint=True,
))
async def search_nearby_pois(
    lat: float,
    lon: float,
    feature_type: str = "aeroway",
    radius_km: float = 50.0,
    limit: int = 10,
) -> str:
    """Search for points of interest near a location using OpenStreetMap.

    Useful for discovering satellite imagery targets like airports, ports,
    military bases, power plants, etc.

    Args:
        lat: Center latitude.
        lon: Center longitude.
        feature_type: OSM feature type. Common types:
            aeroway (airports), amenity (facilities), building, harbour/port,
            military, natural, power, waterway, industrial, tourism, railway.
        radius_km: Search radius in kilometers (default 50).
        limit: Maximum number of results (default 10).

    Returns:
        JSON with matching features including names and coordinates.
    """
    try:
        result = await search_nearby_features(lat, lon, feature_type, radius_km, limit)
        return json.dumps(result, indent=2)
    except Exception as e:
        return _format_error(e)


# ══════════════════════════════════════════════════════════════════════════════════
# Tool 12: get_account_info (Req #12 — auth/payments)
# ══════════════════════════════════════════════════════════════════════════════════


@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=True, idempotentHint=True, openWorldHint=True,
))
async def get_account_info(
    api_key: str | None = None,
) -> str:
    """Get your SkyFi account information including budget and payment status.

    Useful to check remaining budget before placing orders.

    Args:
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with account details, budget usage, and payment status.
    """
    try:
        async with _get_client(api_key) as client:
            user = await client.whoami()

        return json.dumps({
            "id": user.id,
            "email": user.email,
            "name": f"{user.first_name} {user.last_name}",
            "organization_id": user.organization_id,
            "is_demo_account": user.is_demo_account,
            "budget_used_cents": user.current_budget_usage,
            "budget_used_usd": user.current_budget_usage / 100,
            "budget_total_cents": user.budget_amount,
            "budget_total_usd": user.budget_amount / 100,
            "budget_remaining_usd": (user.budget_amount - user.current_budget_usage) / 100,
            "has_valid_payment_method": user.has_valid_shared_card,
        }, indent=2)

    except Exception as e:
        return _format_error(e)
