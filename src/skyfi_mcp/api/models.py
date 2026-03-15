"""Pydantic models for the SkyFi Platform API.

Generated from https://app.skyfi.com/platform-api/openapi.json (OpenAPI 3.1.0).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ───────────────────────────────────────────────────────────────────────


class ApiProvider(str, Enum):
    """Satellite imagery providers available through SkyFi."""

    SIWEI = "SIWEI"
    SATELLOGIC = "SATELLOGIC"
    UMBRA = "UMBRA"
    GEOSAT = "GEOSAT"
    SENTINEL1_CREODIAS = "SENTINEL1_CREODIAS"
    SENTINEL2 = "SENTINEL2"
    SENTINEL2_CREODIAS = "SENTINEL2_CREODIAS"
    PLANET = "PLANET"
    IMPRO = "IMPRO"
    URBAN_SKY = "URBAN_SKY"
    NSL = "NSL"
    VEXCEL = "VEXCEL"
    VANTOR = "VANTOR"
    ICEYE_US = "ICEYE_US"


class ProductType(str, Enum):
    """Satellite product types."""

    DAY = "DAY"
    NIGHT = "NIGHT"
    VIDEO = "VIDEO"
    SAR = "SAR"
    HYPERSPECTRAL = "HYPERSPECTRAL"
    MULTISPECTRAL = "MULTISPECTRAL"
    STEREO = "STEREO"
    BASEMAP = "BASEMAP"


class ResolutionLevel(str, Enum):
    """Resolution filter levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"
    ULTRA_HIGH = "ULTRA_HIGH"


class DeliveryDriver(str, Enum):
    """Delivery destination drivers."""

    GS = "GS"
    S3 = "S3"
    AZURE = "AZURE"
    DELIVERY_CONFIG = "DELIVERY_CONFIG"
    S3_SERVICE_ACCOUNT = "S3_SERVICE_ACCOUNT"
    GS_SERVICE_ACCOUNT = "GS_SERVICE_ACCOUNT"
    AZURE_SERVICE_ACCOUNT = "AZURE_SERVICE_ACCOUNT"
    NONE = "NONE"


class DeliveryStatus(str, Enum):
    """Order delivery status progression."""

    CREATED = "CREATED"
    STARTED = "STARTED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PLATFORM_FAILED = "PLATFORM_FAILED"
    PROVIDER_PENDING = "PROVIDER_PENDING"
    PROVIDER_COMPLETE = "PROVIDER_COMPLETE"
    PROVIDER_FAILED = "PROVIDER_FAILED"
    PROCESSING_PENDING = "PROCESSING_PENDING"
    PROCESSING_COMPLETE = "PROCESSING_COMPLETE"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    DELIVERY_PENDING = "DELIVERY_PENDING"
    DELIVERY_COMPLETED = "DELIVERY_COMPLETED"
    DELIVERY_FAILED = "DELIVERY_FAILED"
    INTERNAL_IMAGE_PROCESSING_PENDING = "INTERNAL_IMAGE_PROCESSING_PENDING"


class DeliverableType(str, Enum):
    """Types of downloadable deliverables."""

    IMAGE = "image"
    PAYLOAD = "payload"
    COG = "cog"
    BABA = "baba"


class OrderType(str, Enum):
    """Order types."""

    ARCHIVE = "ARCHIVE"
    TASKING = "TASKING"


class FeasibilityCheckStatus(str, Enum):
    """Feasibility task processing status."""

    PENDING = "PENDING"
    STARTED = "STARTED"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"


class SortColumn(str, Enum):
    """Sortable columns for order listing."""

    CREATED_AT = "created_at"
    LAST_MODIFIED = "last_modified"
    CUSTOMER_ITEM_COST = "customer_item_cost"
    STATUS = "status"


class SortDirection(str, Enum):
    """Sort direction."""

    ASC = "asc"
    DESC = "desc"


class SarPolarisation(str, Enum):
    """SAR polarisation options."""

    HH = "HH"
    VV = "VV"


class SarProductType(str, Enum):
    """SAR-specific product types."""

    GEC = "GEC"
    SICD = "SICD"
    SIDD = "SIDD"
    CPHD = "CPHD"


# ── Archive Models ──────────────────────────────────────────────────────────────


