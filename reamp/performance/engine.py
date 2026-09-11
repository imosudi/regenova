"""
REAMP Performance Intelligence Engine.
Canonical orchestrator evaluating expected generation, performance gaps,
state arbitration, data confidence, and explainable waterfall loss attribution.
"""

import datetime
from typing import Dict, Any, Optional, List, Union
from reamp.performance.models import (
    OperatingState,
    LossCategory,
    PerformanceClassification,
    LossComponent,
    SolarParameters,
    WindParameters,
    BessParameters,
    PerformanceEvaluationResult,
)
from reamp.performance.solar import SolarPerformanceModel
from reamp.performance.wind import WindPerformanceModel
from reamp.performance.bess import BessPerformanceModel


class PerformanceIntelligenceEngine:
    """
    Central deterministic engine evaluating expected vs actual generation.
    Rigourously isolates environmental variation, underperformance, missing data, and outages.
    """

    MODEL_VERSION = "2.0.0-phase7"

    def __init__(self):
        self.solar_model = SolarPerformanceModel()
        self.wind_model = WindPerformanceModel()
        self.bess_model = BessPerformanceModel()

    def evaluate_solar(
        self,
        asset_id: str,
        params: SolarParameters,
        telemetry: Dict[str, Any],
        duration_hours: float = 1.0
    ) -> PerformanceEvaluationResult:
        """
        Evaluate Solar PV performance, computing weather-adjusted expected power,
        IEC 61724-1 PR, performance gap, and transparent loss waterfall.
        """
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        tariff = params.ppa_tariff_per_kwh

        # 1. Operational State Ingestion
        op_state_str = str(telemetry.get("operating_state", "RUNNING")).upper()
        try:
            op_state = OperatingState(op_state_str)
        except ValueError:
            op_state = OperatingState.RUNNING

        # 2. Quality Gate: Missing or Corrupt Data Handling
        g_poa = telemetry.get("irradiance_poa_wm2")
        p_actual = telemetry.get("actual_power_kw")
        t_amb = telemetry.get("temperature_ambient_c", 25.0)
        t_bom = telemetry.get("temperature_module_c")
        telemetry_confidence = float(telemetry.get("confidence", 1.0))
        telemetry_quality = str(telemetry.get("quality_status", "VALID")).upper()

        if g_poa is None or p_actual is None or telemetry_quality in ("INVALID", "MISSING"):
            # Penalize confidence and suppress false equipment alarms
            confidence = min(0.30, telemetry_confidence)
            loss = LossComponent(
                category=LossCategory.MISSING_DATA,
                lost_power_kw=0.0,
                lost_energy_kwh=0.0,
                financial_loss=0.0,
                explanation="Critical telemetry (irradiance or power) is missing or invalid. False failure alarms suppressed."
            )
            return PerformanceEvaluationResult(
                asset_id=asset_id,
                technology_type="SOLAR_PV",
                operating_state=op_state,
                classification=PerformanceClassification.MISSING_DATA,
                expected_power_kw=0.0,
                actual_power_kw=float(p_actual) if p_actual is not None else 0.0,
                performance_gap_kw=0.0,
                performance_ratio=None,
                weather_adjusted_pr=None,
                confidence=confidence,
                is_uncertain=True,
                losses=[loss],
                total_lost_energy_kwh=0.0,
                total_financial_loss=0.0,
                explanation="Evaluation paused: Telemetry channel missing or flagged invalid. Confidence penalized.",
                timestamp=now_str,
                model_version=self.MODEL_VERSION,
                metadata={"quality_status": telemetry_quality}
            )

        # 3. Physics Expected Power Calculation
        solar_eval = self.solar_model.calculate_expected_power(
            params=params,
            g_poa_wm2=float(g_poa),
            t_amb_c=float(t_amb),
            t_bom_c=float(t_bom) if t_bom is not None else None
        )
        p_expected = solar_eval["p_ac_expected"]
        t_cell = solar_eval["t_cell_c"]

        # 4. IEC 61724-1 Performance Ratios
        pr_raw, pr_stc = self.solar_model.calculate_performance_ratios(
            actual_power_kw=float(p_actual),
            params=params,
            g_poa_wm2=float(g_poa),
            t_cell_c=t_cell
        )

        losses: List[LossComponent] = []

        # 5. Quality Gate State Arbitration
        if op_state in (OperatingState.FAULT_TRIPPED, OperatingState.MAINTENANCE, OperatingState.OFFLINE):
            # Asset Outage: Deficit is attributed entirely to equipment availability
            classification = PerformanceClassification.OUTAGE
            p_gap = p_expected
            lost_kwh = round(p_gap * duration_hours, 2)
            fin_loss = round(lost_kwh * tariff, 2)
            losses.append(LossComponent(
                category=LossCategory.ASSET_OUTAGE,
                lost_power_kw=p_gap,
                lost_energy_kwh=lost_kwh,
                financial_loss=fin_loss,
                explanation=f"Asset in operational outage ({op_state.value}). Lost potential attributed to availability downtime."
            ))
            explanation = f"Outage event ({op_state.value}): Full expected generation of {p_expected:.1f} kW lost to downtime."

        elif op_state == OperatingState.CURTAILED:
            # Grid Curtailment: Deficit is due to external grid constraint
            classification = PerformanceClassification.CURTAILED
            curtail_limit = float(telemetry.get("curtailment_limit_kw", p_actual))
            p_gap = max(0.0, p_expected - float(p_actual))
            lost_kwh = round(p_gap * duration_hours, 2)
            fin_loss = round(lost_kwh * tariff, 2)
            losses.append(LossComponent(
                category=LossCategory.CURTAILMENT,
                lost_power_kw=p_gap,
                lost_energy_kwh=lost_kwh,
                financial_loss=fin_loss,
                explanation=f"Grid curtailment active (limit {curtail_limit:.1f} kW). Deemed generation claim recorded."
            ))
            explanation = f"Utility curtailment active: Output restricted by grid operator; {lost_kwh:.1f} kWh deemed loss."

        else:
            # Operational State is RUNNING (or STANDBY)
            # Compile Waterfall Loss Breakdown
            # A. Environmental Resource Variation
            if solar_eval["p_loss_resource"] > 0.0:
                losses.append(LossComponent(
                    category=LossCategory.RESOURCE_VARIATION,
                    lost_power_kw=solar_eval["p_loss_resource"],
                    lost_energy_kwh=round(solar_eval["p_loss_resource"] * duration_hours, 2),
                    financial_loss=0.0,  # Natural resource deficit is not a penalized financial loss
                    explanation=f"Sub-STC irradiance ({g_poa:.1f} W/m2 vs 1000 W/m2 reference)."
                ))

            # B. Thermal Derating Loss
            if solar_eval["p_loss_thermal"] > 0.0:
                losses.append(LossComponent(
                    category=LossCategory.THERMAL_DERATE,
                    lost_power_kw=solar_eval["p_loss_thermal"],
                    lost_energy_kwh=round(solar_eval["p_loss_thermal"] * duration_hours, 2),
                    financial_loss=0.0,  # Uncontrollable ambient temperature effect
                    explanation=f"Cell temperature elevation ({t_cell:.1f} degC vs 25 degC STC, derate factor {solar_eval['f_temp']:.3f})."
                ))

            # C. Inverter Clipping Loss
            if solar_eval["p_loss_clipping"] > 0.0:
                losses.append(LossComponent(
                    category=LossCategory.INVERTER_CLIPPING,
                    lost_power_kw=solar_eval["p_loss_clipping"],
                    lost_energy_kwh=round(solar_eval["p_loss_clipping"] * duration_hours, 2),
                    financial_loss=0.0,  # Intentional DC oversizing design limit
                    explanation=f"DC generation exceeded AC inverter rating ({params.rated_ac_kw} kW)."
                ))

            # D. Controllable Technical Underperformance
            p_gap_raw = p_expected - float(p_actual)
            p_gap = max(0.0, p_gap_raw)

            # Check threshold for true underperformance
            # We allow 3% tolerance for instrumentation noise
            tolerance_kw = 0.03 * params.rated_ac_kw
            if p_gap > tolerance_kw:
                classification = PerformanceClassification.UNDERPERFORMING
                lost_kwh = round(p_gap * duration_hours, 2)
                fin_loss = round(lost_kwh * tariff, 2)
                losses.append(LossComponent(
                    category=LossCategory.CONTROLLABLE_UNDERPERFORMANCE,
                    lost_power_kw=round(p_gap, 2),
                    lost_energy_kwh=lost_kwh,
                    financial_loss=fin_loss,
                    explanation=f"Controllable underperformance: Deficit of {p_gap:.1f} kW under prevailing irradiance."
                ))
                explanation = f"Asset underperforming: Actual output is {p_gap:.1f} kW below expectation (PR_STC={pr_stc:.2f} vs expected ~0.98). Investigate soiling or string faults."
            elif float(g_poa) < 400.0:
                classification = PerformanceClassification.ENVIRONMENTAL_VARIATION
                p_gap = 0.0
                explanation = f"Nominal generation under low irradiance conditions ({g_poa:.1f} W/m2). Performance ratio nominal."
            else:
                classification = PerformanceClassification.NOMINAL
                p_gap = 0.0
                explanation = f"Nominal operation: Actual generation ({p_actual:.1f} kW) meets physical expectation ({p_expected:.1f} kW)."

        total_kwh = sum(l.lost_energy_kwh for l in losses if l.category in (LossCategory.CONTROLLABLE_UNDERPERFORMANCE, LossCategory.ASSET_OUTAGE, LossCategory.CURTAILMENT))
        total_fin = sum(l.financial_loss for l in losses)

        return PerformanceEvaluationResult(
            asset_id=asset_id,
            technology_type="SOLAR_PV",
            operating_state=op_state,
            classification=classification,
            expected_power_kw=p_expected,
            actual_power_kw=float(p_actual),
            performance_gap_kw=round(p_gap, 2),
            performance_ratio=pr_raw,
            weather_adjusted_pr=pr_stc,
            confidence=telemetry_confidence,
            is_uncertain=telemetry_confidence <= 0.60,
            losses=losses,
            total_lost_energy_kwh=round(total_kwh, 2),
            total_financial_loss=round(total_fin, 2),
            explanation=explanation,
            timestamp=now_str,
            model_version=self.MODEL_VERSION,
            metadata={
                "t_cell_c": t_cell,
                "f_temp": solar_eval["f_temp"],
                "g_poa_wm2": float(g_poa),
            }
        )

    def evaluate_wind(
        self,
        asset_id: str,
        params: WindParameters,
        telemetry: Dict[str, Any],
        duration_hours: float = 1.0
    ) -> PerformanceEvaluationResult:
        """Evaluate Wind Turbine generator performance per IEC 61400-12-1."""
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        tariff = params.ppa_tariff_per_kwh

        op_state_str = str(telemetry.get("operating_state", "RUNNING")).upper()
        try:
            op_state = OperatingState(op_state_str)
        except ValueError:
            op_state = OperatingState.RUNNING

        v_wind = telemetry.get("wind_speed_ms")
        p_actual = telemetry.get("actual_power_kw")
        p_baro = telemetry.get("pressure_barometric_hpa", 1013.25)
        t_amb = telemetry.get("temperature_ambient_c", 15.0)
        telemetry_confidence = float(telemetry.get("confidence", 1.0))
        telemetry_quality = str(telemetry.get("quality_status", "VALID")).upper()

        if v_wind is None or p_actual is None or telemetry_quality in ("INVALID", "MISSING"):
            confidence = min(0.30, telemetry_confidence)
            loss = LossComponent(
                category=LossCategory.MISSING_DATA,
                lost_power_kw=0.0,
                lost_energy_kwh=0.0,
                financial_loss=0.0,
                explanation="Critical wind speed or power telemetry missing. False alarms suppressed."
            )
            return PerformanceEvaluationResult(
                asset_id=asset_id,
                technology_type="WIND_TURBINE",
                operating_state=op_state,
                classification=PerformanceClassification.MISSING_DATA,
                expected_power_kw=0.0,
                actual_power_kw=float(p_actual) if p_actual is not None else 0.0,
                performance_gap_kw=0.0,
                performance_ratio=None,
                weather_adjusted_pr=None,
                confidence=confidence,
                is_uncertain=True,
                losses=[loss],
                total_lost_energy_kwh=0.0,
                total_financial_loss=0.0,
                explanation="Evaluation paused: Wind telemetry missing or invalid.",
                timestamp=now_str,
                model_version=self.MODEL_VERSION
            )

        wind_eval = self.wind_model.calculate_expected_power(
            params=params,
            wind_speed_ms=float(v_wind),
            p_baro_hpa=float(p_baro),
            t_amb_c=float(t_amb)
        )
        p_expected = wind_eval["p_expected"]

        losses: List[LossComponent] = []

        if op_state in (OperatingState.FAULT_TRIPPED, OperatingState.MAINTENANCE, OperatingState.OFFLINE):
            classification = PerformanceClassification.OUTAGE
            p_gap = p_expected
            lost_kwh = round(p_gap * duration_hours, 2)
            fin_loss = round(lost_kwh * tariff, 2)
            losses.append(LossComponent(
                category=LossCategory.ASSET_OUTAGE,
                lost_power_kw=p_gap,
                lost_energy_kwh=lost_kwh,
                financial_loss=fin_loss,
                explanation=f"Wind turbine in outage state {op_state.value}."
            ))
            explanation = f"Turbine in outage ({op_state.value}): {p_expected:.1f} kW aerodynamic potential lost to downtime."
        else:
            if wind_eval["p_loss_resource"] > 0.0:
                losses.append(LossComponent(
                    category=LossCategory.RESOURCE_VARIATION,
                    lost_power_kw=wind_eval["p_loss_resource"],
                    lost_energy_kwh=round(wind_eval["p_loss_resource"] * duration_hours, 2),
                    financial_loss=0.0,
                    explanation=f"Wind speed below rated speed ({v_wind:.1f} m/s in {wind_eval['regime']})."
                ))

            p_gap_raw = p_expected - float(p_actual)
            p_gap = max(0.0, p_gap_raw)
            tolerance_kw = 0.05 * params.rated_power_kw

            if p_gap > tolerance_kw:
                classification = PerformanceClassification.UNDERPERFORMING
                lost_kwh = round(p_gap * duration_hours, 2)
                fin_loss = round(lost_kwh * tariff, 2)
                losses.append(LossComponent(
                    category=LossCategory.CONTROLLABLE_UNDERPERFORMANCE,
                    lost_power_kw=round(p_gap, 2),
                    lost_energy_kwh=lost_kwh,
                    financial_loss=fin_loss,
                    explanation=f"Aerodynamic underperformance: Power curve deficit of {p_gap:.1f} kW at {v_wind:.1f} m/s."
                ))
                explanation = f"Wind turbine underperforming: Missing {p_gap:.1f} kW relative to power curve. Check yaw alignment or blade icing."
            elif float(v_wind) < params.cut_in_speed_ms:
                classification = PerformanceClassification.ENVIRONMENTAL_VARIATION
                p_gap = 0.0
                explanation = f"Calm conditions (wind speed {v_wind:.1f} m/s below cut-in {params.cut_in_speed_ms} m/s). Turbine in standby."
            else:
                classification = PerformanceClassification.NOMINAL
                p_gap = 0.0
                explanation = f"Nominal generation: Turbine tracking IEC 61400-12-1 power curve cleanly ({p_actual:.1f} kW)."

        total_kwh = sum(l.lost_energy_kwh for l in losses if l.category in (LossCategory.CONTROLLABLE_UNDERPERFORMANCE, LossCategory.ASSET_OUTAGE))
        total_fin = sum(l.financial_loss for l in losses)

        # Theoretical power coefficient ratio
        pr_approx = round(float(p_actual) / p_expected, 4) if p_expected > 0.0 else None

        return PerformanceEvaluationResult(
            asset_id=asset_id,
            technology_type="WIND_TURBINE",
            operating_state=op_state,
            classification=classification,
            expected_power_kw=p_expected,
            actual_power_kw=float(p_actual),
            performance_gap_kw=round(p_gap, 2),
            performance_ratio=pr_approx,
            weather_adjusted_pr=pr_approx,
            confidence=telemetry_confidence,
            is_uncertain=telemetry_confidence <= 0.60,
            losses=losses,
            total_lost_energy_kwh=round(total_kwh, 2),
            total_financial_loss=round(total_fin, 2),
            explanation=explanation,
            timestamp=now_str,
            model_version=self.MODEL_VERSION,
            metadata=wind_eval
        )

    def evaluate_bess(
        self,
        asset_id: str,
        params: BessParameters,
        telemetry: Dict[str, Any],
        duration_hours: float = 1.0
    ) -> PerformanceEvaluationResult:
        """Evaluate BESS dispatch tracking and thermal de-rating."""
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        tariff = params.ppa_tariff_per_kwh

        op_state_str = str(telemetry.get("operating_state", "RUNNING")).upper()
        try:
            op_state = OperatingState(op_state_str)
        except ValueError:
            op_state = OperatingState.RUNNING

        p_setpoint = telemetry.get("dispatch_setpoint_kw")
        p_actual = telemetry.get("actual_power_kw")
        soc = telemetry.get("state_of_charge_percent", 50.0)
        t_cell = telemetry.get("temperature_cell_max_c", 25.0)
        telemetry_confidence = float(telemetry.get("confidence", 1.0))
        telemetry_quality = str(telemetry.get("quality_status", "VALID")).upper()

        if p_setpoint is None or p_actual is None or telemetry_quality in ("INVALID", "MISSING"):
            confidence = min(0.30, telemetry_confidence)
            loss = LossComponent(
                category=LossCategory.MISSING_DATA,
                lost_power_kw=0.0,
                lost_energy_kwh=0.0,
                financial_loss=0.0,
                explanation="BESS setpoint or power telemetry channel missing. Alarms suppressed."
            )
            return PerformanceEvaluationResult(
                asset_id=asset_id,
                technology_type="BESS",
                operating_state=op_state,
                classification=PerformanceClassification.MISSING_DATA,
                expected_power_kw=0.0,
                actual_power_kw=float(p_actual) if p_actual is not None else 0.0,
                performance_gap_kw=0.0,
                performance_ratio=None,
                weather_adjusted_pr=None,
                confidence=confidence,
                is_uncertain=True,
                losses=[loss],
                total_lost_energy_kwh=0.0,
                total_financial_loss=0.0,
                explanation="Evaluation paused: BESS telemetry missing or invalid.",
                timestamp=now_str,
                model_version=self.MODEL_VERSION
            )

        bess_eval = self.bess_model.calculate_expected_power(
            params=params,
            setpoint_kw=float(p_setpoint),
            soc_percent=float(soc),
            cell_temp_c=float(t_cell)
        )
        p_expected = bess_eval["p_expected"]

        losses: List[LossComponent] = []
        p_gap_raw = abs(p_expected) - abs(float(p_actual))
        p_gap = max(0.0, p_gap_raw)

        if op_state in (OperatingState.FAULT_TRIPPED, OperatingState.MAINTENANCE, OperatingState.OFFLINE):
            classification = PerformanceClassification.OUTAGE
            lost_kwh = round(abs(p_expected) * duration_hours, 2)
            fin_loss = round(lost_kwh * tariff, 2)
            losses.append(LossComponent(
                category=LossCategory.ASSET_OUTAGE,
                lost_power_kw=abs(p_expected),
                lost_energy_kwh=lost_kwh,
                financial_loss=fin_loss,
                explanation=f"BESS unavailable due to {op_state.value}."
            ))
            explanation = f"BESS in outage state {op_state.value}."
        elif p_gap > (0.05 * params.rated_power_kw):
            classification = PerformanceClassification.UNDERPERFORMING
            lost_kwh = round(p_gap * duration_hours, 2)
            fin_loss = round(lost_kwh * tariff, 2)
            losses.append(LossComponent(
                category=LossCategory.CONTROLLABLE_UNDERPERFORMANCE,
                lost_power_kw=p_gap,
                lost_energy_kwh=lost_kwh,
                financial_loss=fin_loss,
                explanation=f"BESS setpoint tracking deficit: Failed to meet dispatch target by {p_gap:.1f} kW."
            ))
            explanation = f"BESS underperforming setpoint: Tracking error of {p_gap:.1f} kW."
        else:
            classification = PerformanceClassification.NOMINAL
            p_gap = 0.0
            explanation = f"BESS meeting dispatch target cleanly: Actual {p_actual:.1f} kW matches target {p_expected:.1f} kW."

        total_kwh = sum(l.lost_energy_kwh for l in losses if l.category in (LossCategory.CONTROLLABLE_UNDERPERFORMANCE, LossCategory.ASSET_OUTAGE))
        total_fin = sum(l.financial_loss for l in losses)

        return PerformanceEvaluationResult(
            asset_id=asset_id,
            technology_type="BESS",
            operating_state=op_state,
            classification=classification,
            expected_power_kw=p_expected,
            actual_power_kw=float(p_actual),
            performance_gap_kw=round(p_gap, 2),
            performance_ratio=bess_eval["rated_rte"],
            weather_adjusted_pr=bess_eval["rated_rte"],
            confidence=telemetry_confidence,
            is_uncertain=telemetry_confidence <= 0.60,
            losses=losses,
            total_lost_energy_kwh=round(total_kwh, 2),
            total_financial_loss=round(total_fin, 2),
            explanation=explanation,
            timestamp=now_str,
            model_version=self.MODEL_VERSION,
            metadata=bess_eval
        )
