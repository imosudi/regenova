"""
REAMP Solar PV Performance Model.
Physics-grounded implementation conforming to IEC 61724-1 and NMOT cell temperature formulations.
"""

import math
from typing import Tuple, Dict, Any, Optional
from reamp.performance.models import SolarParameters


class SolarPerformanceModel:
    """Physics-based expected power and loss attribution for Solar PV systems."""

    MIN_OPERATIONAL_IRRADIANCE_WM2 = 20.0  # W/m2 below which inverters enter standby

    @staticmethod
    def estimate_cell_temperature(
        t_amb_c: float,
        g_poa_wm2: float,
        nmot_c: float = 45.0,
        t_bom_c: Optional[float] = None
    ) -> float:
        """
        Estimate PV module cell temperature in degC.
        Prefers direct back-of-module thermocouple (T_bom) with offset gradient if available.
        Otherwise uses Sandia / PVsyst empirical formulation based on NMOT and ambient temperature.
        """
        if t_bom_c is not None:
            # Empirical thermal gradient from backsheet to junction
            delta_junction = (g_poa_wm2 / 1000.0) * 3.0
            return round(t_bom_c + delta_junction, 2)

        # Standard NMOT / Evans-PVsyst empirical model
        delta_t = g_poa_wm2 * ((nmot_c - 20.0) / 800.0)
        return round(t_amb_c + delta_t, 2)

    @classmethod
    def calculate_expected_power(
        cls,
        params: SolarParameters,
        g_poa_wm2: float,
        t_amb_c: float,
        t_bom_c: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate expected DC and AC power, cell temperature, and intermediate physical losses.
        Returns a dictionary with all intermediate physical states for complete explainability.
        """
        if g_poa_wm2 < cls.MIN_OPERATIONAL_IRRADIANCE_WM2:
            return {
                "t_cell_c": t_amb_c,
                "f_temp": 1.0,
                "p_dc_expected": 0.0,
                "p_ac_uncapped": 0.0,
                "p_ac_expected": 0.0,
                "p_loss_resource": params.rated_ac_kw,
                "p_loss_thermal": 0.0,
                "p_loss_clipping": 0.0,
            }

        # 1. Effective Cell Temperature
        t_cell_c = cls.estimate_cell_temperature(t_amb_c, g_poa_wm2, params.nmot_c, t_bom_c)

        # 2. Temperature Derating Factor (IEC 61724-1)
        # Typically gamma_pmp is negative (e.g. -0.0038 / degC)
        f_temp = 1.0 + params.gamma_pmp * (t_cell_c - 25.0)
        f_temp = max(0.10, min(1.30, f_temp))  # Physical plausibility bounding

        # 3. Base DC Power before temperature derate
        effective_optics = params.soiling_factor * params.dc_loss_factor
        p_dc_stc_unadjusted = params.rated_dc_kw * (g_poa_wm2 / 1000.0) * effective_optics

        # 4. Temperature-compensated DC Power
        p_dc_expected = p_dc_stc_unadjusted * f_temp

        # 5. Inverter AC Conversion
        p_ac_uncapped = p_dc_expected * params.inverter_efficiency

        # 6. Inverter Capacity Saturation (Clipping)
        p_ac_expected = min(params.rated_ac_kw, p_ac_uncapped)

        # 7. Physical Loss Components
        # Resource variation loss relative to nominal rated AC output
        nominal_potential = params.rated_ac_kw
        p_loss_resource = max(0.0, nominal_potential - (p_dc_stc_unadjusted * params.inverter_efficiency))
        
        # Thermal loss: difference between 25C potential and actual temperature derated potential
        p_25c_potential = p_dc_stc_unadjusted * params.inverter_efficiency
        p_loss_thermal = max(0.0, p_25c_potential - p_ac_uncapped)

        # Clipping loss: power clipped by inverter maximum capacity
        p_loss_clipping = max(0.0, p_ac_uncapped - params.rated_ac_kw)

        return {
            "t_cell_c": t_cell_c,
            "f_temp": round(f_temp, 4),
            "p_dc_expected": round(p_dc_expected, 2),
            "p_ac_uncapped": round(p_ac_uncapped, 2),
            "p_ac_expected": round(p_ac_expected, 2),
            "p_loss_resource": round(p_loss_resource, 2),
            "p_loss_thermal": round(p_loss_thermal, 2),
            "p_loss_clipping": round(p_loss_clipping, 2),
        }

    @classmethod
    def calculate_performance_ratios(
        cls,
        actual_power_kw: float,
        params: SolarParameters,
        g_poa_wm2: float,
        t_cell_c: float
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate raw Performance Ratio (PR_raw) and weather-adjusted,
        temperature-compensated Performance Ratio (PR_stc) per IEC 61724-1.
        Returns: (pr_raw, pr_stc)
        """
        if g_poa_wm2 < cls.MIN_OPERATIONAL_IRRADIANCE_WM2:
            return None, None

        # Reference DC Yield at prevailing irradiance
        p_ref_stc = params.rated_dc_kw * (g_poa_wm2 / 1000.0)
        if p_ref_stc <= 0.0:
            return None, None

        pr_raw = actual_power_kw / p_ref_stc

        # Temperature compensation factor
        f_temp = 1.0 + params.gamma_pmp * (t_cell_c - 25.0)
        p_ref_temp_corr = p_ref_stc * f_temp
        if p_ref_temp_corr <= 0.0:
            pr_stc = pr_raw
        else:
            pr_stc = actual_power_kw / p_ref_temp_corr

        return round(pr_raw, 4), round(pr_stc, 4)
