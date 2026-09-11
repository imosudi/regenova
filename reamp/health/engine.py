"""
REAMP Asset Health Assessment Engine.
Computes deterministic, explainable, multi-dimensional condition scores.
"""

import math
import datetime
from typing import Dict, Any, Optional, List, Tuple
from reamp.health.models import (
    HealthState,
    DimensionScore,
    HealthEvaluationResult,
    HealthProfileConfig
)
from reamp.health.profiles import get_profile_by_technology


class AssetHealthEngine:
    """Core deterministic engine evaluating physical health across 7 operational dimensions."""

    def __init__(self):
        pass

    @staticmethod
    def compute_performance_subindex(
        measured_perf: Optional[float],
        nominal_perf: float,
        unit: str = "ratio"
    ) -> Tuple[float, float, str]:
        """Compute performance sub-index based on weather-adjusted yield efficiency."""
        if measured_perf is None:
            return 0.0, 0.0, "MISSING"

        ratio = measured_perf / nominal_perf if nominal_perf > 0 else 0.0
        score = min(100.0, max(0.0, ratio * 100.0))
        return round(score, 2), 1.0, "VALID"

    @staticmethod
    def compute_thermal_subindex(
        measured_temp_c: Optional[float],
        nominal_temp_c: float,
        critical_temp_c: float,
        gamma: float = 1.5
    ) -> Tuple[float, float, str]:
        """Compute thermal stress sub-index using non-linear Arrhenius acceleration."""
        if measured_temp_c is None:
            return 0.0, 0.0, "MISSING"

        if measured_temp_c <= nominal_temp_c:
            return 100.0, 1.0, "VALID"

        if measured_temp_c >= critical_temp_c:
            return 0.0, 1.0, "VALID"

        delta_measured = measured_temp_c - nominal_temp_c
        delta_max = critical_temp_c - nominal_temp_c
        stress_ratio = delta_measured / delta_max
        score = 100.0 * max(0.0, 1.0 - (stress_ratio ** gamma))
        return round(score, 2), 1.0, "VALID"

    @staticmethod
    def compute_availability_subindex(
        uptime_hours: Optional[float],
        total_hours: Optional[float]
    ) -> Tuple[float, float, str]:
        """Compute availability sub-index based on operational uptime."""
        if uptime_hours is None or total_hours is None or total_hours <= 0:
            return 0.0, 0.0, "MISSING"

        avail_ratio = min(1.0, max(0.0, uptime_hours / total_hours))
        return round(avail_ratio * 100.0, 2), 1.0, "VALID"

    @staticmethod
    def compute_communication_subindex(
        is_online: Optional[bool],
        packet_drop_rate: float = 0.0,
        latency_ms: float = 50.0
    ) -> Tuple[float, float, str]:
        """Compute communication reliability sub-index."""
        if is_online is None:
            return 0.0, 0.0, "MISSING"

        if not is_online:
            return 0.0, 0.0, "VALID"  # Complete comms blackout -> confidence = 0.0

        drop_factor = max(0.0, 1.0 - packet_drop_rate)
        latency_factor = max(0.0, 1.0 - (latency_ms / 2000.0))
        score = 100.0 * drop_factor * latency_factor
        return round(score, 2), 1.0, "VALID"

    @staticmethod
    def compute_fault_history_subindex(
        alarms: Optional[List[Dict[str, Any]]],
        half_life_days: float = 3.0
    ) -> Tuple[float, float, str]:
        """Compute fault history sub-index applying exponential time-decay penalties."""
        if alarms is None:
            return 0.0, 0.0, "MISSING"

        severity_weights = {
            "LOW": 2.0,
            "MEDIUM": 8.0,
            "HIGH": 25.0,
            "CRITICAL": 50.0,
            "EMERGENCY": 60.0
        }
        decay_constant = math.log(2.0) / half_life_days

        total_penalty = 0.0
        for alm in alarms:
            sev = alm.get("severity", "LOW").upper()
            weight = severity_weights.get(sev, 2.0)
            age_days = float(alm.get("age_days", 0.0))
            decay_factor = math.exp(-decay_constant * age_days)
            total_penalty += weight * decay_factor

        score = max(0.0, 100.0 - total_penalty)
        return round(score, 2), 1.0, "VALID"

    @staticmethod
    def compute_degradation_subindex(
        age_years: Optional[float],
        design_life_years: float,
        cumulative_cycles: Optional[int] = None,
        rated_cycles: Optional[int] = None
    ) -> Tuple[float, float, str]:
        """Compute degradation sub-index combining calendar aging and cycling wear."""
        if age_years is None and cumulative_cycles is None:
            return 0.0, 0.0, "MISSING"

        cal_deg = 0.0
        if age_years is not None and design_life_years > 0:
            cal_deg = min(1.0, max(0.0, age_years / design_life_years))

        cyc_deg = 0.0
        if cumulative_cycles is not None and rated_cycles is not None and rated_cycles > 0:
            cyc_deg = min(1.0, max(0.0, cumulative_cycles / rated_cycles))

        max_deg = max(cal_deg, cyc_deg)
        score = 100.0 * (1.0 - max_deg)
        return round(score, 2), 1.0, "VALID"

    @staticmethod
    def compute_sensor_quality_subindex(
        valid_samples: Optional[int],
        total_samples: Optional[int],
        mean_confidence: float = 1.0
    ) -> Tuple[float, float, str]:
        """Compute sensor telemetry quality sub-index."""
        if valid_samples is None or total_samples is None or total_samples <= 0:
            return 0.0, 0.0, "MISSING"

        valid_ratio = min(1.0, max(0.0, valid_samples / total_samples))
        score = 100.0 * valid_ratio * mean_confidence
        return round(score, 2), 1.0, "VALID"

    def evaluate(
        self,
        asset_id: str,
        profile: HealthProfileConfig,
        evidence: Dict[str, Any]
    ) -> HealthEvaluationResult:
        """
        Execute deterministic multi-criteria asset health evaluation.
        Redistributes weights over available dimensions and calculates confidence penalties.
        """
        raw_scores: Dict[str, Tuple[float, float, str, Optional[float], str]] = {}

        # 1. Performance
        perf_data = evidence.get("performance", {})
        p_val = perf_data.get("value")
        p_score, p_conf, p_status = self.compute_performance_subindex(
            p_val, profile.nominal_perf_ratio
        )
        raw_scores["performance"] = (p_score, p_conf, p_status, p_val, "ratio")

        # 2. Thermal Stress
        therm_data = evidence.get("thermal", {})
        t_val = therm_data.get("temperature_c")
        t_score, t_conf, t_status = self.compute_thermal_subindex(
            t_val, profile.nominal_temp_c, profile.critical_temp_c, profile.arrhenius_gamma
        )
        raw_scores["thermal"] = (t_score, t_conf, t_status, t_val, "degC")

        # 3. Availability
        avail_data = evidence.get("availability", {})
        a_uptime = avail_data.get("uptime_hours")
        a_total = avail_data.get("total_hours")
        a_score, a_conf, a_status = self.compute_availability_subindex(a_uptime, a_total)
        raw_scores["availability"] = (a_score, a_conf, a_status, a_uptime, "hours")

        # 4. Communication
        comm_data = evidence.get("communication", {})
        c_online = comm_data.get("is_online")
        c_drop = comm_data.get("packet_drop_rate", 0.0)
        c_lat = comm_data.get("latency_ms", 50.0)
        c_score, c_conf, c_status = self.compute_communication_subindex(c_online, c_drop, c_lat)
        if "confidence" in comm_data:
            c_conf = min(c_conf, float(comm_data["confidence"]))
        raw_scores["communication"] = (c_score, c_conf, c_status, 1.0 if c_online else 0.0, "flag")

        # 5. Fault History
        fault_data = evidence.get("fault_history", {})
        f_alarms = fault_data.get("alarms")
        f_score, f_conf, f_status = self.compute_fault_history_subindex(
            f_alarms, profile.alarm_penalty_half_life_days
        )
        if "confidence" in fault_data:
            f_conf = min(f_conf, float(fault_data["confidence"]))
        raw_scores["fault_history"] = (f_score, f_conf, f_status, len(f_alarms) if f_alarms is not None else 0.0, "alarms")

        # 6. Degradation
        deg_data = evidence.get("degradation", {})
        d_age = deg_data.get("age_years")
        d_cycles = deg_data.get("cycles")
        d_score, d_conf, d_status = self.compute_degradation_subindex(
            d_age, profile.design_life_years, d_cycles, profile.rated_cycle_life
        )
        if "confidence" in deg_data:
            d_conf = min(d_conf, float(deg_data["confidence"]))
        raw_scores["degradation"] = (d_score, d_conf, d_status, d_age, "years")

        # 7. Sensor Quality
        dq_data = evidence.get("sensor_quality", {})
        q_valid = dq_data.get("valid_samples")
        q_total = dq_data.get("total_samples")
        q_conf_input = dq_data.get("confidence", 1.0)
        q_score, q_conf, q_status = self.compute_sensor_quality_subindex(q_valid, q_total, q_conf_input)
        if "confidence" in dq_data:
            q_conf = min(q_conf, float(dq_data["confidence"]))
        raw_scores["sensor_quality"] = (q_score, q_conf, q_status, q_valid, "samples")

        # Filter available dimensions (status != "MISSING")
        available_dims = {dim: profile.weights.get(dim, 0.0) for dim, data in raw_scores.items() if data[2] != "MISSING"}
        total_avail_weight = sum(available_dims.values())

        contributing_factors: Dict[str, DimensionScore] = {}
        weighted_sum = 0.0
        conf_sum = 0.0

        for dim, (score, conf, status, meas_val, unit) in raw_scores.items():
            cfg_weight = profile.weights.get(dim, 0.0)
            if status == "MISSING" or total_avail_weight == 0.0:
                eff_weight = 0.0
                weighted_contrib = 0.0
            else:
                eff_weight = cfg_weight / total_avail_weight
                weighted_contrib = round(score * eff_weight, 4)
                weighted_sum += weighted_contrib
                conf_sum += conf

            contributing_factors[dim] = DimensionScore(
                dimension=dim,
                score=score,
                configured_weight=cfg_weight,
                effective_weight=round(eff_weight, 4),
                weighted_contribution=weighted_contrib,
                confidence=conf,
                measured_value=meas_val,
                unit=unit,
                status=status
            )

        # Composite AHI Score
        final_score = round(min(100.0, max(0.0, weighted_sum)), 2)

        # Overall Confidence calculation: combines available weight proportion and individual dimension confidence
        if available_dims:
            mean_conf = conf_sum / len(available_dims)
            overall_confidence = round(total_avail_weight * mean_conf, 2)
        else:
            overall_confidence = 0.0

        is_uncertain = overall_confidence <= 0.60

        # Limiting Dimension Constraint (CIGRE / EPRI Asset Health Standard):
        # A severe degradation in any critical dimension caps the maximum allowable health state
        critical_scores = [
            contributing_factors[d].score
            for d in ("performance", "thermal", "fault_history")
            if d in contributing_factors and contributing_factors[d].status == "VALID"
        ]
        min_critical_score = min(critical_scores) if critical_scores else 100.0

        # Classify Base Health State
        if final_score >= 85.0:
            state = HealthState.EXCELLENT
            action = "Nominal operation: Continue standard scheduling."
        elif final_score >= 70.0:
            state = HealthState.GOOD
            action = "Minor variance: Monitor thermal and performance trends."
        elif final_score >= 50.0:
            state = HealthState.FAIR
            action = "Sub-optimal health: Schedule preventative inspection or cleaning."
        elif final_score >= 30.0:
            state = HealthState.POOR
            action = "Critical degradation: Auto-draft P2 corrective maintenance work order."
        else:
            state = HealthState.CRITICAL
            action = "Severe hazard / imminent failure: Request immediate derate or protective trip."

        # Apply Gating Rule: If a critical dimension is significantly degraded, state cannot be EXCELLENT
        if min_critical_score <= 50.0 and state == HealthState.EXCELLENT:
            state = HealthState.GOOD
            action = "Operational derate: Performance or thermal threshold significantly degraded."

        if is_uncertain:
            action += " (WARNING: Low evaluation confidence due to missing/stale telemetry)."

        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        return HealthEvaluationResult(
            asset_id=asset_id,
            technology_type=profile.technology_type,
            health_score=final_score,
            health_state=state,
            confidence=overall_confidence,
            is_uncertain=is_uncertain,
            contributing_factors=contributing_factors,
            timestamp=now_str,
            model_version=profile.model_version,
            recommended_action=action
        )
