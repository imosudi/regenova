#!/usr/bin/env python3
"""
REAMP Phase 6 - Automated Asset Health Intelligence Test Suite
Validates the 6 mandatory synthetic operational scenarios:
1. Healthy Asset
2. Degraded Asset
3. Communication Failure
4. Thermal Abnormality
5. Performance Degradation
6. Incomplete Telemetry
Plus tests for determinism, mathematical factor attribution, and technology profiles.
"""

import os
import sys
from typing import Dict, Any

# Ensure reamp package is importable
sys.path.insert(0, os.path.abspath("."))

from reamp.health.models import HealthState, HealthEvaluationResult
from reamp.health.profiles import (
    SOLAR_PV_INVERTER_PROFILE,
    WIND_TURBINE_PROFILE,
    BESS_BATTERY_PROFILE,
    get_profile_by_technology
)
from reamp.health.engine import AssetHealthEngine

ERRORS = 0

def log_pass(msg: str):
    print(f"[\033[92mPASS\033[0m] {msg}")

def log_fail(msg: str):
    global ERRORS
    ERRORS += 1
    print(f"[\033[91mFAIL\033[0m] {msg}")


def test_case_1_healthy_asset():
    print("\n--- 1. Testing Case 1: Healthy Asset ---")
    engine = AssetHealthEngine()
    profile = SOLAR_PV_INVERTER_PROFILE

    evidence = {
        "performance": {"value": 0.82, "confidence": 1.0},
        "thermal": {"temperature_c": 52.0, "confidence": 1.0},
        "availability": {"uptime_hours": 720.0, "total_hours": 720.0, "confidence": 1.0},
        "communication": {"is_online": True, "packet_drop_rate": 0.0, "latency_ms": 25.0, "confidence": 1.0},
        "fault_history": {"alarms": [], "confidence": 1.0},
        "degradation": {"age_years": 1.5, "cycles": 500, "confidence": 1.0},
        "sensor_quality": {"valid_samples": 86400, "total_samples": 86400, "confidence": 1.0}
    }

    res = engine.evaluate("inv-healthy-01", profile, evidence)

    if res.health_score >= 95.0 and res.health_state == HealthState.EXCELLENT:
        log_pass(f"Healthy asset correctly scored {res.health_score} with state {res.health_state.value}")
    else:
        log_fail(f"Healthy asset score mismatch: {res.health_score} ({res.health_state})")

    if res.confidence >= 0.95 and not res.is_uncertain:
        log_pass(f"Evaluation confidence verified high: {res.confidence}")
    else:
        log_fail(f"Confidence score mismatch: {res.confidence}")


def test_case_2_degraded_asset():
    print("\n--- 2. Testing Case 2: Degraded Asset ---")
    engine = AssetHealthEngine()
    profile = SOLAR_PV_INVERTER_PROFILE

    evidence = {
        "performance": {"value": 0.35, "confidence": 1.0},  # Low PR (< 50% nominal)
        "thermal": {"temperature_c": 88.0, "confidence": 1.0},  # High heatsink temp
        "availability": {"uptime_hours": 450.0, "total_hours": 720.0, "confidence": 1.0},  # Frequent trips
        "communication": {"is_online": True, "packet_drop_rate": 0.15, "latency_ms": 400.0, "confidence": 0.9},
        "fault_history": {"alarms": [
            {"severity": "CRITICAL", "age_days": 0.5},
            {"severity": "HIGH", "age_days": 1.2},
            {"severity": "HIGH", "age_days": 2.0}
        ], "confidence": 1.0},
        "degradation": {"age_years": 22.0, "confidence": 1.0},  # Near 25-yr end-of-life
        "sensor_quality": {"valid_samples": 70000, "total_samples": 86400, "confidence": 0.85}
    }

    res = engine.evaluate("inv-degraded-01", profile, evidence)

    if res.health_score < 45.0 and res.health_state in (HealthState.POOR, HealthState.CRITICAL):
        log_pass(f"Degraded asset correctly scored {res.health_score} with state {res.health_state.value}")
    else:
        log_fail(f"Degraded asset did not trigger low state: {res.health_score} ({res.health_state})")

    if "work order" in res.recommended_action.lower() or "derate" in res.recommended_action.lower():
        log_pass(f"Prescriptive maintenance action generated: {res.recommended_action}")
    else:
        log_fail(f"Missing prescriptive action: {res.recommended_action}")


