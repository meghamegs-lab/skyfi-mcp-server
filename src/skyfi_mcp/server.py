"""SkyFi MCP Server — the main FastMCP server with all tool definitions.

Supports both local (config file) and cloud (header-based) authentication.
Transport: Streamable HTTP + SSE via FastMCP's built-in Starlette server.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastmcp import FastMCP

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
        "place orders, and monitor areas of interest for new imagery. "
        "IMPORTANT: Before placing any order, you MUST first call get_pricing_options or "
        "check_feasibility to get a confirmation_token. Present the price and feasibility "
        "to the user and get their explicit approval before calling create_archive_order "
        "or create_tasking_order with the token."
    ),
)

token_manager = ConfirmationTokenManager()
event_store = WebhookEventStore()


# NOTE: custom_route is broken in fastmcp >= 2.4. Custom HTTP routes
# (health, webhook, landing page) are mounted in __main__.py via Starlette.


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
        return f"SkyFi API Error ({e.status_code}): {e.detail}"
    return f"Error: {e}"


# ── Search & Discovery Tools ───────────────────────────────────────────────────


@mcp.tool()
async def search_archive(
    aoi: str,
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
    api_key: str | None = None,
) -> str:
    """Search the SkyFi satellite image catalog.

    Use geocode_to_wkt first to convert a place name to WKT format for the aoi parameter.

    Args:
        aoi: Area of interest in WKT format (e.g., POLYGON((...))). Use geocode_to_wkt to get this.
        from_date: Start date filter (ISO format, e.g., 2024-01-01T00:00:00+00:00).
        to_date: End date filter (ISO format).
        max_cloud_coverage_percent: Maximum cloud cover (0-100).
        max_off_nadir_angle: Maximum off-nadir angle (0-50).
        resolutions: Filter by resolution level: LOW, MEDIUM, HIGH, VERY_HIGH, ULTRA_HIGH.
        product_types: Filter by product: DAY, NIGHT, VIDEO, SAR, HYPERSPECTRAL, MULTISPECTRAL, STEREO.
        providers: Filter by provider: PLANET, UMBRA, SATELLOGIC, etc.
        open_data: If true, only return free open data imagery (e.g., Sentinel-2).
        min_overlap_ratio: Minimum overlap between image and AOI (0-1).
        page_size: Number of results per page (default 20, max 100).
        api_key: SkyFi API key (for cloud mode; optional for local mode).

    Returns:
        JSON with archives list, total count, and next_page cursor for pagination.
    """
    try:
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

        return json.dumps({
            "total_results": response.total,
            "page_size": len(archives),
            "next_page": response.next_page,
            "archives": archives,
        }, indent=2)

    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def search_archive_next_page(
    next_page: str,
    api_key: str | None = None,
) -> str:
    """Continue paginating through archive search results.

    Args:
        next_page: The next_page cursor from a previous search_archive response.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with next page of archives and updated cursor.
    """
    try:
        async with _get_client(api_key) as client:
            response = await client.search_archives_next_page(next_page)

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
                "open_data": a.open_data,
                "overlap_ratio": a.overlap_ratio,
            })

        return json.dumps({
            "total_results": response.total,
            "page_size": len(archives),
            "next_page": response.next_page,
            "archives": archives,
        }, indent=2)

    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def get_archive_details(
    archive_id: str,
    api_key: str | None = None,
) -> str:
    """Get full metadata for a specific archive image.

    Args:
        archive_id: The UUID of the archive image.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with complete archive metadata including footprint, pricing, and thumbnail URLs.
    """
    try:
        async with _get_client(api_key) as client:
            a = await client.get_archive_details(archive_id)

        return json.dumps({
            "archive_id": a.archive_id,
            "provider": a.provider.value,
            "constellation": a.constellation,
            "product_type": a.product_type.value,
            "platform_resolution_cm": a.platform_resolution,
            "resolution": a.resolution,
            "capture_date": a.capture_timestamp,
            "cloud_coverage_percent": a.cloud_coverage_percent,
            "off_nadir_angle": a.off_nadir_angle,
            "footprint_wkt": a.footprint,
            "gsd_cm": a.gsd,
            "min_sq_km": a.min_sq_km,
            "max_sq_km": a.max_sq_km,
            "total_area_sq_km": a.total_area_sq_km,
            "price_per_sq_km_usd": a.price_per_sq_km,
            "price_full_scene_usd": a.price_full_scene,
            "open_data": a.open_data,
            "delivery_time_hours": a.delivery_time_hours,
            "thumbnail_urls": a.thumbnail_urls,
            "tiles_url": a.tiles_url,
        }, indent=2)

    except Exception as e:
        return _format_error(e)


# ── Pricing & Feasibility Tools ────────────────────────────────────────────────


@mcp.tool()
async def get_pricing_options(
    aoi: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get pricing options for tasking orders across all products and resolutions.

    This tool returns a confirmation_token that is REQUIRED to place orders.
    Always present the pricing information to the user before proceeding to order.

    Args:
        aoi: Optional WKT area of interest for area-specific pricing.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with pricing matrix and a confirmation_token for placing orders.
    """
    try:
        async with _get_client(api_key) as client:
            pricing = await client.get_pricing(aoi)

        # Generate confirmation token
        ctx = {"type": "pricing", "aoi": aoi or "global", "ts": time.time()}
        confirmation_token = token_manager.create_token("order", ctx)

        return json.dumps({
            "pricing": pricing,
            "confirmation_token": confirmation_token,
            "token_valid_for_seconds": token_manager.ttl_seconds,
            "instructions": (
                "Present these pricing options to the user. "
                "Use the confirmation_token when calling create_archive_order or "
                "create_tasking_order after the user confirms."
            ),
        }, indent=2)

    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def check_feasibility(
    aoi: str,
    product_type: str,
    resolution: str,
    start_date: str,
    end_date: str,
    max_cloud_coverage_percent: float | None = None,
    priority_item: bool | None = None,
    required_provider: str | None = None,
    api_key: str | None = None,
) -> str:
    """Check feasibility of a new satellite image capture for an area.

    Starts an async feasibility check and polls for up to 30 seconds.
    Returns a confirmation_token that is REQUIRED to place tasking orders.

    Args:
        aoi: Area of interest in WKT format.
        product_type: Product type (DAY, NIGHT, SAR, MULTISPECTRAL, etc.).
        resolution: Resolution level string.
        start_date: Start of capture window (ISO format with timezone).
        end_date: End of capture window (ISO format with timezone).
        max_cloud_coverage_percent: Maximum acceptable cloud cover.
        priority_item: Request priority processing.
        required_provider: Require a specific provider (PLANET or UMBRA).
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with feasibility score, weather forecast, provider scores, and confirmation_token.
    """
    try:
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

            # Auto-poll for up to 30 seconds
            feasibility_id = response.id
            result = None

            if response.overall_score:
                result = response
            else:
                for _ in range(10):
                    await asyncio.sleep(3)
                    poll_data = await client.get_feasibility_result(feasibility_id)
                    status = poll_data.get("status") or poll_data.get("overallScore", {}).get("providerScore", {}).get("providerScores", [{}])[0].get("status")
                    if status in ("COMPLETE", "ERROR") or poll_data.get("overallScore"):
                        result = poll_data
                        break

        # Generate confirmation token
        ctx = {"type": "feasibility", "aoi": aoi, "product": product_type, "ts": time.time()}
        confirmation_token = token_manager.create_token("order", ctx)

        if result and isinstance(result, dict):
            output = {
                "feasibility_id": feasibility_id,
                "status": "complete",
                "result": result,
                "confirmation_token": confirmation_token,
                "token_valid_for_seconds": token_manager.ttl_seconds,
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
                "confirmation_token": confirmation_token,
                "token_valid_for_seconds": token_manager.ttl_seconds,
            }
        else:
            output = {
                "feasibility_id": feasibility_id,
                "status": "pending",
                "message": "Feasibility check still processing. Use get_feasibility_result to poll.",
                "confirmation_token": confirmation_token,
                "token_valid_for_seconds": token_manager.ttl_seconds,
            }

        output["instructions"] = (
            "Present the feasibility results and pricing to the user. "
            "Use the confirmation_token when placing the order after user confirms."
        )
        return json.dumps(output, indent=2, default=str)

    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def get_feasibility_result(
    feasibility_id: str,
    api_key: str | None = None,
) -> str:
    """Poll for the result of a previously started feasibility check.

    Args:
        feasibility_id: The UUID returned from check_feasibility.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with current feasibility status and results if complete.
    """
    try:
        async with _get_client(api_key) as client:
            result = await client.get_feasibility_result(feasibility_id)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def predict_satellite_passes(
    aoi: str,
    from_date: str,
    to_date: str,
    product_types: list[str] | None = None,
    resolutions: list[str] | None = None,
    max_off_nadir_angle: float | None = 30,
    api_key: str | None = None,
) -> str:
    """Find upcoming satellite passes that can observe a ground location.

    Args:
        aoi: Area of interest in WKT format.
        from_date: Start of search window (ISO format with timezone).
        to_date: End of search window (ISO format with timezone).
        product_types: Filter by product type (DAY, SAR, etc.).
        resolutions: Filter by resolution (LOW, MEDIUM, HIGH, VERY_HIGH, ULTRA_HIGH).
        max_off_nadir_angle: Maximum off-nadir angle (default 30 degrees).
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with list of satellite passes including timing, pricing, and capabilities.
    """
    try:
        request = PassPredictionRequest(
            aoi=aoi,
            fromDate=from_date,
            toDate=to_date,
            productTypes=[ProductType(p) for p in product_types] if product_types else None,
            resolutions=[ResolutionLevel(r) for r in resolutions] if resolutions else None,
            maxOffNadirAngle=max_off_nadir_angle,
        )

        async with _get_client(api_key) as client:
            response = await client.predict_passes(request)

        passes = []
        for p in response.passes:
            passes.append({
                "provider": p.provider.value,
                "satellite_name": p.sat_name,
                "product_type": p.product_type.value,
                "resolution": p.resolution,
                "pass_date": p.pass_date,
                "off_nadir_angle": p.off_nadir_angle,
                "solar_elevation_angle": p.solar_elevation_angle,
                "price_per_sq_km_usd": p.price_per_sq_km,
                "min_area_sq_km": p.min_sq_km,
                "max_area_sq_km": p.max_sq_km,
            })

        return json.dumps({
            "total_passes": len(passes),
            "passes": passes,
        }, indent=2)

    except Exception as e:
        return _format_error(e)


