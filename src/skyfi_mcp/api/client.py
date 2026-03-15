"""Async HTTP client for the SkyFi Platform API.

Wraps all 19 API endpoints with typed request/response models.
"""

from __future__ import annotations

from typing import Any

import httpx

from skyfi_mcp.api.models import (
    Archive,
    ArchiveOrderRequest,
    ArchiveOrderResponse,
    ArchiveResponse,
    DeliverableType,
    FeasibilityRequest,
    FeasibilityResponse,
    GetArchivesRequest,
    GetArchivesResponse,
    ListNotificationsResponse,
    ListOrdersResponse,
    NotificationRequest,
    NotificationResponse,
    NotificationWithHistoryResponse,
    OrderRedeliveryRequest,
    OrderType,
    PassPredictionRequest,
    PassPredictionResponse,
    SortColumn,
    SortDirection,
    StatusResponse,
    TaskingOrderRequest,
    TaskingOrderResponse,
    WhoamiUser,
)
from skyfi_mcp.auth.config import AuthConfig


class SkyFiAPIError(Exception):
    """Raised when the SkyFi API returns an error response."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"SkyFi API error {status_code}: {detail}")


class SkyFiClient:
    """Async client for the SkyFi Platform API.

    Usage:
        config = AuthConfig(api_key="sk-...")
        async with SkyFiClient(config) as client:
            archives = await client.search_archives(request)
    """

    def __init__(self, config: AuthConfig):
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers=config.headers,
            timeout=60.0,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()

    async def _request(
        self, method: str, path: str, json_data: dict | None = None, params: dict | None = None
    ) -> dict[str, Any]:
        """Make an authenticated request and return parsed JSON."""
        response = await self._client.request(method, path, json=json_data, params=params)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise SkyFiAPIError(response.status_code, detail)
        if response.status_code == 204:
            return {"status": "ok"}
        return response.json()

    # ── Archives ────────────────────────────────────────────────────────────

    async def search_archives(self, request: GetArchivesRequest) -> GetArchivesResponse:
        """Search the satellite image catalog.

        POST /archives
        """
        data = await self._request(
            "POST", "/archives", json_data=request.model_dump(by_alias=True, exclude_none=True)
        )
        return GetArchivesResponse.model_validate(data)

    async def search_archives_next_page(self, page_url: str) -> GetArchivesResponse:
        """Continue paginating through catalog results.

        GET /archives?page=<cursor>
        """
        data = await self._request("GET", "/archives", params={"page": page_url})
        return GetArchivesResponse.model_validate(data)

    async def get_archive_details(self, archive_id: str) -> Archive:
        """Get full information for a specific archive image.

        GET /archives/{archive_id}
        Note: Single-archive endpoint does NOT return overlap metrics
        (overlapRatio, overlapSqkm) — those only come from search.
        """
        data = await self._request("GET", f"/archives/{archive_id}")
        return Archive.model_validate(data)

    # ── Orders ──────────────────────────────────────────────────────────────

    async def create_archive_order(self, request: ArchiveOrderRequest) -> ArchiveOrderResponse:
        """Create a new archive order (charges immediately).

        POST /order-archive
        """
        data = await self._request(
            "POST", "/order-archive", json_data=request.model_dump(by_alias=True, exclude_none=True)
        )
        return ArchiveOrderResponse.model_validate(data)

    async def create_tasking_order(self, request: TaskingOrderRequest) -> TaskingOrderResponse:
        """Create a new tasking order (charges immediately).

        POST /order-tasking
        """
        data = await self._request(
            "POST", "/order-tasking", json_data=request.model_dump(by_alias=True, exclude_none=True)
        )
        return TaskingOrderResponse.model_validate(data)

    async def list_orders(
        self,
        order_type: OrderType | None = None,
        page_number: int = 0,
        page_size: int = 25,
        sort_columns: list[SortColumn] | None = None,
        sort_directions: list[SortDirection] | None = None,
    ) -> ListOrdersResponse:
        """Get paginated list of orders.

        GET /orders
        """
        params: dict[str, Any] = {
            "pageNumber": page_number,
            "pageSize": page_size,
        }
        if order_type:
            params["orderType"] = order_type.value
        json_body: dict[str, Any] = {}
        if sort_columns:
            json_body["sortColumns"] = [c.value for c in sort_columns]
        if sort_directions:
            json_body["sortDirections"] = [d.value for d in sort_directions]

        # This endpoint uses GET with a request body (unusual but per spec)
        data = await self._request("GET", "/orders", params=params, json_data=json_body or None)
        return ListOrdersResponse.model_validate(data)

    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        """Get detailed order status with event history.

        GET /orders/{order_id}

        Returns raw dict since response can be ArchiveOrderInfoResponse or TaskingOrderInfoResponse.
        """
        return await self._request("GET", f"/orders/{order_id}")

    async def schedule_redelivery(
        self, order_id: str, request: OrderRedeliveryRequest
    ) -> dict[str, Any]:
        """Schedule redelivery for an order.

        POST /orders/{order_id}/redelivery
        """
        return await self._request(
            "POST",
            f"/orders/{order_id}/redelivery",
            json_data=request.model_dump(by_alias=True, exclude_none=True),
        )

    async def get_download_url(self, order_id: str, deliverable_type: DeliverableType) -> str:
        """Get redirect URL for downloading a deliverable.

        GET /orders/{order_id}/{deliverable_type}
        """
        response = await self._client.request(
            "GET",
            f"/orders/{order_id}/{deliverable_type.value}",
            follow_redirects=False,
        )
        if response.status_code in (301, 302, 307, 308):
            return response.headers.get("location", "")
        if response.status_code >= 400:
            raise SkyFiAPIError(response.status_code, response.text)
        # If no redirect, return the response URL
        return str(response.url)

    # ── Feasibility ─────────────────────────────────────────────────────────

    async def check_feasibility(self, request: FeasibilityRequest) -> FeasibilityResponse:
        """Start a feasibility check for an AOI.

        POST /feasibility
        """
        data = await self._request(
            "POST", "/feasibility", json_data=request.model_dump(by_alias=True, exclude_none=True)
        )
        return FeasibilityResponse.model_validate(data)

    async def get_feasibility_result(self, feasibility_id: str) -> dict[str, Any]:
        """Poll for feasibility task result.

        GET /feasibility/{feasibility_id}
        """
        return await self._request("GET", f"/feasibility/{feasibility_id}")

    async def predict_passes(self, request: PassPredictionRequest) -> PassPredictionResponse:
        """Find satellite passes that can observe a location.

        POST /feasibility/pass-prediction
        """
        data = await self._request(
            "POST",
            "/feasibility/pass-prediction",
            json_data=request.model_dump(by_alias=True, exclude_none=True),
        )
        return PassPredictionResponse.model_validate(data)

    # ── Pricing ─────────────────────────────────────────────────────────────

    async def get_pricing(self, aoi: str | None = None) -> dict[str, Any]:
        """Get pricing options for tasking orders.

        POST /pricing
        """
        body = {}
        if aoi:
            body["aoi"] = aoi
        return await self._request("POST", "/pricing", json_data=body)

    # ── Notifications ───────────────────────────────────────────────────────

    async def create_notification(self, request: NotificationRequest) -> NotificationResponse:
        """Create a new AOI monitoring notification.

        POST /notifications
        """
        data = await self._request(
            "POST",
            "/notifications",
            json_data=request.model_dump(by_alias=True, exclude_none=True),
        )
        return NotificationResponse.model_validate(data)

    async def list_notifications(
        self, page_number: int = 0, page_size: int = 10
    ) -> ListNotificationsResponse:
        """List active notifications.

        GET /notifications
        """
        data = await self._request(
            "GET", "/notifications", params={"pageNumber": page_number, "pageSize": page_size}
        )
        return ListNotificationsResponse.model_validate(data)

    async def get_notification_history(
        self, notification_id: str
    ) -> NotificationWithHistoryResponse:
        """Get notification with trigger history.

        GET /notifications/{notification_id}
        """
        data = await self._request("GET", f"/notifications/{notification_id}")
        return NotificationWithHistoryResponse.model_validate(data)

    async def delete_notification(self, notification_id: str) -> StatusResponse:
        """Delete an active notification.

        DELETE /notifications/{notification_id}
        """
        data = await self._request("DELETE", f"/notifications/{notification_id}")
        return StatusResponse.model_validate(data)

    # ── Auth / Utility ──────────────────────────────────────────────────────

    async def whoami(self) -> WhoamiUser:
        """Get current user profile and budget info.

        GET /auth/whoami
        """
        data = await self._request("GET", "/auth/whoami")
        return WhoamiUser.model_validate(data)

    async def ping(self) -> str:
        """Ping the API.

        GET /ping
        """
        data = await self._request("GET", "/ping")
        return data.get("message", "pong")

    async def health_check(self) -> str:
        """Check API health.

        GET /health_check
        """
        data = await self._request("GET", "/health_check")
        return data.get("status", "unknown")
