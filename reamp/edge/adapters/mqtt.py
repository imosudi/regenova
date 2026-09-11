"""
REAMP MQTT Protocol Adapter.
Processes JSON telemetry payloads from MQTT subscription topics.
"""

import json
import datetime
from typing import List, Dict, Any, Optional
from reamp.edge.adapters.base import BaseProtocolAdapter
from reamp.edge.models import TelemetryObservation, QualityFlag, CommunicationStatus


class MqttProtocolAdapter(BaseProtocolAdapter):
    """Subscribes to plant MQTT topics and normalizes message payloads."""

    def __init__(
        self,
        name: str,
        tenant_id: str,
        site_id: str,
        broker_host: str,
        port: int = 8883,
        topic_pattern: str = "reamp/field/+/+/telemetry"
    ):
        super().__init__(name, tenant_id, site_id)
        self.broker_host = broker_host
        self.port = port
        self.topic_pattern = topic_pattern

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def poll(self) -> List[TelemetryObservation]:
        """Poll queued incoming messages (or simulated message in test mode)."""
        if not self._connected:
            return []
        sim_message = {
            "topic": "reamp/field/mojave/tracker/TRK-01/telemetry",
            "payload": {
                "asset_id": "trk-asset-01",
                "sensor_id": "trk-tilt-sens",
                "metric": "tracker_tilt_angle_deg",
                "value": 45.2,
                "unit": "deg",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
        }
        return self.normalize(sim_message)

    def normalize(self, raw_mqtt_message: Dict[str, Any]) -> List[TelemetryObservation]:
        payload = raw_mqtt_message.get("payload", {})
        ts = payload.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat())

        obs = TelemetryObservation(
            tenant_id=self.tenant_id,
            asset_id=payload.get("asset_id", "unknown-asset"),
            sensor_id=payload.get("sensor_id", "unknown-sensor"),
            metric=payload.get("metric", "unknown-metric"),
            value=float(payload.get("value", 0.0)),
            unit=payload.get("unit", ""),
            timestamp=ts,
            source="MQTT_ADAPTER",
            quality=QualityFlag.VALID,
            confidence=1.0,
            communication_status=CommunicationStatus.ONLINE
        )
        return [obs]
