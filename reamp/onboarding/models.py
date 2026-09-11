"""
REGENOVA Onboarding Data Models.
Standardized dataclasses for user, facility (site), and device (asset) onboarding.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import datetime
from reamp.security.models import SecurityRole, Permission
from reamp.mvp.models import TechnologyType, AssetStatus


@dataclass
class UserRecord:
    """Registered platform user with role-based access control."""
    user_id: str
    name: str
    email: str
    role: SecurityRole
    tenant_id: str
    status: str = "ACTIVE"
    token: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    permissions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FacilityOnboardingRequest:
    """Request payload to onboard a new renewable energy generation plant / site."""
    facility_id: str
    name: str
    portfolio_id: str
    technology: TechnologyType
    latitude: float
    longitude: float
    rated_capacity_mw: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceOnboardingRequest:
    """Request payload to onboard a new renewable energy device / asset."""
    device_id: str
    facility_id: str
    name: str
    asset_type: str  # "INVERTER", "WIND_TURBINE", "BESS_CONTAINER", "WEATHER_STATION", etc.
    model: str
    rated_power_kw: float
    device_secret: Optional[str] = None
    provision_digital_twin: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OnboardingResult:
    """Standardized response from onboarding operations."""
    status: str  # "SUCCESS" or "ERROR"
    entity_id: str
    entity_type: str  # "USER", "FACILITY", "DEVICE"
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
