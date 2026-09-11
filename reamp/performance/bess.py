"""
REAMP Battery Energy Storage System (BESS) Performance Model.
Electrochemical throughput, dispatch setpoint tracking, and round-trip efficiency evaluation.
"""

from typing import Dict, Any, Optional
from reamp.performance.models import BessParameters


class BessPerformanceModel:
    """Expected power, dispatch tracking, and loss attribution for BESS."""

    @classmethod
    def calculate_expected_power(
        cls,
        params: BessParameters,
        setpoint_kw: float,
        soc_percent: float,
        cell_temp_c: float = 25.0
    ) -> Dict[str, Any]:
        """
        Calculate expected BESS power based on dispatch setpoint, SoC limits,
        and battery thermal operational envelope.
        """
        soc_decimal = soc_percent / 100.0 if soc_percent > 1.0 else soc_percent

        # 1. Thermal Operational Derate
        # Optimal battery cell temperature range: 15°C - 35°C
        if cell_temp_c < 5.0:
            # Low temperature lithium plating risk -> charge/discharge rate restricted
            f_thermal = max(0.20, 1.0 - 0.05 * (5.0 - cell_temp_c))
        elif cell_temp_c > 40.0:
            # Elevated temperature accelerated degradation -> derating active
            f_thermal = max(0.30, 1.0 - 0.04 * (cell_temp_c - 40.0))
        else:
            f_thermal = 1.0

        effective_rated_kw = params.rated_power_kw * f_thermal

        # 2. Dispatch Setpoint Evaluation
        if setpoint_kw > 0.0:
            # Discharge mode
            if soc_decimal <= params.min_soc:
                p_expected = 0.0
                state_note = "DISCHARGE_BLOCKED_LOW_SOC"
            else:
                p_expected = min(setpoint_kw, effective_rated_kw)
                state_note = "DISCHARGING"
        elif setpoint_kw < 0.0:
            # Charge mode
            if soc_decimal >= params.max_soc:
                p_expected = 0.0
                state_note = "CHARGE_BLOCKED_HIGH_SOC"
            else:
                p_expected = max(setpoint_kw, -effective_rated_kw)
                state_note = "CHARGING"
        else:
            # Standby mode
            p_expected = 0.0
            state_note = "STANDBY"

        # Baseline auxiliary HVAC cooling load (parasitic loss)
        p_auxiliary_kw = 0.01 * params.rated_power_kw if abs(p_expected) > 0.0 else 0.003 * params.rated_power_kw

        return {
            "p_expected": round(p_expected, 2),
            "state_note": state_note,
            "f_thermal": round(f_thermal, 4),
            "p_auxiliary_kw": round(p_auxiliary_kw, 2),
            "rated_rte": params.rated_rte,
        }
