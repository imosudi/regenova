"""
REAMP Health Technology Profiles.
Pre-calibrated, technology-specific weight distributions, baselines, and thermal fatigue limits.
"""

from reamp.health.models import HealthProfileConfig


SOLAR_PV_INVERTER_PROFILE = HealthProfileConfig(
    technology_type="SOLAR_PV_INVERTER",
    model_version="AHI-PV-INV-v1.0",
    weights={
        "performance": 0.25,
        "thermal": 0.25,
        "availability": 0.15,
        "fault_history": 0.15,
        "degradation": 0.10,
        "communication": 0.05,
        "sensor_quality": 0.05
    },
    nominal_perf_ratio=0.82,     # Expected nominal IEC 61724-1 PR_STC
    nominal_temp_c=65.0,         # Heatsink rated threshold
    critical_temp_c=95.0,        # Thermal trip limit
    arrhenius_gamma=1.5,
    design_life_years=25.0,
    rated_cycle_life=10000
)

WIND_TURBINE_PROFILE = HealthProfileConfig(
    technology_type="WIND_TURBINE",
    model_version="AHI-WTG-v1.0",
    weights={
        "performance": 0.25,
        "fault_history": 0.20,
        "thermal": 0.15,
        "availability": 0.15,
        "degradation": 0.15,
        "communication": 0.05,
        "sensor_quality": 0.05
    },
    nominal_perf_ratio=0.45,     # Nominal power coefficient Cp
    nominal_temp_c=70.0,         # Gearbox oil nominal limit
    critical_temp_c=85.0,        # Gearbox trip temperature
    arrhenius_gamma=1.8,
    design_life_years=20.0,
    rated_cycle_life=100000
)

BESS_BATTERY_PROFILE = HealthProfileConfig(
    technology_type="BESS_STORAGE",
    model_version="AHI-BESS-v1.0",
    weights={
        "thermal": 0.30,
        "performance": 0.20,
        "fault_history": 0.15,
        "degradation": 0.15,
        "availability": 0.10,
        "communication": 0.05,
        "sensor_quality": 0.05
    },
    nominal_perf_ratio=0.88,     # Nominal Round-Trip Efficiency (RTE)
    nominal_temp_c=35.0,         # Max continuous cell temp
    critical_temp_c=60.0,        # Thermal runaway warning limit
    arrhenius_gamma=2.0,
    design_life_years=15.0,
    rated_cycle_life=5000
)

TRANSFORMER_PROFILE = HealthProfileConfig(
    technology_type="SUBSTATION_TRANSFORMER",
    model_version="AHI-XFMR-v1.0",
    weights={
        "thermal": 0.35,
        "fault_history": 0.20,
        "availability": 0.15,
        "degradation": 0.15,
        "performance": 0.05,
        "communication": 0.05,
        "sensor_quality": 0.05
    },
    nominal_perf_ratio=0.98,     # Electrical efficiency
    nominal_temp_c=75.0,         # Top oil temp
    critical_temp_c=110.0,       # Oil trip limit
    arrhenius_gamma=1.5,
    design_life_years=35.0,
    rated_cycle_life=20000
)


def get_profile_by_technology(tech_type: str) -> HealthProfileConfig:
    """Retrieve the standard profile for a given renewable technology type."""
    t = tech_type.upper()
    if "SOLAR" in t or "PV" in t or "INVERTER" in t:
        return SOLAR_PV_INVERTER_PROFILE
    elif "WIND" in t or "TURBINE" in t:
        return WIND_TURBINE_PROFILE
    elif "BESS" in t or "BATTERY" in t or "STORAGE" in t:
        return BESS_BATTERY_PROFILE
    elif "TRANSFORMER" in t or "SUBSTATION" in t:
        return TRANSFORMER_PROFILE
    else:
        # Generic fallback profile
        return SOLAR_PV_INVERTER_PROFILE