# ── Order Tools ────────────────────────────────────────────────────────────────


@mcp.tool()
async def create_archive_order(
    aoi: str,
    archive_id: str,
    confirmation_token: str,
    delivery_driver: str = "NONE",
    delivery_params: dict | None = None,
    label: str = "MCP Order",
    webhook_url: str | None = None,
    metadata: dict | None = None,
    api_key: str | None = None,
) -> str:
    """Place an order for an existing archive satellite image. CHARGES THE USER.

    REQUIRES a confirmation_token from get_pricing_options or check_feasibility.
    You MUST present the price to the user and get their explicit confirmation first.

    Args:
        aoi: Area of interest in WKT format.
        archive_id: The archive image UUID to order.
        confirmation_token: Token from get_pricing_options or check_feasibility.
        delivery_driver: Where to deliver: NONE, S3, GS, AZURE (default NONE).
        delivery_params: Driver-specific params (bucket_id, region, keys, etc.).
        label: Label for this order item.
        webhook_url: Webhook URL for order status updates.
        metadata: Custom metadata to attach to the order.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with order confirmation, cost, and status.
    """
    # Validate confirmation token
    valid, msg = token_manager.validate_token(confirmation_token, "order")
    if not valid:
        return json.dumps({
            "error": f"Order rejected: {msg}",
            "instructions": (
                "You must call get_pricing_options or check_feasibility first, "
                "present the results to the user, get their confirmation, "
                "then use the confirmation_token from that response."
            ),
        })

    try:
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

    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def create_tasking_order(
    aoi: str,
    window_start: str,
    window_end: str,
    product_type: str,
    resolution: str,
    confirmation_token: str,
    delivery_driver: str = "NONE",
    delivery_params: dict | None = None,
    label: str = "MCP Tasking Order",
    webhook_url: str | None = None,
    metadata: dict | None = None,
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
    api_key: str | None = None,
) -> str:
    """Place a new satellite tasking order to capture fresh imagery. CHARGES THE USER.

    REQUIRES a confirmation_token from get_pricing_options or check_feasibility.
    You MUST present the price and feasibility to the user and get their explicit confirmation first.

    Args:
        aoi: Area of interest in WKT format.
        window_start: Tasking window start (ISO format).
        window_end: Tasking window end (ISO format).
        product_type: Product type (DAY, NIGHT, SAR, MULTISPECTRAL, etc.).
        resolution: Resolution level string.
        confirmation_token: Token from get_pricing_options or check_feasibility.
        delivery_driver: Where to deliver: NONE, S3, GS, AZURE.
        delivery_params: Driver-specific params.
        label: Label for this order.
        webhook_url: Webhook URL for status updates.
        metadata: Custom metadata.
        priority_item: Request priority processing.
        max_cloud_coverage_percent: Max cloud cover (0-100, default 20).
        max_off_nadir_angle: Max off-nadir angle (0-45, default 30).
        required_provider: Specific provider to use.
        sar_product_types: SAR product types (GEC, SICD, SIDD, CPHD).
        sar_polarisation: SAR polarisation (HH or VV).
        sar_grazing_angle_min: SAR min grazing angle (10-80).
        sar_grazing_angle_max: SAR max grazing angle (10-80).
        sar_azimuth_angle_min: SAR min azimuth angle (0-360).
        sar_azimuth_angle_max: SAR max azimuth angle (0-360).
        sar_number_of_looks: SAR number of looks.
        provider_window_id: Specific provider window ID from pass prediction.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with order confirmation, cost, and status.
    """
    # Validate confirmation token
    valid, msg = token_manager.validate_token(confirmation_token, "order")
    if not valid:
        return json.dumps({
            "error": f"Order rejected: {msg}",
            "instructions": (
                "You must call get_pricing_options or check_feasibility first, "
                "present the results to the user, get their confirmation, "
                "then use the confirmation_token from that response."
            ),
        })

    try:
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

    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def list_orders(
    order_type: str | None = None,
    page_number: int = 0,
    page_size: int = 25,
    sort_by: str = "created_at",
    sort_direction: str = "desc",
    api_key: str | None = None,
) -> str:
    """List your previous SkyFi orders with pagination and filtering.

    Args:
        order_type: Filter by type: ARCHIVE or TASKING. None for all.
        page_number: Page number (0-indexed).
        page_size: Orders per page (default 25).
        sort_by: Sort column: created_at, last_modified, customer_item_cost, status.
        sort_direction: Sort direction: asc or desc.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with order list including status, cost, and download URLs.
    """
    try:
        async with _get_client(api_key) as client:
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


