"""Unit tests for Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from skyfi_mcp.api.models import (
    ApiProvider,
    Archive,
    ArchiveOrderRequest,
    DeliveryDriver,
    DeliveryStatus,
    FeasibilityRequest,
    GetArchivesRequest,
    NotificationRequest,
    ProductType,
    TaskingOrderRequest,
    WhoamiUser,
)


class TestArchiveModel:
    """Tests for Archive model validation."""

    def test_archive_with_all_fields(self):
        """Test Archive model with all fields populated."""
        data = {
            "archiveId": "arch-123",
            "provider": "SIWEI",
            "constellation": "SIWEI-1",
            "productType": "DAY",
            "platformResolution": 1.5,
            "resolution": "1.5m",
            "captureTimestamp": "2025-03-14T10:30:00Z",
            "cloudCoveragePercent": 5.2,
            "offNadirAngle": 15.0,
            "footprint": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "minSqKm": 10.0,
            "maxSqKm": 100.0,
            "priceForOneSquareKm": 50.0,
            "priceForOneSquareKmCents": 5000,
            "priceFullScene": 2500.0,
            "openData": False,
            "totalAreaSquareKm": 50.0,
            "deliveryTimeHours": 24.0,
            "gsd": 1.5,
            "thumbnailUrls": {"small": "https://example.com/thumb.jpg"},
            "tilesUrl": "https://example.com/tiles/{z}/{x}/{y}.png",
        }
        archive = Archive(**data)
        assert archive.archive_id == "arch-123"
        assert archive.provider == ApiProvider.SIWEI
        assert archive.product_type == ProductType.DAY
        assert archive.cloud_coverage_percent == 5.2
        assert archive.off_nadir_angle == 15.0

    def test_archive_with_minimal_fields(self):
        """Test Archive model with required fields only."""
        data = {
            "archiveId": "arch-456",
            "provider": "PLANET",
            "constellation": "PLANET-SCOPE",
            "productType": "NIGHT",
            "platformResolution": 3.0,
            "resolution": "3m",
            "captureTimestamp": "2025-03-13T22:00:00Z",
            "footprint": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "minSqKm": 5.0,
            "maxSqKm": 50.0,
            "priceForOneSquareKm": 25.0,
            "priceForOneSquareKmCents": 2500,
            "priceFullScene": 1000.0,
            "totalAreaSquareKm": 25.0,
            "gsd": 3.0,
        }
        archive = Archive(**data)
        assert archive.archive_id == "arch-456"
        assert archive.cloud_coverage_percent is None
        assert archive.off_nadir_angle is None
        assert archive.delivery_time_hours == 12  # Default value

    def test_archive_enum_validation(self):
        """Test Archive validates enum values correctly."""
        data = {
            "archiveId": "arch-789",
            "provider": "INVALID_PROVIDER",
            "constellation": "TEST",
            "productType": "DAY",
            "platformResolution": 1.5,
            "resolution": "1.5m",
            "captureTimestamp": "2025-03-14T10:30:00Z",
            "footprint": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "minSqKm": 10.0,
            "maxSqKm": 100.0,
            "priceForOneSquareKm": 50.0,
            "priceForOneSquareKmCents": 5000,
            "priceFullScene": 2500.0,
            "totalAreaSquareKm": 50.0,
            "gsd": 1.5,
        }
        with pytest.raises(ValidationError):
            Archive(**data)

    def test_archive_serialize_with_alias(self):
        """Test Archive serialization uses aliases correctly."""
        data = {
            "archiveId": "arch-999",
            "provider": "UMBRA",
            "constellation": "UMBRA-SAR",
            "productType": "SAR",
            "platformResolution": 0.3,
            "resolution": "0.3m",
            "captureTimestamp": "2025-03-14T15:00:00Z",
            "footprint": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "minSqKm": 1.0,
            "maxSqKm": 10.0,
            "priceForOneSquareKm": 100.0,
            "priceForOneSquareKmCents": 10000,
            "priceFullScene": 500.0,
            "totalAreaSquareKm": 5.0,
            "gsd": 0.3,
        }
        archive = Archive(**data)
        dumped = archive.model_dump(by_alias=True)
        assert "archiveId" in dumped
        assert "offNadirAngle" in dumped or "off_nadir_angle" in dumped or archive.off_nadir_angle is None


class TestGetArchivesRequest:
    """Tests for GetArchivesRequest model serialization."""

    def test_get_archives_request_with_aliases(self):
        """Test GetArchivesRequest respects alias names in input."""
        data = {
            "aoi": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "fromDate": "2025-01-01T00:00:00Z",
            "toDate": "2025-03-14T23:59:59Z",
            "maxCloudCoveragePercent": 50.0,
            "maxOffNadirAngle": 25.0,
            "productTypes": ["DAY", "NIGHT"],
            "pageSize": 50,
        }
        req = GetArchivesRequest(**data)
        assert req.aoi == "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        assert req.from_date == "2025-01-01T00:00:00Z"
        assert req.to_date == "2025-03-14T23:59:59Z"
        assert req.max_cloud_coverage_percent == 50.0
        assert req.page_size == 50

    def test_get_archives_request_cloud_coverage_validation(self):
        """Test cloud coverage percentage is validated (0-100)."""
        data = {
            "aoi": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "maxCloudCoveragePercent": 150.0,  # Invalid: > 100
        }
        with pytest.raises(ValidationError) as exc_info:
            GetArchivesRequest(**data)
        assert "less than or equal to 100" in str(exc_info.value)

    def test_get_archives_request_off_nadir_validation(self):
        """Test off-nadir angle is validated (0-50)."""
        data = {
            "aoi": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "maxOffNadirAngle": 60.0,  # Invalid: > 50
        }
        with pytest.raises(ValidationError) as exc_info:
            GetArchivesRequest(**data)
        assert "less than or equal to 50" in str(exc_info.value)

    def test_get_archives_request_minimal(self):
        """Test GetArchivesRequest with only required field."""
        data = {"aoi": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"}
        req = GetArchivesRequest(**data)
        assert req.aoi == "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        assert req.from_date is None
        assert req.page_size == 100  # Default


class TestArchiveOrderRequest:
    """Tests for ArchiveOrderRequest model serialization."""

    def test_archive_order_request_full(self):
        """Test ArchiveOrderRequest with all fields."""
        data = {
            "aoi": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "archiveId": "arch-123",
            "deliveryDriver": "S3",
            "deliveryParams": {"bucket": "my-bucket", "prefix": "imagery/"},
            "label": "Test Order",
            "orderLabel": "Priority Imagery",
            "metadata": {"project": "satellite-analysis"},
            "webhookUrl": "https://example.com/webhook",
        }
        req = ArchiveOrderRequest(**data)
        assert req.aoi == "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        assert req.archive_id == "arch-123"
        assert req.delivery_driver == DeliveryDriver.S3
        assert req.delivery_params == {"bucket": "my-bucket", "prefix": "imagery/"}
        assert req.label == "Test Order"

    def test_archive_order_request_minimal(self):
        """Test ArchiveOrderRequest with minimal required fields."""
        data = {
            "aoi": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "archiveId": "arch-456",
        }
        req = ArchiveOrderRequest(**data)
        assert req.delivery_driver == DeliveryDriver.NONE  # Default
        assert req.label == "Platform Order"  # Default


class TestTaskingOrderRequest:
    """Tests for TaskingOrderRequest model with SAR parameters."""

    def test_tasking_order_request_optical(self):
        """Test TaskingOrderRequest for optical imagery."""
        data = {
            "aoi": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "windowStart": "2025-04-01T00:00:00Z",
            "windowEnd": "2025-04-30T23:59:59Z",
            "productType": "DAY",
            "resolution": "1.5m",
            "deliveryDriver": "GS",
            "maxCloudCoveragePercent": 30,
            "maxOffNadirAngle": 20,
        }
        req = TaskingOrderRequest(**data)
        assert req.product_type == ProductType.DAY
        assert req.resolution == "1.5m"
        assert req.max_cloud_coverage_percent == 30
        assert req.sar_product_types is None

    def test_tasking_order_request_sar(self):
        """Test TaskingOrderRequest with SAR parameters."""
        data = {
            "aoi": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "windowStart": "2025-04-01T00:00:00Z",
            "windowEnd": "2025-04-30T23:59:59Z",
            "productType": "SAR",
            "resolution": "1.0m",
            "sarProductTypes": ["GEC", "SICD"],
            "sarPolarisation": "VV",
            "sarGrazingAngleMin": 20.0,
            "sarGrazingAngleMax": 70.0,
            "sarAzimuthAngleMin": 0.0,
            "sarAzimuthAngleMax": 180.0,
            "sarNumberOfLooks": 4,
        }
        req = TaskingOrderRequest(**data)
        assert req.product_type == ProductType.SAR
        assert req.sar_product_types == ["GEC", "SICD"]
        assert req.sar_polarisation == "VV"
        assert req.sar_grazing_angle_min == 20.0
        assert req.sar_azimuth_angle_max == 180.0

    def test_tasking_order_request_sar_grazing_angle_validation(self):
        """Test SAR grazing angle is validated (10-80)."""
        data = {
            "aoi": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "windowStart": "2025-04-01T00:00:00Z",
            "windowEnd": "2025-04-30T23:59:59Z",
            "productType": "SAR",
            "resolution": "1.0m",
            "sarGrazingAngleMin": 5.0,  # Invalid: < 10
        }
        with pytest.raises(ValidationError) as exc_info:
            TaskingOrderRequest(**data)
        assert "greater than or equal to 10" in str(exc_info.value)

    def test_tasking_order_request_defaults(self):
        """Test TaskingOrderRequest applies correct defaults."""
        data = {
            "aoi": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "windowStart": "2025-04-01T00:00:00Z",
            "windowEnd": "2025-04-30T23:59:59Z",
            "productType": "DAY",
            "resolution": "3m",
        }
        req = TaskingOrderRequest(**data)
        assert req.delivery_driver == DeliveryDriver.NONE
        assert req.label == "Platform Order"
        assert req.max_cloud_coverage_percent == 20
        assert req.max_off_nadir_angle == 30


class TestFeasibilityRequest:
    """Tests for FeasibilityRequest model serialization."""

    def test_feasibility_request_basic(self):
        """Test FeasibilityRequest with basic fields."""
        data = {
            "aoi": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "productType": "DAY",
            "resolution": "1.5m",
            "startDate": "2025-03-14T00:00:00Z",
            "endDate": "2025-04-14T23:59:59Z",
        }
        req = FeasibilityRequest(**data)
        assert req.aoi == "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        assert req.product_type == ProductType.DAY
        assert req.start_date == "2025-03-14T00:00:00Z"
        assert req.sar_parameters == {}

    def test_feasibility_request_with_sar_parameters(self):
        """Test FeasibilityRequest with SAR parameters."""
        data = {
            "aoi": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "productType": "SAR",
            "resolution": "1.0m",
            "startDate": "2025-03-14T00:00:00Z",
            "endDate": "2025-04-14T23:59:59Z",
            "sarParameters": {
                "productTypes": ["GEC"],
                "polarisation": "VV",
                "grazingAngleMin": 20.0,
                "grazingAngleMax": 70.0,
            },
        }
        req = FeasibilityRequest(**data)
        assert req.product_type == ProductType.SAR
        assert "productTypes" in req.sar_parameters
        assert req.sar_parameters["polarisation"] == "VV"

    def test_feasibility_request_with_priority_and_cloud(self):
        """Test FeasibilityRequest with optional fields."""
        data = {
            "aoi": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "productType": "NIGHT",
            "resolution": "0.5m",
            "startDate": "2025-03-14T00:00:00Z",
            "endDate": "2025-04-14T23:59:59Z",
            "maxCloudCoveragePercent": 25.0,
            "priorityItem": True,
            "requiredProvider": "UMBRA",
        }
        req = FeasibilityRequest(**data)
        assert req.max_cloud_coverage_percent == 25.0
        assert req.priority_item is True
        assert req.required_provider == "UMBRA"


class TestNotificationRequest:
    """Tests for NotificationRequest model serialization."""

    def test_notification_request_minimal(self):
        """Test NotificationRequest with required fields."""
        data = {
            "aoi": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "webhookUrl": "https://example.com/notifications",
        }
        req = NotificationRequest(**data)
        assert req.aoi == "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"
        assert req.webhook_url == "https://example.com/notifications"
        assert req.gsd_min is None
        assert req.product_type is None

    def test_notification_request_full(self):
        """Test NotificationRequest with all fields."""
        data = {
            "aoi": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            "webhookUrl": "https://example.com/notifications",
            "gsdMin": 1,
            "gsdMax": 3,
            "productType": "DAY",
        }
        req = NotificationRequest(**data)
        assert req.gsd_min == 1
        assert req.gsd_max == 3
        assert req.product_type == ProductType.DAY


class TestWhoamiUser:
    """Tests for WhoamiUser deserialization."""

    def test_whoami_user_full(self):
        """Test WhoamiUser with all fields."""
        data = {
            "id": "user-123",
            "organizationId": "org-456",
            "email": "user@example.com",
            "firstName": "John",
            "lastName": "Doe",
            "isDemoAccount": False,
            "currentBudgetUsage": 50000,  # in cents
            "budgetAmount": 100000,
            "hasValidSharedCard": True,
        }
        user = WhoamiUser(**data)
        assert user.id == "user-123"
        assert user.organization_id == "org-456"
        assert user.email == "user@example.com"
        assert user.is_demo_account is False
        assert user.current_budget_usage == 50000
        assert user.has_valid_shared_card is True

    def test_whoami_user_optional_fields(self):
        """Test WhoamiUser with optional fields as None."""
        data = {
            "id": "user-789",
            "email": "test@example.com",
            "firstName": "Jane",
            "lastName": "Smith",
            "isDemoAccount": True,
            "currentBudgetUsage": 0,
            "budgetAmount": 50000,
            "hasValidSharedCard": False,
        }
        user = WhoamiUser(**data)
        assert user.organization_id is None
        assert user.is_demo_account is True


class TestEnumValues:
    """Tests for all Enum values."""

    def test_api_provider_enum(self):
        """Test all ApiProvider enum values."""
        providers = [
            ApiProvider.SIWEI,
            ApiProvider.SATELLOGIC,
            ApiProvider.UMBRA,
            ApiProvider.GEOSAT,
            ApiProvider.SENTINEL1_CREODIAS,
            ApiProvider.SENTINEL2,
            ApiProvider.SENTINEL2_CREODIAS,
            ApiProvider.PLANET,
            ApiProvider.IMPRO,
            ApiProvider.URBAN_SKY,
            ApiProvider.NSL,
            ApiProvider.VEXCEL,
            ApiProvider.VANTOR,
            ApiProvider.ICEYE_US,
        ]
        assert len(providers) == 14
        assert ApiProvider.SIWEI.value == "SIWEI"
        assert ApiProvider.PLANET.value == "PLANET"

    def test_product_type_enum(self):
        """Test all ProductType enum values."""
        types = [
            ProductType.DAY,
            ProductType.NIGHT,
            ProductType.VIDEO,
            ProductType.SAR,
            ProductType.HYPERSPECTRAL,
            ProductType.MULTISPECTRAL,
            ProductType.STEREO,
            ProductType.BASEMAP,
        ]
        assert len(types) == 8
        assert ProductType.SAR.value == "SAR"

    def test_delivery_status_enum(self):
        """Test all DeliveryStatus enum values."""
        statuses = [
            DeliveryStatus.CREATED,
            DeliveryStatus.STARTED,
            DeliveryStatus.PAYMENT_FAILED,
            DeliveryStatus.PLATFORM_FAILED,
            DeliveryStatus.PROVIDER_PENDING,
            DeliveryStatus.PROVIDER_COMPLETE,
            DeliveryStatus.PROVIDER_FAILED,
            DeliveryStatus.PROCESSING_PENDING,
            DeliveryStatus.PROCESSING_COMPLETE,
            DeliveryStatus.PROCESSING_FAILED,
            DeliveryStatus.DELIVERY_PENDING,
            DeliveryStatus.DELIVERY_COMPLETED,
            DeliveryStatus.DELIVERY_FAILED,
            DeliveryStatus.INTERNAL_IMAGE_PROCESSING_PENDING,
        ]
        assert len(statuses) == 14
        assert DeliveryStatus.DELIVERY_COMPLETED.value == "DELIVERY_COMPLETED"
