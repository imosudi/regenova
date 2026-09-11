"""
REAMP Degradation and Remaining Useful Life (RUL) Engine.
Implements Weibull hazard modeling, degradation trajectory regression,
and strict Quality Gate evidence-sufficiency uncertainty enforcement.
"""

import math
from typing import List, Tuple, Optional, Dict, Any
from reamp.maintenance.models import (
    RULPrediction,
    EvidenceSufficiency,
)


class DegradationEngine:
    """
    Evaluates degradation trajectories, computes Weibull failure probabilities,
    and calculates RUL with rigorous uncertainty gating.
    """

    MODEL_NAME = "Weibull-OLS-Hybrid-v1.0"

    @staticmethod
    def compute_weibull_failure_probability(
        t_current_hours: float,
        horizon_hours: float = 720.0,   # 30-day horizon (30 * 24h)
        beta: float = 2.8,              # Wear-out shape parameter
        eta: float = 87600.0            # Characteristic 10-year life (87,600 h)
    ) -> float:
        """
        Compute conditional failure probability in the upcoming window Delta_t
        given survival up to t_current_hours.
        P_f(Delta_t | t_0) = 1 - exp(-[((t_0 + Delta_t)/eta)^beta - (t_0/eta)^beta])
        """
        if t_current_hours < 0.0 or eta <= 0.0:
            return 0.0

        t0 = max(0.0, float(t_current_hours))
        t1 = t0 + float(horizon_hours)

        cum_hazard_t0 = (t0 / eta) ** beta
        cum_hazard_t1 = (t1 / eta) ** beta
        delta_hazard = cum_hazard_t1 - cum_hazard_t0

        p_fail = 1.0 - math.exp(-delta_hazard)
        return round(float(min(1.0, max(0.0, p_fail))), 4)

    @classmethod
    def estimate_rul(
        cls,
        history: List[Tuple[float, float]],  # List of (operating_hours, health_score)
        current_health: float,
        operating_hours: float,
        eol_threshold: float = 30.0,
        telemetry_confidence: float = 1.0
    ) -> RULPrediction:
        """
        Estimate Remaining Useful Life (RUL) with confidence bounds.
        Enforces Phase 9 Quality Gate: Never claim precise RUL without sufficient evidence.
        """
        pf_30d = cls.compute_weibull_failure_probability(operating_hours)

        # ---------------------------------------------------------------------
        # 1. Quality Gate: Evidence Sufficiency Evaluation
        # ---------------------------------------------------------------------
        # Minimum sample size requirement: N >= 5 points and confidence >= 0.60
        if len(history) < 5 or telemetry_confidence < 0.60:
            return RULPrediction(
                predicted_rul_hours=None,
                rul_confidence_interval=(0.0, 0.0),
                failure_probability_30d=pf_30d,
                evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT,
                uncertainty_flag=True,
                degradation_rate_per_1000h=0.0,
                r_squared=0.0,
                model_name=cls.MODEL_NAME,
                explanation=(
                    f"Quality Gate Triggered: Insufficient degradation history (N={len(history)} < 5 "
                    f"or confidence={telemetry_confidence:.2f} < 0.60). Precise RUL prediction refused "
                    "in accordance with Phase 9 Quality Gate. Condition-based monitoring active."
                )
            )

        # ---------------------------------------------------------------------
        # 2. Ordinary Least Squares Linear Regression
        # ---------------------------------------------------------------------
        t_vals = [pt[0] for pt in history]
        h_vals = [pt[1] for pt in history]
        n = len(history)

        mean_t = sum(t_vals) / n
        mean_h = sum(h_vals) / n

        ss_tt = sum((t - mean_t) ** 2 for t in t_vals)
        ss_th = sum((t - mean_t) * (h - mean_h) for t, h in zip(t_vals, h_vals))

        if ss_tt <= 0.0:
            # Degenerate time series (identical timestamps)
            return RULPrediction(
                predicted_rul_hours=None,
                rul_confidence_interval=(0.0, 0.0),
                failure_probability_30d=pf_30d,
                evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT,
                uncertainty_flag=True,
                degradation_rate_per_1000h=0.0,
                r_squared=0.0,
                model_name=cls.MODEL_NAME,
                explanation="Degenerate time series: Insufficient elapsed operating time to model trend."
            )

        slope = ss_th / ss_tt  # Delta H / Delta t (points of health per operating hour)
        intercept = mean_h - slope * mean_t

        # Calculate R^2 goodness of fit and standard error of slope
        ss_tot = sum((h - mean_h) ** 2 for h in h_vals)
        fitted_vals = [intercept + slope * t for t in t_vals]
        ss_res = sum((h - y_hat) ** 2 for h, y_hat in zip(h_vals, fitted_vals))

        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0.0 else 0.0
        r_squared = max(0.0, min(1.0, r_squared))

        # Standard error of the slope
        variance_res = ss_res / max(1, n - 2)
        s_slope = math.sqrt(variance_res / ss_tt)

        deg_rate_1000h = round(-slope * 1000.0, 2)  # Positive number = loss per 1000h

        # ---------------------------------------------------------------------
        # 3. Slope and Goodness-of-Fit Validation
        # ---------------------------------------------------------------------
        if slope >= -0.00001:
            # Asset is not currently undergoing active health degradation
            return RULPrediction(
                predicted_rul_hours=None,
                rul_confidence_interval=(0.0, 0.0),
                failure_probability_30d=pf_30d,
                evidence_sufficiency=EvidenceSufficiency.SUFFICIENT,
                uncertainty_flag=False,
                degradation_rate_per_1000h=0.0,
                r_squared=round(r_squared, 4),
                model_name=cls.MODEL_NAME,
                explanation="Asset exhibits stable health condition (zero negative degradation slope). Normal O&M scheduling."
            )

        delta_h = current_health - eol_threshold
        if delta_h <= 0.0:
            # Asset has already crossed or reached EOL threshold
            return RULPrediction(
                predicted_rul_hours=0.0,
                rul_confidence_interval=(0.0, 0.0),
                failure_probability_30d=1.0,
                evidence_sufficiency=EvidenceSufficiency.SUFFICIENT,
                uncertainty_flag=False,
                degradation_rate_per_1000h=deg_rate_1000h,
                r_squared=round(r_squared, 4),
                model_name=cls.MODEL_NAME,
                explanation="Asset has reached critical End-of-Life threshold (Health <= 30.0). Immediate maintenance required."
            )

        # ---------------------------------------------------------------------
        # 4. RUL Point Estimate and 90% Confidence Interval
        # ---------------------------------------------------------------------
        abs_slope = abs(slope)
        rul_point = delta_h / abs_slope

        # Critical value t_crit = 1.645 (90% two-sided normal / t-distribution approximation)
        t_crit = 1.645
        rul_lower = delta_h / (abs_slope + t_crit * s_slope)
        rul_upper = delta_h / max(0.00001, abs_slope - t_crit * s_slope)

        # Classify sufficiency based on R^2
        if r_squared >= 0.70:
            sufficiency = EvidenceSufficiency.SUFFICIENT
            uncertainty = False
            expl = (
                f"Statistically validated degradation trajectory (R2={r_squared:.2f}, Rate={deg_rate_1000h:.1f} pts/1000h). "
                f"Predicted RUL: {rul_point:.0f} hours [{rul_lower:.0f}h - {rul_upper:.0f}h 90% CI]."
            )
        else:
            sufficiency = EvidenceSufficiency.PARTIAL
            uncertainty = True
            expl = (
                f"Emerging degradation trend with moderate fit (R2={r_squared:.2f} < 0.70). "
                f"Estimated RUL: {rul_point:.0f} hours with wide uncertainty [{rul_lower:.0f}h - {rul_upper:.0f}h]. "
                "Monitor for trajectory stabilization."
            )

        return RULPrediction(
            predicted_rul_hours=round(rul_point, 1),
            rul_confidence_interval=(round(rul_lower, 1), round(rul_upper, 1)),
            failure_probability_30d=pf_30d,
            evidence_sufficiency=sufficiency,
            uncertainty_flag=uncertainty,
            degradation_rate_per_1000h=deg_rate_1000h,
            r_squared=round(r_squared, 4),
            model_name=cls.MODEL_NAME,
            explanation=expl
        )