@mcp.tool()
async def get_order_status(
    order_id: str,
    api_key: str | None = None,
) -> str:
    """Get detailed status for a specific order, including full event history.

    Args:
        order_id: The UUID of the order.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with order details, event timeline, and download URLs.
    """
    try:
        async with _get_client(api_key) as client:
            result = await client.get_order_status(order_id)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def get_download_url(
    order_id: str,
    deliverable_type: str = "image",
    api_key: str | None = None,
) -> str:
    """Get a download URL for an order's deliverable (image, payload, or COG).

    Args:
        order_id: The UUID of the order.
        deliverable_type: Type of deliverable: image, payload, cog.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with the download URL.
    """
    try:
        async with _get_client(api_key) as client:
            url = await client.get_download_url(order_id, DeliverableType(deliverable_type))
        return json.dumps({"download_url": url, "deliverable_type": deliverable_type})
    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def schedule_redelivery(
    order_id: str,
    delivery_driver: str,
    delivery_params: dict,
    api_key: str | None = None,
) -> str:
    """Schedule redelivery of an order to a different storage destination.

    Args:
        order_id: The UUID of the order to redeliver.
        delivery_driver: Destination: S3, GS, or AZURE.
        delivery_params: Driver-specific parameters (bucket, region, credentials).
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with redelivery status.
    """
    try:
        request = OrderRedeliveryRequest(
            deliveryDriver=delivery_driver,
            deliveryParams=delivery_params,
        )
        async with _get_client(api_key) as client:
            result = await client.schedule_redelivery(order_id, request)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return _format_error(e)


