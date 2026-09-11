"""
REAMP Edge Data Models.
Canonical dataclasses and enumerations for edge telemetry observations, sensor configs, and alerts.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any
import datetime


class QualityFlag(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    MISSING = "MISSING"
    STALE = "STALE"
    UNCERTAIN = "UNCERTAIN"


class CommunicationStatus(str, Enum):
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    BUFFERED = "BUFFERED"


@dataclass
class TelemetryObservation:
    """Canonical 10-attribute telemetry observation."""
    tenant_id: str
    asset_id: str
    sensor_id: str
    metric: str
    value: float
    unit: str
    timestamp: str  # ISO-8601 UTC
    source: str = "EDGE_GATEWAY"
    quality: QualityFlag = QualityFlag.VALID
    confidence: float = 1.0
    communication_status: CommunicationStatus = CommunicationStatus.ONLINE
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["quality"] = self.quality.value if isinstance(self.quality, QualityFlag) else self.quality
        d["communication_status"] = (
            self.communication_status.value
            if isinstance(self.communication_status, CommunicationStatus)
            else self.communication_status
        )
        return d


@dataclass
class SensorConfig:
    """Configuration and physical boundary parameters for a monitored sensor."""
    sensor_id: str
    asset_id: str
    metric: str
    unit: str
    min_range: Optional[float] = None
    max_range: Optional[float] = None
    rate_of_change_max: Optional[float] = None
    critical_high_threshold: Optional[float] = None
    sampling_interval_sec: int = 1


@dataclass
class EdgeAlert:
    """Locally detected edge threshold alarm."""
    alert_code: str
    asset_id: str
    sensor_id: str
    metric: str
    value: float
    severity: str  # "WARNING", "CRITICAL", "EMERGENCY"
    timestamp: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