def test_case_3_communication_failure():
    print("\n--- 3. Testing Case 3: Communication Failure ---")
    engine = AssetHealthEngine()
    profile = SOLAR_PV_INVERTER_PROFILE

    evidence = {
        "performance": {"value": 0.80, "confidence": 1.0},
        "thermal": {"temperature_c": 55.0, "confidence": 1.0},
        "availability": {"uptime_hours": 720.0, "total_hours": 720.0, "confidence": 1.0},
        "communication": {"is_online": False, "confidence": 0.0},  # Complete blackout
        "fault_history": {"alarms": [], "confidence": 1.0},
        "degradation": {"age_years": 2.0, "confidence": 1.0},
        "sensor_quality": {"valid_samples": 0, "total_samples": 86400, "confidence": 0.0}
    }

    res = engine.evaluate("inv-comm-loss-01", profile, evidence)

    comm_factor = res.contributing_factors["communication"]
    if comm_factor.score == 0.0:
        log_pass("Communication sub-index collapsed to 0.0 on link loss")
    else:
        log_fail(f"Communication score should be 0.0, got {comm_factor.score}")

    if res.confidence < 0.90:
        log_pass(f"Confidence score penalized appropriately for comms failure: {res.confidence}")
    else:
        log_fail(f"Confidence score was not penalized: {res.confidence}")


def test_case_4_thermal_abnormality():
    print("\n--- 4. Testing Case 4: Thermal Abnormality ---")
    engine = AssetHealthEngine()
    profile = SOLAR_PV_INVERTER_PROFILE

    # Nominal asset except heatsink temperature is 92.0 C (critical limit is 95.0 C)
    evidence = {
        "performance": {"value": 0.81, "confidence": 1.0},
        "thermal": {"temperature_c": 92.0, "confidence": 1.0},
        "availability": {"uptime_hours": 720.0, "total_hours": 720.0, "confidence": 1.0},
        "communication": {"is_online": True, "confidence": 1.0},
        "fault_history": {"alarms": [], "confidence": 1.0},
        "degradation": {"age_years": 1.0, "confidence": 1.0},
        "sensor_quality": {"valid_samples": 86400, "total_samples": 86400, "confidence": 1.0}
    }

    res = engine.evaluate("inv-hot-01", profile, evidence)

    therm_factor = res.contributing_factors["thermal"]
    if therm_factor.score < 20.0:
        log_pass(f"Thermal sub-index severely penalized by Arrhenius acceleration: {therm_factor.score}")
    else:
        log_fail(f"Thermal sub-index failed to penalize hotspot: {therm_factor.score}")

    # Verify thermal factor explains the majority of the score loss
    if therm_factor.score < res.health_score:
        log_pass("Explainability factor attribution correctly isolates thermal stress as dominant contributor")
    else:
        log_fail("Factor attribution failed to isolate thermal abnormality")


def test_case_5_performance_degradation():
    print("\n--- 5. Testing Case 5: Performance Degradation ---")
    engine = AssetHealthEngine()
    profile = WIND_TURBINE_PROFILE

    # Clean turbine except power coefficient Cp is 0.225 (50% of nominal 0.45 due to blade soiling/pitch fault)
    evidence = {
        "performance": {"value": 0.225, "confidence": 1.0},
        "thermal": {"temperature_c": 60.0, "confidence": 1.0},  # Normal gearbox temp (< 70 C)
        "availability": {"uptime_hours": 720.0, "total_hours": 720.0, "confidence": 1.0},
        "communication": {"is_online": True, "confidence": 1.0},
        "fault_history": {"alarms": [], "confidence": 1.0},
        "degradation": {"age_years": 3.0, "confidence": 1.0},
        "sensor_quality": {"valid_samples": 86400, "total_samples": 86400, "confidence": 1.0}
    }

    res = engine.evaluate("wtg-degraded-01", profile, evidence)

    perf_factor = res.contributing_factors["performance"]
    if perf_factor.score == 50.0:
        log_pass("Performance sub-index accurately reflects 50% aerodynamic yield efficiency")
    else:
        log_fail(f"Expected performance score 50.0, got {perf_factor.score}")

    if res.health_state in (HealthState.GOOD, HealthState.FAIR):
        log_pass(f"Overall state transitioned to {res.health_state.value} reflecting yield degradation")
    else:
        log_fail(f"Unexpected health state: {res.health_state.value}")