class Archive(BaseModel):
    """A single archive image in the SkyFi catalog."""

    archive_id: str = Field(alias="archiveId")
    provider: ApiProvider
    constellation: str
    product_type: ProductType = Field(alias="productType")
    platform_resolution: float = Field(alias="platformResolution", description="Nadir resolution in cm")
    resolution: str
    capture_timestamp: str = Field(alias="captureTimestamp")
    cloud_coverage_percent: float | None = Field(None, alias="cloudCoveragePercent")
    off_nadir_angle: float | None = Field(None, alias="offNadirAngle")
    footprint: str = Field(description="WKT representation")
    min_sq_km: float = Field(alias="minSqKm")
    max_sq_km: float = Field(alias="maxSqKm")
    price_per_sq_km: float = Field(alias="priceForOneSquareKm", description="USD per sq km")
    price_per_sq_km_cents: int = Field(alias="priceForOneSquareKmCents")
    price_full_scene: float = Field(alias="priceFullScene", description="Full scene price in USD")
    open_data: bool = Field(False, alias="openData")
    total_area_sq_km: float = Field(alias="totalAreaSquareKm")
    delivery_time_hours: float = Field(12, alias="deliveryTimeHours")
    thumbnail_urls: dict[str, str] | None = Field(None, alias="thumbnailUrls")
    gsd: float = Field(description="Ground Sample Distance")
    tiles_url: str | None = Field(None, alias="tilesUrl")

    model_config = {"populate_by_name": True}


class ArchiveResponse(Archive):
    """Archive with overlap metrics (returned from search)."""

    overlap_ratio: float = Field(alias="overlapRatio")
    overlap_sq_km: float = Field(alias="overlapSqkm")

    model_config = {"populate_by_name": True}


class GetArchivesRequest(BaseModel):
    """Request body for POST /archives."""

    aoi: str = Field(description="WKT representation of area of interest")
    from_date: str | None = Field(None, alias="fromDate", description="ISO datetime with timezone")
    to_date: str | None = Field(None, alias="toDate", description="ISO datetime with timezone")
    max_cloud_coverage_percent: float | None = Field(None, alias="maxCloudCoveragePercent", ge=0, le=100)
    max_off_nadir_angle: float | None = Field(None, alias="maxOffNadirAngle", ge=0, le=50)
    resolutions: list[ResolutionLevel] | None = None
    product_types: list[ProductType] | None = Field(None, alias="productTypes")
    providers: list[ApiProvider] | None = None
    open_data: bool | None = Field(None, alias="openData")
    min_overlap_ratio: float | None = Field(None, alias="minOverlapRatio", ge=0, le=1)
    page_size: int = Field(100, alias="pageSize", ge=1)

    model_config = {"populate_by_name": True}


class GetArchivesResponse(BaseModel):
    """Response from archive search."""

    request: dict[str, Any]
    archives: list[ArchiveResponse]
    next_page: str | None = Field(None, alias="nextPage")
    total: int | None = None

    model_config = {"populate_by_name": True}


# ── Order Models ────────────────────────────────────────────────────────────────


class DeliveryEventInfo(BaseModel):
    """A single status change event for an order."""

    status: DeliveryStatus
    timestamp: str
    message: str | None = None


class ArchiveOrderRequest(BaseModel):
    """Request body for POST /order-archive."""

    aoi: str = Field(description="WKT area of interest")
    archive_id: str = Field(alias="archiveId")
    delivery_driver: DeliveryDriver = Field(DeliveryDriver.NONE, alias="deliveryDriver")
    delivery_params: dict[str, Any] | None = Field(None, alias="deliveryParams")
    label: str = Field("Platform Order")
    order_label: str = Field("Platform Order", alias="orderLabel")
    metadata: dict[str, Any] | None = None
    webhook_url: str | None = Field(None, alias="webhookUrl")

    model_config = {"populate_by_name": True}


