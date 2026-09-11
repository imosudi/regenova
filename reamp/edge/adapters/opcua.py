"""
REAMP OPC UA Protocol Adapter.
Maps OPC UA NodeId address spaces to canonical telemetry observations.
"""

import datetime
from typing import List, Dict, Any, Optional
from reamp.edge.adapters.base import BaseProtocolAdapter
from reamp.edge.models import TelemetryObservation, QualityFlag, CommunicationStatus


class OpcUaNodeMapping:
    def __init__(
        self,
        node_id: str,
        asset_id: str,
        sensor_id: str,
        metric: str,
        unit: str,
        scale_factor: float = 1.0
    ):
        self.node_id = node_id
        self.asset_id = asset_id
        self.sensor_id = sensor_id
        self.metric = metric
        self.unit = unit
        self.scale_factor = scale_factor


class OpcUaProtocolAdapter(BaseProtocolAdapter):
    """Subscribes to OPC UA NodeIds and converts data change notifications into observations."""

    def __init__(
        self,
        name: str,
        tenant_id: str,
        site_id: str,
        endpoint_url: str,
        mappings: Optional[List[OpcUaNodeMapping]] = None
    ):
        super().__init__(name, tenant_id, site_id)
        self.endpoint_url = endpoint_url
        self.mappings = mappings or []

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def poll(self) -> List[TelemetryObservation]:
        """Poll nodes (simulated in test/offline environment)."""
        if not self._connected:
            return []
        sim_node_values = {
            "ns=2;s=Turbine.Nacelle.WindSpeed": 12.8,
            "ns=2;s=Turbine.Gearbox.BearingVibrationRMS": 2.45
        }
        return self.normalize(sim_node_values)

    def normalize(self, raw_node_dict: Dict[str, Any]) -> List[TelemetryObservation]:
        observations = []
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for m in self.mappings:
            if m.node_id in raw_node_dict:
                raw_val = float(raw_node_dict[m.node_id])
                phys_val = round(raw_val * m.scale_factor, 4)
                obs = TelemetryObservation(
                    tenant_id=self.tenant_id,
                    asset_id=m.asset_id,
                    sensor_id=m.sensor_id,
                    metric=m.metric,
                    value=phys_val,
                    unit=m.unit,
                    timestamp=now_str,
                    source="OPCUA_ADAPTER",
                    quality=QualityFlag.VALID,
                    confidence=1.0,
                    communication_status=CommunicationStatus.ONLINE
                )
                observations.append(obs)

        return observations
