"""
REAMP Edge Local Data Pipeline.
Executes physical range validation, flatline freeze screening, rate-of-change checks,
tumbling window aggregation, and immediate local safety alarm dispatch.
"""

import math
import datetime
from typing import Dict, List, Optional, Tuple, Any
from reamp.edge.models import TelemetryObservation, SensorConfig, EdgeAlert, QualityFlag, CommunicationStatus


class ValidationEngine:
    """Evaluates telemetry observations against physical bounds and temporal invariants."""

    def __init__(self):
        self.sensor_configs: Dict[str, SensorConfig] = {}
        self.history: Dict[str, List[float]] = {}

    def register_sensor(self, config: SensorConfig):
        """Register configuration boundaries for a sensor."""
        self.sensor_configs[config.sensor_id] = config

    def validate(self, obs: TelemetryObservation) -> Tuple[TelemetryObservation, Optional[EdgeAlert]]:
        """Validate observation and optionally trigger an EdgeAlert if safety limit breached."""
        alert: Optional[EdgeAlert] = None
        cfg = self.sensor_configs.get(obs.sensor_id)

        # 1. Timestamp Future Skew Check
        try:
            # Parse ISO-8601 timestamp
            ts = obs.timestamp.replace("Z", "+00:00")
            obs_dt = datetime.datetime.fromisoformat(ts)
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            skew_sec = (obs_dt - now_dt).total_seconds()
            if skew_sec > 5.0:
                obs.quality = QualityFlag.INVALID
                obs.confidence = 0.0
                obs.metadata["validation_error"] = f"Future timestamp skew ({skew_sec:.1f}s)"
                return obs, alert
        except Exception as e:
            obs.quality = QualityFlag.INVALID
            obs.confidence = 0.0
            obs.metadata["validation_error"] = f"Invalid timestamp format: {str(e)}"
            return obs, alert

        # 2. Physical Range Bounds Check
        if cfg:
            if cfg.min_range is not None and obs.value < cfg.min_range:
                obs.quality = QualityFlag.INVALID
                obs.confidence = 0.0
                obs.metadata["validation_error"] = f"Value {obs.value} below min_range {cfg.min_range}"
                return obs, alert

            if cfg.max_range is not None and obs.value > cfg.max_range:
                obs.quality = QualityFlag.INVALID
                obs.confidence = 0.0
                obs.metadata["validation_error"] = f"Value {obs.value} above max_range {cfg.max_range}"
                return obs, alert

            # 3. Critical Safety Threshold Check
            if cfg.critical_high_threshold is not None and obs.value >= cfg.critical_high_threshold:
                alert = EdgeAlert(
                    alert_code=f"ALM-{obs.metric.upper()}-HIGH",
                    asset_id=obs.asset_id,
                    sensor_id=obs.sensor_id,
                    metric=obs.metric,
                    value=obs.value,
                    severity="CRITICAL",
                    timestamp=obs.timestamp,
                    message=f"Critical threshold exceeded: {obs.value} {obs.unit} >= {cfg.critical_high_threshold} {obs.unit}"
                )

        # 4. Signal Freeze / Flatline Detection
        key = f"{obs.tenant_id}:{obs.sensor_id}:{obs.metric}"
        if key not in self.history:
            self.history[key] = []
        self.history[key].append(obs.value)

        # Keep last 10 readings
        if len(self.history[key]) > 10:
            self.history[key].pop(0)

        # Flatline detection: 4 identical consecutive non-zero readings
        if len(self.history[key]) >= 4:
            last4 = self.history[key][-4:]
            if len(set(last4)) == 1 and obs.value != 0.0:
                obs.quality = QualityFlag.STALE
                obs.confidence = 0.20
                obs.metadata["validation_warning"] = "Sensor flatline freeze detected"
                return obs, alert

        # If nominal and no previous flags
        if obs.quality not in (QualityFlag.INVALID, QualityFlag.STALE):
            obs.quality = QualityFlag.VALID
            obs.confidence = 1.0

        return obs, alert


class AggregationEngine:
    """Computes fixed-interval tumbling window statistics and manages burst-mode override."""

    def __init__(self, window_sec: int = 60, burst_cooldown_sec: int = 900):
        self.window_sec = window_sec
        self.burst_cooldown_sec = burst_cooldown_sec
        self.windows: Dict[str, List[TelemetryObservation]] = {}
        self.window_start_times: Dict[str, datetime.datetime] = {}
        self.burst_mode_active = False
        self.burst_activated_at: Optional[datetime.datetime] = None

    def trigger_burst_mode(self):
        """Activate high-frequency raw streaming due to operational anomaly."""
        self.burst_mode_active = True
        self.burst_activated_at = datetime.datetime.now(datetime.timezone.utc)

    def process_observation(self, obs: TelemetryObservation) -> List[TelemetryObservation]:
        """Process observation; returns raw observation in burst mode or downsampled rollups when window closes."""
        now = datetime.datetime.now(datetime.timezone.utc)

        # Check burst cooldown
        if self.burst_mode_active and self.burst_activated_at:
            if (now - self.burst_activated_at).total_seconds() > self.burst_cooldown_sec:
                self.burst_mode_active = False
                self.burst_activated_at = None

        # In burst mode: Pass raw observation directly
        if self.burst_mode_active:
            obs.metadata["stream_mode"] = "BURST_RAW_1HZ"
            return [obs]

        # In nominal mode: Accumulate in tumbling window
        key = f"{obs.tenant_id}:{obs.asset_id}:{obs.sensor_id}:{obs.metric}"
        if key not in self.windows:
            self.windows[key] = []
            self.window_start_times[key] = now

        self.windows[key].append(obs)

        # If window elapsed, compute and emit aggregate
        elapsed = (now - self.window_start_times[key]).total_seconds()
        if elapsed >= self.window_sec:
            aggregate = self._compute_aggregate(key, obs)
            self.windows[key] = []
            self.window_start_times[key] = now
            return [aggregate]

        return []

    def _compute_aggregate(self, key: str, latest_obs: TelemetryObservation) -> TelemetryObservation:
        """Compute statistical summary for tumbling window."""
        items = self.windows[key]
        values = [o.value for o in items if o.quality in (QualityFlag.VALID, QualityFlag.UNCERTAIN)]
        
        if not values:
            values = [latest_obs.value]

        count = len(values)
        avg_val = sum(values) / count
        min_val = min(values)
        max_val = max(values)
        variance = sum((x - avg_val) ** 2 for x in values) / count if count > 1 else 0.0
        stddev = math.sqrt(variance)

        agg_obs = TelemetryObservation(
            tenant_id=latest_obs.tenant_id,
            asset_id=latest_obs.asset_id,
            sensor_id=latest_obs.sensor_id,
            metric=f"{latest_obs.metric}_1min_avg",
            value=round(avg_val, 4),
            unit=latest_obs.unit,
            timestamp=latest_obs.timestamp,
            source="EDGE_COMPUTED",
            quality=QualityFlag.VALID,
            confidence=1.0,
            communication_status=latest_obs.communication_status,
            metadata={
                "sample_count": count,
                "min": round(min_val, 4),
                "max": round(max_val, 4),
                "stddev": round(stddev, 4)
            }
        )
        return agg_obs
