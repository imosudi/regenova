"""
REAMP Base Protocol Adapter Interface.
Defines abstract contract for industrial protocol integration.
"""

from abc import ABC, abstractmethod
from typing import List, Any
from reamp.edge.models import TelemetryObservation


class BaseProtocolAdapter(ABC):
    """Abstract base class for all field protocol adapters."""

    def __init__(self, name: str, tenant_id: str, site_id: str):
        self.name = name
        self.tenant_id = tenant_id
        self.site_id = site_id
        self._connected = False

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to field device / bus."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Terminate field connection."""
        pass

    @property
    def is_connected(self) -> bool:
        """Return True if active link exists to field hardware."""
        return self._connected

    @abstractmethod
    def poll(self) -> List[TelemetryObservation]:
        """Poll field device and return normalized canonical observations."""
        pass

    @abstractmethod
    def normalize(self, raw_payload: Any) -> List[TelemetryObservation]:
        """Convert raw protocol bytes / frames / JSON into canonical TelemetryObservation objects."""
        pass
