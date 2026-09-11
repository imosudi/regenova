"""
REAMP Level 1 Anomaly Detector: Deterministic Rule-Based Engine.
Sub-second evaluation of hard engineering limits, unexpected shutdowns,
communication timeouts, and impossible physical values.
"""

import uuid
import datetime
from typing import Dict, Any, List, Optional
from reamp.anomaly.models import (
    AnomalyObject,
    AnomalyType,
    AnomalySeverity,
    Level1RuleConfig
)


class Level1RuleDetector:
    """Deterministic rule-based detector for hard safety, state, and physical limits."""

    MODEL_VERSION = "1.0.0-phase8"

    def __init__(self, config: Optional[Level1RuleConfig] = None):
        self.config = config or Level1RuleConfig()

    def evaluate(
        self,
        asset_id: str,
        telemetry: Dict[str, Any],
        timestamp_str: Optional[str] = None
    ) -> List[AnomalyObject]:
        """Evaluate a single telemetry observation against configured rules."""
        anomalies: List[AnomalyObject] = []
        now_str = timestamp_str or datetime.datetime.now(datetime.timezone.utc).isoformat()
        conf = float(telemetry.get("confidence", 1.0))

        # ---------------------------------------------------------------------
        # 1. Impossible Physical Values
        # ---------------------------------------------------------------------
        g_poa = telemetry.get("irradiance_poa_wm2")
        if g_poa is not None:
            if g_poa < self.config.impossible_irradiance_min or g_poa > self.config.impossible_irradiance_max:
                anomalies.append(AnomalyObject(
                    anomaly_id=f"ANOM-L1-{uuid.uuid4().hex[:8]}",
                    asset_id=asset_id,
                    timestamp=now_str,
                    type=AnomalyType.IMPOSSIBLE_VALUE,
                    severity=AnomalySeverity.HIGH,
                    score=1.0,
                    evidence={
                        "parameter": "irradiance_poa_wm2",
                        "observed_value": g_poa,
                        "valid_range": [self.config.impossible_irradiance_min, self.config.impossible_irradiance_max]
                    },
                    confidence=conf,
                    detection_method="LEVEL_1_IMPOSSIBLE_VALUE",
                    model_version=self.MODEL_VERSION,
                    recommended_action="Inspect pyranometer wiring and calibration; sensor reporting physically impossible values."
                ))

        t_cell = telemetry.get("temperature_cell_max_c")
        if t_cell is not None:
            if t_cell < -50.0 or t_cell > 130.0:
                anomalies.append(AnomalyObject(
                    anomaly_id=f"ANOM-L1-{uuid.uuid4().hex[:8]}",
                    asset_id=asset_id,
                    timestamp=now_str,
                    type=AnomalyType.IMPOSSIBLE_VALUE,
                    severity=AnomalySeverity.HIGH,
                    score=1.0,
                    evidence={
                        "parameter": "temperature_cell_max_c",
                        "observed_value": t_cell,
                        "valid_range": [-50.0, 130.0]
                    },
                    confidence=conf,
                    detection_method="LEVEL_1_IMPOSSIBLE_VALUE",
                    model_version=self.MODEL_VERSION,
                    recommended_action="Inspect thermocouple lead wire; open-circuit or short-circuit sensor condition."
                ))

        # ---------------------------------------------------------------------
        # 2. Threshold Violations (Voltage, Temperature, Current)
        # ---------------------------------------------------------------------
        v_ac = telemetry.get("voltage_ac_v")
        if v_ac is not None and v_ac > 0.0:
            if v_ac > self.config.voltage_ac_max_v or v_ac < self.config.voltage_ac_min_v:
                dev = abs(v_ac - 480.0) / 480.0
                sev = AnomalySeverity.CRITICAL if dev > 0.15 else AnomalySeverity.HIGH
                anomalies.append(AnomalyObject(
                    anomaly_id=f"ANOM-L1-{uuid.uuid4().hex[:8]}",
                    asset_id=asset_id,
                    timestamp=now_str,
                    type=AnomalyType.THRESHOLD_VIOLATION,
                    severity=sev,
                    score=min(1.0, dev * 5.0),
                    evidence={
                        "parameter": "voltage_ac_v",
                        "observed_value": v_ac,
                        "limits": [self.config.voltage_ac_min_v, self.config.voltage_ac_max_v]
                    },
                    confidence=conf,
                    detection_method="LEVEL_1_THRESHOLD",
                    model_version=self.MODEL_VERSION,
                    recommended_action="Grid voltage anomaly: check interconnect point tap changers and protective relays."
                ))

        t_hs = telemetry.get("temperature_heatsink_c")
        if t_hs is not None and t_hs > self.config.temp_heatsink_max_c:
            anomalies.append(AnomalyObject(
                anomaly_id=f"ANOM-L1-{uuid.uuid4().hex[:8]}",
                asset_id=asset_id,
                timestamp=now_str,
                type=AnomalyType.THRESHOLD_VIOLATION,
                severity=AnomalySeverity.CRITICAL,
                score=1.0,
                evidence={
                    "parameter": "temperature_heatsink_c",
                    "observed_value": t_hs,
                    "limit": self.config.temp_heatsink_max_c
                },
                confidence=conf,
                detection_method="LEVEL_1_THRESHOLD",
                model_version=self.MODEL_VERSION,
                recommended_action="IGBT thermal overload: check inverter cooling fans and air filters immediately."
            ))

        i_ac = telemetry.get("current_ac_a")
        if i_ac is not None and i_ac > self.config.current_ac_max_a:
            anomalies.append(AnomalyObject(
                anomaly_id=f"ANOM-L1-{uuid.uuid4().hex[:8]}",
                asset_id=asset_id,
                timestamp=now_str,
                type=AnomalyType.THRESHOLD_VIOLATION,
                severity=AnomalySeverity.CRITICAL,
                score=1.0,
                evidence={
                    "parameter": "current_ac_a",
                    "observed_value": i_ac,
                    "limit": self.config.current_ac_max_a
                },
                confidence=conf,
                detection_method="LEVEL_1_THRESHOLD",
                model_version=self.MODEL_VERSION,
                recommended_action="AC overcurrent trip threshold exceeded. Inspect inverter bridge for ground fault."
            ))

        # ---------------------------------------------------------------------
        # 3. Unexpected Shutdown Detection
        # ---------------------------------------------------------------------
        p_act = telemetry.get("actual_power_kw")
        op_state = str(telemetry.get("operating_state", "RUNNING")).upper()
        if p_act is not None and op_state == "RUNNING" and g_poa is not None:
            if g_poa >= self.config.shutdown_min_poa_wm2 and p_act <= self.config.shutdown_max_power_kw:
                anomalies.append(AnomalyObject(
                    anomaly_id=f"ANOM-L1-{uuid.uuid4().hex[:8]}",
                    asset_id=asset_id,
                    timestamp=now_str,
                    type=AnomalyType.UNEXPECTED_SHUTDOWN,
                    severity=AnomalySeverity.CRITICAL,
                    score=1.0,
                    evidence={
                        "operating_state": op_state,
                        "irradiance_poa_wm2": g_poa,
                        "actual_power_kw": p_act,
                        "threshold_poa": self.config.shutdown_min_poa_wm2
                    },
                    confidence=conf,
                    detection_method="LEVEL_1_UNEXPECTED_SHUTDOWN",
                    model_version=self.MODEL_VERSION,
                    recommended_action="Uncommanded generation collapse during high resource potential: check main breaker and protective trip log."
                ))

        # ---------------------------------------------------------------------
        # 4. Communication Timeout Watchdog
        # ---------------------------------------------------------------------
        heartbeat_gap = telemetry.get("heartbeat_gap_seconds")
        is_comm_lost = telemetry.get("communication_lost", False)
        if (heartbeat_gap is not None and heartbeat_gap > self.config.comm_timeout_seconds) or is_comm_lost:
            anomalies.append(AnomalyObject(
                anomaly_id=f"ANOM-L1-{uuid.uuid4().hex[:8]}",
                asset_id=asset_id,
                timestamp=now_str,
                type=AnomalyType.COMMUNICATION_TIMEOUT,
                severity=AnomalySeverity.HIGH,
                score=1.0,
                evidence={
                    "heartbeat_gap_seconds": heartbeat_gap,
                    "timeout_threshold": self.config.comm_timeout_seconds
                },
                confidence=0.50,  # Comms drop lowers data confidence
                detection_method="LEVEL_1_COMMUNICATION_WATCHDOG",
                model_version=self.MODEL_VERSION,
                recommended_action="Telemetry link offline: verify edge gateway network connectivity and switch port status."
            ))

        return anomalies