class ArchiveOrderResponse(BaseModel):
    """Response from creating an archive order."""

    aoi: str
    archive_id: str = Field(alias="archiveId")
    id: str
    order_type: OrderType = Field(alias="orderType")
    order_cost: int = Field(alias="orderCost", description="Cost in cents")
    owner_id: str = Field(alias="ownerId")
    status: DeliveryStatus
    aoi_sq_km: float = Field(alias="aoiSqkm")
    tiles_url: str | None = Field(None, alias="tilesUrl")
    download_image_url: str | None = Field(None, alias="downloadImageUrl")
    download_payload_url: str | None = Field(None, alias="downloadPayloadUrl")
    download_cog_url: str | None = Field(None, alias="downloadCogUrl")
    payload_size: int | None = Field(None, alias="payloadSize")
    cog_size: int | None = Field(None, alias="cogSize")
    order_code: str = Field(alias="orderCode")
    geocode_location: str | None = Field(None, alias="geocodeLocation")
    created_at: str = Field(alias="createdAt")
    order_id: str = Field(alias="orderId")
    item_id: str = Field(alias="itemId")
    deliverable_id: str | None = Field(None, alias="deliverableId")
    delivery_driver: DeliveryDriver | None = Field(None, alias="deliveryDriver")
    delivery_params: dict[str, Any] | None = Field(None, alias="deliveryParams")
    label: str | None = None
    order_label: str | None = Field(None, alias="orderLabel")
    metadata: dict[str, Any] | None = None
    webhook_url: str | None = Field(None, alias="webhookUrl")
    archive: Archive | None = None

    model_config = {"populate_by_name": True}


class TaskingOrderRequest(BaseModel):
    """Request body for POST /order-tasking."""

    aoi: str = Field(description="WKT area of interest")
    window_start: str = Field(alias="windowStart", description="ISO datetime")
    window_end: str = Field(alias="windowEnd", description="ISO datetime")
    product_type: ProductType = Field(alias="productType")
    resolution: str
    delivery_driver: DeliveryDriver = Field(DeliveryDriver.NONE, alias="deliveryDriver")
    delivery_params: dict[str, Any] | None = Field(None, alias="deliveryParams")
    label: str = Field("Platform Order")
    order_label: str = Field("Platform Order", alias="orderLabel")
    metadata: dict[str, Any] | None = None
    webhook_url: str | None = Field(None, alias="webhookUrl")
    priority_item: bool | None = Field(False, alias="priorityItem")
    max_cloud_coverage_percent: int | None = Field(20, alias="maxCloudCoveragePercent", ge=0, le=100)
    max_off_nadir_angle: int | None = Field(30, alias="maxOffNadirAngle", ge=0, le=45)
    required_provider: ApiProvider | None = Field(None, alias="requiredProvider")
    # SAR-specific optional parameters
    sar_product_types: list[SarProductType] | None = Field(None, alias="sarProductTypes")
    sar_polarisation: SarPolarisation | None = Field(None, alias="sarPolarisation")
    sar_grazing_angle_min: float | None = Field(None, alias="sarGrazingAngleMin", ge=10, le=80)
    sar_grazing_angle_max: float | None = Field(None, alias="sarGrazingAngleMax", ge=10, le=80)
    sar_azimuth_angle_min: float | None = Field(None, alias="sarAzimuthAngleMin", ge=0, le=360)
    sar_azimuth_angle_max: float | None = Field(None, alias="sarAzimuthAngleMax", ge=0, le=360)
    sar_number_of_looks: int | None = Field(None, alias="sarNumberOfLooks")
    provider_window_id: str | None = Field(None, alias="providerWindowId")

    model_config = {"populate_by_name": True}


class TaskingOrderResponse(BaseModel):
    """Response from creating a tasking order."""

    aoi: str
    window_start: str = Field(alias="windowStart")
    window_end: str = Field(alias="windowEnd")
    product_type: ProductType = Field(alias="productType")
    resolution: str
    id: str
    order_type: OrderType = Field(alias="orderType")
    order_cost: int = Field(alias="orderCost", description="Cost in cents")
    owner_id: str = Field(alias="ownerId")
    status: DeliveryStatus
    aoi_sq_km: float = Field(alias="aoiSqkm")
    tiles_url: str | None = Field(None, alias="tilesUrl")
    download_image_url: str | None = Field(None, alias="downloadImageUrl")
    download_payload_url: str | None = Field(None, alias="downloadPayloadUrl")
    download_cog_url: str | None = Field(None, alias="downloadCogUrl")
    payload_size: int | None = Field(None, alias="payloadSize")
    cog_size: int | None = Field(None, alias="cogSize")
    order_code: str = Field(alias="orderCode")
    geocode_location: str | None = Field(None, alias="geocodeLocation")
    created_at: str = Field(alias="createdAt")
    order_id: str = Field(alias="orderId")
    item_id: str = Field(alias="itemId")
    deliverable_id: str | None = Field(None, alias="deliverableId")
    delivery_driver: DeliveryDriver | None = Field(None, alias="deliveryDriver")
    delivery_params: dict[str, Any] | None = Field(None, alias="deliveryParams")
    label: str | None = None
    order_label: str | None = Field(None, alias="orderLabel")
    metadata: dict[str, Any] | None = None
    webhook_url: str | None = Field(None, alias="webhookUrl")
    priority_item: bool | None = Field(False, alias="priorityItem")
    max_cloud_coverage_percent: int | None = Field(None, alias="maxCloudCoveragePercent")
    max_off_nadir_angle: int | None = Field(None, alias="maxOffNadirAngle")
    required_provider: ApiProvider | None = Field(None, alias="requiredProvider")

    model_config = {"populate_by_name": True}