def test_case_6_incomplete_telemetry():
    print("\n--- 6. Testing Case 6: Incomplete Telemetry (Missing Data Handling) ---")
    engine = AssetHealthEngine()
    profile = BESS_BATTERY_PROFILE

    # Only provide performance and thermal telemetry; omit availability, comms, faults, degradation
    evidence = {
        "performance": {"value": 0.88, "confidence": 1.0},
        "thermal": {"temperature_c": 32.0, "confidence": 1.0}
    }

    res = engine.evaluate("bess-sparse-01", profile, evidence)

    # Check that missing dimensions did NOT cause exceptions and weights were redistributed
    perf_factor = res.contributing_factors["performance"]
    therm_factor = res.contributing_factors["thermal"]

    if perf_factor.status == "VALID" and therm_factor.status == "VALID":
        log_pass("Present dimensions evaluated cleanly")
    else:
        log_fail("Present dimensions failed evaluation")

    missing_dims = [dim for dim, f in res.contributing_factors.items() if f.status == "MISSING"]
    if len(missing_dims) == 5:
        log_pass(f"5 missing dimensions gracefully handled and flagged MISSING ({missing_dims})")
    else:
        log_fail(f"Expected 5 missing dimensions, got {len(missing_dims)}")

    # Effective weights for available dimensions should sum to 1.0
    total_eff_weight = sum(f.effective_weight for f in res.contributing_factors.values())
    if abs(total_eff_weight - 1.0) < 0.01:
        log_pass(f"Weight redistribution normalized cleanly to sum {total_eff_weight:.2f}")
    else:
        log_fail(f"Effective weights do not sum to 1.0: {total_eff_weight}")

    # Confidence should be penalized because only 50% of the weight was available
    if res.confidence <= 0.50 and res.is_uncertain:
        log_pass(f"Confidence score penalized ({res.confidence}) and flagged UNCERTAIN due to sparse data")
    else:
        log_fail(f"Sparse data failed to penalize confidence: {res.confidence}")


def test_determinism_and_factor_attribution():
    print("\n--- 7. Testing Determinism & Mathematical Factor Attribution ---")
    engine = AssetHealthEngine()
    profile = SOLAR_PV_INVERTER_PROFILE

    evidence = {
        "performance": {"value": 0.75, "confidence": 1.0},
        "thermal": {"temperature_c": 68.0, "confidence": 1.0},
        "availability": {"uptime_hours": 700.0, "total_hours": 720.0, "confidence": 1.0},
        "communication": {"is_online": True, "packet_drop_rate": 0.02, "latency_ms": 60.0, "confidence": 1.0},
        "fault_history": {"alarms": [{"severity": "MEDIUM", "age_days": 1.0}], "confidence": 1.0},
        "degradation": {"age_years": 4.0, "confidence": 1.0},
        "sensor_quality": {"valid_samples": 85000, "total_samples": 86400, "confidence": 0.98}
    }

    # Determinism: Run 50 iterations, verify identical results
    scores = [engine.evaluate("inv-det-01", profile, evidence).health_score for _ in range(50)]
    if len(set(scores)) == 1:
        log_pass(f"Determinism verified: 50/50 executions yielded identical score ({scores[0]})")
    else:
        log_fail(f"Non-deterministic outputs detected: {set(scores)}")

    # Factor Attribution: Sum of weighted contributions MUST equal health_score
    res = engine.evaluate("inv-det-01", profile, evidence)
    sum_contrib = sum(f.weighted_contribution for f in res.contributing_factors.values())
    if abs(sum_contrib - res.health_score) < 0.05:
        log_pass(f"Explainability verified: Sum of weighted contributions ({sum_contrib:.2f}) matches total score ({res.health_score})")
    else:
        log_fail(f"Attribution mismatch: sum={sum_contrib}, score={res.health_score}")


def main():
    print("================================================================")
    print("REAMP Phase 6 Verification: Asset Health Assessment Engine")
    print("================================================================")

    test_case_1_healthy_asset()
    test_case_2_degraded_asset()
    test_case_3_communication_failure()
    test_case_4_thermal_abnormality()
    test_case_5_performance_degradation()
    test_case_6_incomplete_telemetry()
    test_determinism_and_factor_attribution()

    print("\n================================================================")
    if ERRORS == 0:
        print("[\033[92mALL TESTS PASSED\033[0m] Phase 6 Asset Health quality gate criteria satisfied!")
        print("Notice: Results derived from synthetic test suites in accordance with Phase 6 instructions.")
        sys.exit(0)
    else:
        print(f"[\033[91mFAILED\033[0m] {ERRORS} test(s) failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
