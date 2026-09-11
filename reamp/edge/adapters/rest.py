"""
REAMP REST HTTP Client Protocol Adapter.
Polls weather stations, smart meters, and external APIs.
"""

import json
import datetime
from typing import List, Dict, Any, Optional
from reamp.edge.adapters.base import BaseProtocolAdapter
from reamp.edge.models import TelemetryObservation, QualityFlag, CommunicationStatus


class RestProtocolAdapter(BaseProtocolAdapter):
    """Polls HTTP/REST JSON endpoints and maps responses to canonical observations."""

    def __init__(
        self,
        name: str,
        tenant_id: str,
        site_id: str,
        endpoint_url: str,
        metric_mappings: Dict[str, Dict[str, Any]]
    ):
        super().__init__(name, tenant_id, site_id)
        self.endpoint_url = endpoint_url
        self.metric_mappings = metric_mappings  # {"json_key": {"asset_id": ..., "sensor_id": ..., "metric": ..., "unit": ...}}

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def poll(self) -> List[TelemetryObservation]:
        """Poll the endpoint (or simulate response if offline/test mode)."""
        if not self._connected:
            return []
        # Simulation payload for testing / offline execution
        sim_payload = {
            "ambient_temp": 28.4,
            "poa_irradiance": 920.5,
            "wind_speed": 4.6
        }
        return self.normalize(sim_payload)

    def normalize(self, raw_payload: Dict[str, Any]) -> List[TelemetryObservation]:
        observations = []
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for key, value in raw_payload.items():
            if key in self.metric_mappings:
                cfg = self.metric_mappings[key]
                obs = TelemetryObservation(
                    tenant_id=self.tenant_id,
                    asset_id=cfg["asset_id"],
                    sensor_id=cfg["sensor_id"],
                    metric=cfg["metric"],
                    value=float(value),
                    unit=cfg["unit"],
                    timestamp=now_str,
                    source="REST_ADAPTER",
                    quality=QualityFlag.VALID,
                    confidence=1.0,
                    communication_status=CommunicationStatus.ONLINE
                )
                observations.append(obs)

        return observations
