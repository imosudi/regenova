"""
REAMP MVP — Unified Domain Models.

Defines the entity hierarchy (Organization -> Portfolio -> Site -> Asset -> Sensor),
as well as alert structures, dashboard state aggregates, and executive report models.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any


class TechnologyType(str, Enum):
    SOLAR_PV = "SOLAR_PV"
    WIND = "WIND"
    BESS = "BESS"
    HYBRID = "HYBRID"


class AssetStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    MAINTENANCE = "MAINTENANCE"
    FAILED = "FAILED"
    OFFLINE = "OFFLINE"


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


@dataclass
class Organization:
    """Top-level multi-tenant enterprise entity."""
    org_id: str
    name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Portfolio:
    """Group of renewable energy sites belonging to an organization."""
    portfolio_id: str
    org_id: str
    name: str
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Site:
    """Individual renewable energy power generation site / plant."""
    site_id: str
    portfolio_id: str
    name: str
    latitude: float
    longitude: float
    rated_capacity_mw: float
    technology: TechnologyType = TechnologyType.SOLAR_PV
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AssetRecord:
    """Registered generation, conversion, or measurement asset."""
    asset_id: str
    site_id: str
    name: str
    asset_type: str  # e.g., "INVERTER", "PYRANOMETER", "TRANSFORMER", "TURBINE"
    model: str
    rated_power_kw: float
    commissioned_date: datetime
    status: AssetStatus = AssetStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SensorRecord:
    """Registered physical or virtual telemetry sensor."""
    sensor_id: str
    asset_id: str
    name: str
    measurement_type: str  # e.g., "POA_IRRADIANCE", "AMBIENT_TEMP", "HEATSINK_TEMP", "DC_POWER", "AC_POWER"
    engineering_unit: str  # e.g., "W/m^2", "degC", "kW", "V", "A"
    min_range: float
    max_range: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertRecord:
    """Real-time operational alarm or incident event."""
    alert_id: str
    site_id: str
    asset_id: str
    severity: AlertSeverity
    title: str
    description: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: AlertStatus = AlertStatus.ACTIVE
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    related_anomaly_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedDashboardState:
    """Consolidated state model for SCADA operator and management dashboards."""
    site_id: str
    site_name: str
    timestamp: datetime
    total_generation_mw: float
    rated_capacity_mw: float
    performance_ratio: float
    site_health_index: float
    active_alerts_count: int
    pending_work_orders_count: int
    assets_summary: Dict[str, Dict[str, Any]]
    active_alerts: List[Dict[str, Any]]
    recent_work_orders: List[Dict[str, Any]]


@dataclass
class ExecutiveReport:
    """Executive operational, financial, and compliance summary."""
    report_id: str
    site_id: str
    site_name: str
    timestamp: datetime
    period_start: datetime
    period_end: datetime
    total_generation_mwh: float
    expected_generation_mwh: float
    performance_ratio: float
    total_revenue_loss_usd: float
    avoided_downtime_savings_usd: float
    critical_incidents_count: int
    open_work_orders_count: int
    audit_chain_valid: bool
    details: Dict[str, Any] = field(default_factory=dict)
