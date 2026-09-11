"""
REAMP Edge Gateway Main Orchestrator.
Coordinates industrial protocol adapters, local validation, SQLite buffering,
burst-mode overrides, and cloud backfill synchronization.
"""

import json
import datetime
from typing import List, Dict, Any, Optional, Callable
from reamp.edge.models import TelemetryObservation, SensorConfig, EdgeAlert, QualityFlag, CommunicationStatus
from reamp.edge.config import EdgeConfig
from reamp.edge.buffer import SQLiteEdgeBuffer
from reamp.edge.pipeline import ValidationEngine, AggregationEngine
from reamp.edge.adapters.base import BaseProtocolAdapter


class EdgeGateway:
    """Core runtime engine for REAMP Edge Agent."""

    def __init__(self, config: Optional[EdgeConfig] = None):
        self.config = config or EdgeConfig()
        self.buffer = SQLiteEdgeBuffer(self.config.db_path)
        self.validator = ValidationEngine()
        self.aggregator = AggregationEngine(
            window_sec=self.config.aggregation_window_sec,
            burst_cooldown_sec=self.config.burst_cooldown_sec
        )
        self.adapters: List[BaseProtocolAdapter] = []
        self.active_alerts: List[EdgeAlert] = []
        self.is_wan_online: bool = True
        self.cloud_transmit_callback: Optional[Callable[[List[Dict[str, Any]]], bool]] = None

    def register_adapter(self, adapter: BaseProtocolAdapter):
        """Register and connect a field protocol adapter."""
        self.adapters.append(adapter)
        adapter.connect()

    def register_sensor(self, sensor_cfg: SensorConfig):
        """Register sensor boundaries and alert limits."""
        self.validator.register_sensor(sensor_cfg)

    def ingest(self, obs: TelemetryObservation) -> Dict[str, Any]:
        """Ingest a single observation through validation, alerting, and buffering."""
        # 1. Validate observation
        validated_obs, alert = self.validator.validate(obs)
        if alert:
            self.active_alerts.append(alert)
            self.aggregator.trigger_burst_mode()

        # 2. Assign communication status based on current WAN link
        if not self.is_wan_online:
            validated_obs.communication_status = CommunicationStatus.BUFFERED

        # 3. Process through aggregation or burst engine
        emitted_obs_list = self.aggregator.process_observation(validated_obs)

        # 4. If nothing emitted (accumulating in tumbling window), buffer the raw observation as insurance
        records_to_buffer = emitted_obs_list if emitted_obs_list else [validated_obs]

        # 5. Insert into SQLite store-and-forward queue
        seq_id = 0
        for r in records_to_buffer:
            seq_id = self.buffer.insert(r)

        return {
            "status": "INGESTED",
            "quality": validated_obs.quality.value,
            "confidence": validated_obs.confidence,
            "alert_triggered": alert is not None,
            "buffered_seq_id": seq_id
        }

    def simulate_wan_disconnect(self):
        """Simulate physical WAN network dropout (cellular or satellite loss)."""
        self.is_wan_online = False

    def simulate_wan_reconnect(self):
        """Simulate network link restoration."""
        self.is_wan_online = True

    def synchronize_with_cloud(self, batch_size: Optional[int] = None) -> int:
        """Extract unacknowledged records in FIFO order and stream them to central cloud."""
        if not self.is_wan_online:
            return 0  # Cannot synchronize while WAN is offline

        limit = batch_size or self.config.batch_size
        unacked = self.buffer.get_unacknowledged_batch(limit=limit)
        if not unacked:
            return 0

        # Transmit via callback or mock sender
        success = True
        if self.cloud_transmit_callback:
            success = self.cloud_transmit_callback(unacked)

        if success:
            highest_seq = max(r["sequence_id"] for r in unacked)
            acked_count = self.buffer.acknowledge_batch(highest_seq)
            return acked_count

        return 0

    def get_status(self) -> Dict[str, Any]:
        """Return diagnostic health and queue statistics."""
        return {
            "gateway_id": self.config.gateway_id,
            "wan_online": self.is_wan_online,
            "backlog_records": self.buffer.get_backlog_count(),
            "total_records_logged": self.buffer.get_total_count(),
            "active_alerts_count": len(self.active_alerts),
            "burst_mode_active": self.aggregator.burst_mode_active,
            "adapters_count": len(self.adapters)
        }

    def shutdown(self):
        """Gracefully disconnect adapters and close SQLite handle."""
        for a in self.adapters:
            a.disconnect()
        self.buffer.close()
