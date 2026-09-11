"""
REAMP Anomaly Detection Data Models.
Standardized dataclasses and enums for multi-level anomaly objects, severities, and configurations.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, Optional, List
import datetime
import uuid


class AnomalyType(str, Enum):
    """Categorization of detected anomalies across Levels 1–4."""
    # Level 1: Rule-based
    THRESHOLD_VIOLATION = "THRESHOLD_VIOLATION"
    UNEXPECTED_SHUTDOWN = "UNEXPECTED_SHUTDOWN"
    COMMUNICATION_TIMEOUT = "COMMUNICATION_TIMEOUT"
    IMPOSSIBLE_VALUE = "IMPOSSIBLE_VALUE"
    # Level 2: Statistical
    STATISTICAL_ZSCORE = "STATISTICAL_ZSCORE"
    STATISTICAL_EWMA = "STATISTICAL_EWMA"
    CHANGE_POINT_CUSUM = "CHANGE_POINT_CUSUM"
    # Level 3: Machine Learning
    ML_ISOLATION_FOREST = "ML_ISOLATION_FOREST"
    # Level 4: Contextual & Multi-Variate
    PHYSICAL_RESIDUAL = "PHYSICAL_RESIDUAL"
    PEER_OUTLIER = "PEER_OUTLIER"


class AnomalySeverity(str, Enum):
    """Operational severity hierarchy for triage and alert prioritization."""
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class AnomalyObject:
    """
    Canonical explainable anomaly record conforming to Phase 8 specification.
    Contains all 10 mandatory attributes plus prescriptive action.
    """
    anomaly_id: str
    asset_id: str
    timestamp: str
    type: AnomalyType
    severity: AnomalySeverity
    score: float                      # Normalized anomaly extremity [0.0, 1.0]
    evidence: Dict[str, Any]          # Detailed metrics, threshold, observed vs expected
    confidence: float                 # Confidence rating [0.0, 1.0] based on sensor quality
    detection_method: str             # Algorithm/method name (e.g. "LEVEL_1_THRESHOLD")
    model_version: str                # Version string of detector model
    recommended_action: str = ""      # Prescriptive operator advice

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["type"] = self.type.value if isinstance(self.type, AnomalyType) else self.type
        d["severity"] = self.severity.value if isinstance(self.severity, AnomalySeverity) else self.severity
        return d


@dataclass
class Level1RuleConfig:
    """Configurable boundaries for deterministic rule-based checks."""
    voltage_ac_max_v: float = 528.0   # +10% over 480V nominal
    voltage_ac_min_v: float = 432.0   # -10% under 480V nominal
    temp_cell_max_c: float = 75.0     # Critical cell temp limit
    temp_heatsink_max_c: float = 85.0 # Inverter IGBT heatsink limit
    current_ac_max_a: float = 1200.0  # Overcurrent protection limit
    shutdown_min_poa_wm2: float = 250.0
    shutdown_max_power_kw: float = 1.0
    comm_timeout_seconds: float = 60.0
    impossible_irradiance_min: float = -5.0
    impossible_irradiance_max: float = 1600.0


@dataclass
class Level2StatisticalConfig:
    """Configurable parameters for statistical filters and change-point detectors."""
    z_threshold: float = 3.0          # 3-sigma outlier limit
    rolling_window: int = 30          # Number of samples for sliding window
    ewma_alpha: float = 0.20          # Smoothing weight factor
    ewma_l_factor: float = 3.0        # Control limit multiplier
    cusum_slack_k: float = 0.5        # Slack allowance in standard deviations
    cusum_threshold_h: float = 5.0    # Decision boundary in standard deviations


@dataclass
class Level3MLConfig:
    """Parameters for Isolation Forest unsupervised machine learning detector."""
    n_trees: int = 50                 # Number of isolation trees in ensemble
    sub_sample_size: int = 64         # Subsample size per tree
    anomaly_threshold: float = 0.58   # Score above which instance is flagged anomalous
    random_seed: int = 42


@dataclass
class Level4ContextualConfig:
    """Parameters for physical residual analysis and peer cohort comparisons."""
    pvi_residual_threshold: float = 0.12 # 12% mismatch between P and V*I
    thermal_k_factor: float = 35.0       # Heatsink rise coefficient
    thermal_residual_threshold_c: float = 20.0
    peer_mad_threshold: float = 3.5      # Modified Z-score threshold for peer outlier
    peer_min_cohort_power_kw: float = 50.0
