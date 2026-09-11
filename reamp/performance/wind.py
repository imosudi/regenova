"""
REAMP Wind Turbine Performance Model.
Aerodynamic power curve formulation conforming to IEC 61400-12-1 with air density normalization.
"""

import math
from typing import Dict, Any, Optional
from reamp.performance.models import WindParameters


class WindPerformanceModel:
    """Physics-based expected power and loss attribution for Wind Turbines."""

    R_SPECIFIC_AIR = 287.058  # J/(kg*K)

    @classmethod
    def calculate_air_density(
        cls,
        p_baro_hpa: float = 1013.25,
        t_amb_c: float = 15.0
    ) -> float:
        """Calculate dry air density in kg/m3 from barometric pressure and ambient temperature."""
        t_kelvin = t_amb_c + 273.15
        p_pa = p_baro_hpa * 100.0
        rho = p_pa / (cls.R_SPECIFIC_AIR * t_kelvin)
        return round(rho, 4)

    @classmethod
    def calculate_expected_power(
        cls,
        params: WindParameters,
        wind_speed_ms: float,
        p_baro_hpa: float = 1013.25,
        t_amb_c: float = 15.0
    ) -> Dict[str, Any]:
        """
        Calculate expected wind turbine electrical output across four aerodynamic regimes
        with air density normalization per IEC 61400-12-1.
        """
        if wind_speed_ms < 0.0:
            wind_speed_ms = 0.0

        # 1. Air Density Correction
        rho = cls.calculate_air_density(p_baro_hpa, t_amb_c)
        density_ratio = rho / params.air_density_ref
        # Normalised wind speed equivalent for standard power curve
        v_norm = wind_speed_ms * math.pow(density_ratio, 1.0 / 3.0)

        # 2. Four-Regime Power Evaluation
        if v_norm < params.cut_in_speed_ms:
            # Region I: Sub-cut-in calm
            regime = "REGION_I_SUB_CUT_IN"
            p_expected = 0.0
            p_loss_resource = params.rated_power_kw
        elif v_norm < params.rated_speed_ms:
            # Region II: Aerodynamic cubic tracking
            regime = "REGION_II_AERODYNAMIC_TRACKING"
            v_cubed_delta = (v_norm ** 3) - (params.cut_in_speed_ms ** 3)
            denom = (params.rated_speed_ms ** 3) - (params.cut_in_speed_ms ** 3)
            ratio = max(0.0, min(1.0, v_cubed_delta / denom))
            p_expected = params.rated_power_kw * ratio
            p_loss_resource = params.rated_power_kw - p_expected
        elif v_norm <= params.cut_out_speed_ms:
            # Region III: Rated pitch control
            regime = "REGION_III_RATED_PITCH_CONTROL"
            p_expected = params.rated_power_kw
            p_loss_resource = 0.0
        else:
            # Region IV: Storm high-wind safety cutout
            regime = "REGION_IV_STORM_CUT_OUT"
            p_expected = 0.0
            p_loss_resource = params.rated_power_kw

        return {
            "v_normalized_ms": round(v_norm, 2),
            "air_density_kgm3": rho,
            "regime": regime,
            "p_expected": round(p_expected, 2),
            "p_loss_resource": round(p_loss_resource, 2),
        }