class OrderInfoWithEvent(BaseModel):
    """Order info combined with its latest event (used in order list)."""

    order_info: ArchiveOrderResponse | TaskingOrderResponse = Field(alias="orderInfo")
    event: DeliveryEventInfo

    model_config = {"populate_by_name": True}


class ListOrdersResponse(BaseModel):
    """Response from GET /orders."""

    request: dict[str, Any]
    total: int
    orders: list[OrderInfoWithEvent]


class ArchiveOrderInfoResponse(ArchiveOrderResponse):
    """Detailed archive order with event history."""

    events: list[DeliveryEventInfo] = []


class TaskingOrderInfoResponse(TaskingOrderResponse):
    """Detailed tasking order with event history."""

    events: list[DeliveryEventInfo] = []


class OrderRedeliveryRequest(BaseModel):
    """Request body for POST /orders/{id}/redelivery."""

    delivery_driver: DeliveryDriver = Field(alias="deliveryDriver")
    delivery_params: dict[str, Any] = Field(alias="deliveryParams")

    model_config = {"populate_by_name": True}


# ── Feasibility Models ──────────────────────────────────────────────────────────


class CloudCoverage(BaseModel):
    """Daily cloud coverage forecast."""

    date: str
    cloud_coverage: float = Field(alias="cloudCoverage")

    model_config = {"populate_by_name": True}


class WeatherDetails(BaseModel):
    """Weather forecast details."""

    weather_score: float = Field(alias="weatherScore")
    clouds: list[CloudCoverage] | None = None


class WeatherScore(BaseModel):
    """Weather component of feasibility score."""

    weather_score: float = Field(alias="weatherScore")
    weather_details: WeatherDetails | None = Field(None, alias="weatherDetails")

    model_config = {"populate_by_name": True}


class Opportunity(BaseModel):
    """A satellite capture opportunity window."""

    window_start: str = Field(alias="windowStart")
    window_end: str = Field(alias="windowEnd")
    satellite_id: str | None = Field(None, alias="satelliteId")
    provider_window_id: str | None = Field(None, alias="providerWindowId")
    provider_metadata: dict[str, Any] = Field(default_factory=dict, alias="providerMetadata")

    model_config = {"populate_by_name": True}


class ProviderScore(BaseModel):
    """Feasibility score from a specific provider."""

    provider: str | None = None
    score: float
    status: FeasibilityCheckStatus | None = None
    reference: str | None = None
    opportunities: list[Opportunity] = []


class ProviderCombinedScore(BaseModel):
    """Combined feasibility score across providers."""

    score: float
    provider_scores: list[ProviderScore] | None = Field(None, alias="providerScores")

    model_config = {"populate_by_name": True}


class FeasibilityScore(BaseModel):
    """Overall feasibility assessment."""

    feasibility: float
    weather_score: WeatherScore | None = Field(None, alias="weatherScore")
    provider_score: ProviderCombinedScore | None = Field(None, alias="providerScore")

    model_config = {"populate_by_name": True}


class FeasibilityRequest(BaseModel):
    """Request body for POST /feasibility."""

    aoi: str = Field(description="WKT area of interest")
    product_type: ProductType = Field(alias="productType")
    resolution: str
    start_date: str = Field(alias="startDate", description="ISO datetime with timezone")
    end_date: str = Field(alias="endDate", description="ISO datetime with timezone")
    max_cloud_coverage_percent: float | None = Field(None, alias="maxCloudCoveragePercent")
    priority_item: bool | None = Field(None, alias="priorityItem")
    required_provider: str | None = Field(None, alias="requiredProvider")
    sar_parameters: dict[str, Any] = Field(default_factory=dict, alias="sarParameters")

    model_config = {"populate_by_name": True}