# ── Notification / Monitoring Tools ────────────────────────────────────────────


@mcp.tool()
async def create_aoi_notification(
    aoi: str,
    webhook_url: str,
    gsd_min: int | None = None,
    gsd_max: int | None = None,
    product_type: str | None = None,
    api_key: str | None = None,
) -> str:
    """Set up monitoring for an area of interest to be notified of new satellite imagery.

    SkyFi will post to the webhook URL when new archive images matching the filters
    become available for the specified area.

    Args:
        aoi: Area of interest in WKT format.
        webhook_url: URL to receive webhook notifications.
        gsd_min: Minimum ground sample distance (resolution filter).
        gsd_max: Maximum ground sample distance (resolution filter).
        product_type: Filter by product type (DAY, SAR, etc.).
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with notification ID and configuration.
    """
    try:
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
            "notification_id": response.id,
            "aoi": response.aoi,
            "webhook_url": response.webhook_url,
            "gsd_min": response.gsd_min,
            "gsd_max": response.gsd_max,
            "product_type": response.product_type.value if response.product_type else None,
            "created_at": response.created_at,
            "status": "active",
        }, indent=2)

    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def list_notifications(
    page_number: int = 0,
    page_size: int = 10,
    api_key: str | None = None,
) -> str:
    """List your active AOI monitoring notifications.

    Args:
        page_number: Page number (0-indexed).
        page_size: Notifications per page.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with list of active notification monitors.
    """
    try:
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
            "total": response.total,
            "notifications": notifications,
        }, indent=2)

    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def get_notification_history(
    notification_id: str,
    api_key: str | None = None,
) -> str:
    """Get the trigger history for a specific notification monitor.

    Shows when the notification was triggered (i.e., when new imagery was detected).

    Args:
        notification_id: The UUID of the notification.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with notification details and event history.
    """
    try:
        async with _get_client(api_key) as client:
            response = await client.get_notification_history(notification_id)

        return json.dumps({
            "notification_id": response.id,
            "aoi": response.aoi,
            "webhook_url": response.webhook_url,
            "created_at": response.created_at,
            "history_events": [e.model_dump() for e in response.history],
        }, indent=2, default=str)

    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def delete_notification(
    notification_id: str,
    api_key: str | None = None,
) -> str:
    """Delete an active AOI monitoring notification.

    Args:
        notification_id: The UUID of the notification to delete.
        api_key: SkyFi API key (optional for local mode).

    Returns:
        JSON with deletion status.
    """
    try:
        async with _get_client(api_key) as client:
            result = await client.delete_notification(notification_id)
        return json.dumps({"status": result.status, "notification_id": notification_id})
    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def check_new_images(
    notification_id: str | None = None,
    hours: int = 24,
    mark_as_read: bool = True,
) -> str:
    """Check for new satellite images from your AOI monitoring webhooks.

    This tool checks the local webhook event store for new notifications.
    Use this to poll for new imagery availability (ChatGPT Pulse-style).

    Args:
        notification_id: Filter by notification ID. None for all.
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


# ── OSM Tools ──────────────────────────────────────────────────────────────────


@mcp.tool()
async def geocode_location(
    location_name: str,
    buffer_km: float = 1.0,
) -> str:
    """Convert a place name to WKT coordinates for use with SkyFi tools.

    Use this before calling search_archive or other tools that require an AOI in WKT format.
    The result includes a WKT polygon that can be directly used as the 'aoi' parameter.

    Args:
        location_name: Human-readable place name (e.g., "Suez Canal", "LAX Airport", "Manhattan").
        buffer_km: Buffer in km around the location for the bounding box (default 1km).

    Returns:
        JSON with WKT polygon, coordinates, and display name.
    """
    try:
        result = await geocode_to_wkt(location_name, buffer_km)
        return json.dumps(result, indent=2)
    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def reverse_geocode_location(
    lat: float,
    lon: float,
) -> str:
    """Convert coordinates to a human-readable place name.

    Args:
        lat: Latitude.
        lon: Longitude.

    Returns:
        JSON with display name and address details.
    """
    try:
        result = await reverse_geocode(lat, lon)
        return json.dumps(result, indent=2)
    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def search_nearby_pois(
    lat: float,
    lon: float,
    feature_type: str = "aeroway",
    radius_km: float = 50.0,
    limit: int = 10,
) -> str:
    """Search for points of interest near a location using OpenStreetMap.

    Useful for finding specific features for satellite imagery analysis.

    Args:
        lat: Center latitude.
        lon: Center longitude.
        feature_type: OSM feature type to search for. Common types:
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


# ── Account Tools ──────────────────────────────────────────────────────────────


@mcp.tool()
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
