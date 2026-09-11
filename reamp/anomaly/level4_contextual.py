"""
REAMP Level 4 Anomaly Detector: Contextual & Multi-Variate Engine.
Evaluates physical relationship residuals (P vs V*I, Thermal vs Power)
and cross-inverter spatial peer outlier detection using robust MAD statistics.
"""

import math
import uuid
import datetime
import numpy as np
from typing import Dict, Any, List, Optional
from reamp.anomaly.models import (
    AnomalyObject,
    AnomalyType,
    AnomalySeverity,
    Level4ContextualConfig
)


class Level4ContextualDetector:
    """Contextual physical residual and spatial peer cohort anomaly detector."""

    MODEL_VERSION = "1.0.0-phase8"

    def __init__(self, config: Optional[Level4ContextualConfig] = None):
        self.config = config or Level4ContextualConfig()

    def evaluate_residuals(
        self,
        asset_id: str,
        telemetry: Dict[str, Any],
        timestamp_str: Optional[str] = None
    ) -> List[AnomalyObject]:
        """Evaluate physical conservation and coupling residuals."""
        anomalies: List[AnomalyObject] = []
        now_str = timestamp_str or datetime.datetime.now(datetime.timezone.utc).isoformat()
        conf = float(telemetry.get("confidence", 1.0))
        p_rated = float(telemetry.get("rated_power_kw", 800.0))

        # ---------------------------------------------------------------------
        # 1. Three-Phase Power Law Residual: P vs sqrt(3) * V * I * PF
        # ---------------------------------------------------------------------
        p_act = telemetry.get("actual_power_kw")
        v_ac = telemetry.get("voltage_ac_v")
        i_ac = telemetry.get("current_ac_a")
        pf = float(telemetry.get("power_factor", 0.99))

        if p_act is not None and v_ac is not None and i_ac is not None:
            p_act_f = float(p_act)
            v_ac_f = float(v_ac)
            i_ac_f = float(i_ac)

            if p_act_f > 10.0:  # Only evaluate under active generating load
                p_calc = (math.sqrt(3.0) * v_ac_f * i_ac_f * pf) / 1000.0
                residual_kw = abs(p_act_f - p_calc)
                norm_residual = residual_kw / p_rated

                if norm_residual > self.config.pvi_residual_threshold:
                    anomalies.append(AnomalyObject(
                        anomaly_id=f"ANOM-L4-PVI-{uuid.uuid4().hex[:8]}",
                        asset_id=asset_id,
                        timestamp=now_str,
                        type=AnomalyType.PHYSICAL_RESIDUAL,
                        severity=AnomalySeverity.HIGH,
                        score=round(min(1.0, norm_residual * 4.0), 3),
                        evidence={
                            "subsystem": "ELECTRICAL_TRANSDUCER",
                            "measured_active_power_kw": round(p_act_f, 2),
                            "calculated_from_vi_kw": round(p_calc, 2),
                            "residual_kw": round(residual_kw, 2),
                            "residual_ratio": round(norm_residual, 4),
                            "threshold": self.config.pvi_residual_threshold
                        },
                        confidence=conf,
                        detection_method="LEVEL_4_PVI_CONSERVATION_LAW",
                        model_version=self.MODEL_VERSION,
                        recommended_action="Electrical transducer inconsistency: Check CT/PT scaling factors or power meter calibration."
                    ))

        # ---------------------------------------------------------------------
        # 2. Heatsink Thermal Coupling Residual: Delta_T vs (P/P_rated)^2
        # ---------------------------------------------------------------------
        t_hs = telemetry.get("temperature_heatsink_c")
        t_amb = telemetry.get("temperature_ambient_c", 25.0)

        if p_act is not None and t_hs is not None and t_amb is not None:
            p_act_f = float(p_act)
            t_hs_f = float(t_hs)
            t_amb_f = float(t_amb)

            if p_act_f > 50.0:
                delta_t_act = t_hs_f - t_amb_f
                # Expected quadratic ohmic heatsink rise
                delta_t_exp = self.config.thermal_k_factor * ((p_act_f / p_rated) ** 2)
                thermal_residual = delta_t_act - delta_t_exp

                if thermal_residual > self.config.thermal_residual_threshold_c:
                    anomalies.append(AnomalyObject(
                        anomaly_id=f"ANOM-L4-THERM-{uuid.uuid4().hex[:8]}",
                        asset_id=asset_id,
                        timestamp=now_str,
                        type=AnomalyType.PHYSICAL_RESIDUAL,
                        severity=AnomalySeverity.HIGH,
                        score=round(min(1.0, thermal_residual / 40.0), 3),
                        evidence={
                            "subsystem": "COOLING_INFRASTRUCTURE",
                            "measured_heatsink_temp_c": round(t_hs_f, 2),
                            "ambient_temp_c": round(t_amb_f, 2),
                            "delta_t_measured": round(delta_t_act, 2),
                            "delta_t_expected": round(delta_t_exp, 2),
                            "thermal_residual_c": round(thermal_residual, 2),
                            "threshold_c": self.config.thermal_residual_threshold_c
                        },
                        confidence=conf,
                        detection_method="LEVEL_4_THERMAL_LOADING_COUPLING",
                        model_version=self.MODEL_VERSION,
                        recommended_action="Thermal cooling degradation: Inverter heatsink temperature excessive for current electrical load. Inspect fan operation."
                    ))

        return anomalies

    def evaluate_cohort_peers(
        self,
        target_asset_id: str,
        cohort_powers: Dict[str, float],
        timestamp_str: Optional[str] = None,
        confidence: float = 1.0
    ) -> List[AnomalyObject]:
        """
        Evaluate cross-inverter spatial peer consistency across an array cohort
        using Boris Iglewicz & David Hoaglin's robust Median Absolute Deviation (MAD).
        """
        now_str = timestamp_str or datetime.datetime.now(datetime.timezone.utc).isoformat()
        if len(cohort_powers) < 3 or target_asset_id not in cohort_powers:
            return []

        values = np.array(list(cohort_powers.values()), dtype=float)
        cohort_median = float(np.median(values))

        # Check if cohort is generating substantial power
        if cohort_median < self.config.peer_min_cohort_power_kw:
            return []

        mad = float(np.median(np.abs(values - cohort_median)))
        effective_mad = max(mad, 0.02 * cohort_median)  # Guard against identical peers

        target_power = float(cohort_powers[target_asset_id])
        # Modified Z-score
        modified_z = 0.6745 * (target_power - cohort_median) / effective_mad

        if modified_z < -self.config.peer_mad_threshold:
            deficit_kw = cohort_median - target_power
            dev_ratio = deficit_kw / cohort_median if cohort_median > 0 else 0.0
            sev = AnomalySeverity.CRITICAL if dev_ratio > 0.40 else AnomalySeverity.HIGH

            return [
                AnomalyObject(
                    anomaly_id=f"ANOM-L4-PEER-{uuid.uuid4().hex[:8]}",
                    asset_id=target_asset_id,
                    timestamp=now_str,
                    type=AnomalyType.PEER_OUTLIER,
                    severity=sev,
                    score=round(min(1.0, abs(modified_z) / 10.0), 3),
                    evidence={
                        "target_power_kw": round(target_power, 2),
                        "cohort_median_power_kw": round(cohort_median, 2),
                        "cohort_mad_kw": round(mad, 2),
                        "modified_z_score": round(modified_z, 2),
                        "deficit_kw": round(deficit_kw, 2),
                        "deficit_percentage": round(dev_ratio * 100.0, 1),
                        "cohort_size": len(cohort_powers)
                    },
                    confidence=confidence,
                    detection_method="LEVEL_4_SPATIAL_PEER_MAD",
                    model_version=self.MODEL_VERSION,
                    recommended_action=f"Spatial peer outlier: Inverter generating {deficit_kw:.1f} kW ({dev_ratio*100:.1f}%) less than array cohort under identical weather. Investigate string outages or localized shading."
                )
            ]

        return []