class FeasibilityResponse(BaseModel):
    """Response from POST /feasibility."""

    id: str
    valid_until: str = Field(alias="validUntil")
    overall_score: FeasibilityScore | None = Field(None, alias="overallScore")

    model_config = {"populate_by_name": True}


# ── Pass Prediction Models ──────────────────────────────────────────────────────


class PlatformPass(BaseModel):
    """A single satellite pass prediction."""

    provider: ApiProvider
    sat_name: str = Field(alias="satname")
    sat_id: str = Field(alias="satid")
    norad_id: str = Field(alias="noradid")
    node: str
    product_type: ProductType = Field(alias="productType")
    resolution: str
    lat: float
    lon: float
    pass_date: str = Field(alias="passDate")
    mean_t: int = Field(alias="meanT")
    off_nadir_angle: float = Field(alias="offNadirAngle")
    solar_elevation_angle: float = Field(alias="solarElevationAngle")
    min_sq_km: float = Field(alias="minSquareKms")
    max_sq_km: float = Field(alias="maxSquareKms")
    price_per_sq_km: float = Field(alias="priceForOneSquareKm")
    price_per_sq_km_cents: int | None = Field(None, alias="priceForOneSquareKmCents")
    gsd_deg_min: float = Field(alias="gsdDegMin")
    gsd_deg_max: float = Field(alias="gsdDegMax")

    model_config = {"populate_by_name": True}


class PassPredictionRequest(BaseModel):
    """Request body for POST /feasibility/pass-prediction."""

    aoi: str = Field(description="WKT area of interest")
    from_date: str = Field(alias="fromDate", description="ISO datetime with timezone")
    to_date: str = Field(alias="toDate", description="ISO datetime with timezone")
    product_types: list[ProductType] | None = Field(None, alias="productTypes")
    resolutions: list[ResolutionLevel] | None = None
    max_off_nadir_angle: float | None = Field(30, alias="maxOffNadirAngle")

    model_config = {"populate_by_name": True}


class PassPredictionResponse(BaseModel):
    """Response from POST /feasibility/pass-prediction."""

    passes: list[PlatformPass]


# ── Notification Models ─────────────────────────────────────────────────────────


class NotificationRequest(BaseModel):
    """Request body for POST /notifications."""

    aoi: str = Field(description="WKT area of interest")
    gsd_min: int | None = Field(None, alias="gsdMin")
    gsd_max: int | None = Field(None, alias="gsdMax")
    product_type: ProductType | None = Field(None, alias="productType")
    webhook_url: str = Field(alias="webhookUrl")

    model_config = {"populate_by_name": True}


class NotificationResponse(BaseModel):
    """Response from creating/listing a notification."""

    id: str
    owner_id: str = Field(alias="ownerId")
    aoi: str
    gsd_min: int | None = Field(None, alias="gsdMin")
    gsd_max: int | None = Field(None, alias="gsdMax")
    product_type: ProductType | None = Field(None, alias="productType")
    webhook_url: str = Field(alias="webhookUrl")
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class NotificationEvent(BaseModel):
    """A single notification trigger event."""

    model_config = {"extra": "allow"}


class NotificationWithHistoryResponse(NotificationResponse):
    """Notification with its trigger history."""

    history: list[NotificationEvent] = []


class ListNotificationsResponse(BaseModel):
    """Response from GET /notifications."""

    request: dict[str, Any]
    total: int
    notifications: list[NotificationResponse]


# ── Pricing Models ──────────────────────────────────────────────────────────────


class PricingRequest(BaseModel):
    """Request body for POST /pricing."""

    aoi: str | None = Field(None, description="Optional WKT area of interest")


# ── Auth / Utility Models ───────────────────────────────────────────────────────


class WhoamiUser(BaseModel):
    """Current user profile with budget information."""

    id: str
    organization_id: str | None = Field(None, alias="organizationId")
    email: str
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    is_demo_account: bool = Field(True, alias="isDemoAccount")
    current_budget_usage: int = Field(alias="currentBudgetUsage", description="In cents")
    budget_amount: int = Field(alias="budgetAmount", description="In cents")
    has_valid_shared_card: bool = Field(alias="hasValidSharedCard")

    model_config = {"populate_by_name": True}


class StatusResponse(BaseModel):
    """Generic status response."""

    status: str


class PongResponse(BaseModel):
    """Response from ping endpoint."""

    message: str
