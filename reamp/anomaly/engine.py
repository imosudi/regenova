"""
REAMP Canonical Anomaly Detection Engine.
Central orchestrator coordinating Levels 1–4, applying alert deduplication,
subsumption arbitration, and emitting standardized Anomaly Objects.
"""

from typing import Dict, Any, List, Optional
from reamp.anomaly.models import (
    AnomalyObject,
    AnomalyType,
    AnomalySeverity,
    Level1RuleConfig,
    Level2StatisticalConfig,
    Level3MLConfig,
    Level4ContextualConfig,
)
from reamp.anomaly.level1_rules import Level1RuleDetector
from reamp.anomaly.level2_statistical import Level2StatisticalDetector
from reamp.anomaly.level3_ml import Level3MLDetector
from reamp.anomaly.level4_contextual import Level4ContextualDetector


class AnomalyDetectionEngine:
    """
    Unified multi-tier anomaly detection engine for renewable energy assets.
    Orchestrates deterministic rules, statistical filters, isolation forests,
    and contextual peer residual analysis.
    """

    MODEL_VERSION = "1.0.0-phase8"

    def __init__(
        self,
        l1_config: Optional[Level1RuleConfig] = None,
        l2_config: Optional[Level2StatisticalConfig] = None,
        l3_config: Optional[Level3MLConfig] = None,
        l4_config: Optional[Level4ContextualConfig] = None
    ):
        self.l1_detector = Level1RuleDetector(l1_config)
        self.l2_detector = Level2StatisticalDetector(l2_config)
        self.l3_detector = Level3MLDetector(l3_config)
        self.l4_detector = Level4ContextualDetector(l4_config)

    def evaluate(
        self,
        asset_id: str,
        telemetry: Dict[str, Any],
        cohort_powers: Optional[Dict[str, float]] = None,
        timestamp_str: Optional[str] = None
    ) -> List[AnomalyObject]:
        """
        Execute comprehensive multi-level anomaly evaluation on a single telemetry record.
        Coordinates Levels 1–4 and applies subsumption arbitration to prevent alarm floods.
        """
        all_anomalies: List[AnomalyObject] = []

        # ---------------------------------------------------------------------
        # 1. Level 1: Deterministic Rules (Thresholds, Shutdown, Comms, Physical)
        # ---------------------------------------------------------------------
        l1_anomalies = self.l1_detector.evaluate(asset_id, telemetry, timestamp_str)
        all_anomalies.extend(l1_anomalies)

        # Check for critical Level 1 condition that subsumes downstream warnings
        has_shutdown = any(a.type == AnomalyType.UNEXPECTED_SHUTDOWN for a in l1_anomalies)
        has_impossible = any(a.type == AnomalyType.IMPOSSIBLE_VALUE for a in l1_anomalies)
        has_comm_loss = any(a.type == AnomalyType.COMMUNICATION_TIMEOUT for a in l1_anomalies)

        # ---------------------------------------------------------------------
        # 2. Level 2: Statistical Filters (Z-Score, EWMA, CUSUM)
        # ---------------------------------------------------------------------
        # Suppress statistical noise if an unexpected trip or impossible value occurred
        if not (has_shutdown or has_impossible or has_comm_loss):
            l2_anomalies = self.l2_detector.evaluate(asset_id, telemetry, timestamp_str)
            all_anomalies.extend(l2_anomalies)

        # ---------------------------------------------------------------------
        # 3. Level 3: Unsupervised Machine Learning (Isolation Forest)
        # ---------------------------------------------------------------------
        if not (has_shutdown or has_impossible or has_comm_loss):
            l3_anomalies = self.l3_detector.evaluate(asset_id, telemetry, timestamp_str)
            all_anomalies.extend(l3_anomalies)

        # ---------------------------------------------------------------------
        # 4. Level 4: Contextual Physical Residuals & Spatial Peer Analysis
        # ---------------------------------------------------------------------
        if not (has_impossible or has_comm_loss):
            # Physical conservation residuals
            l4_residuals = self.l4_detector.evaluate_residuals(asset_id, telemetry, timestamp_str)
            all_anomalies.extend(l4_residuals)

            # Spatial peer cohort analysis
            if cohort_powers is not None and asset_id in cohort_powers:
                conf = float(telemetry.get("confidence", 1.0))
                l4_peers = self.l4_detector.evaluate_cohort_peers(
                    target_asset_id=asset_id,
                    cohort_powers=cohort_powers,
                    timestamp_str=timestamp_str,
                    confidence=conf
                )
                all_anomalies.extend(l4_peers)

        # Sort emitted anomalies by severity descending
        severity_order = {
            AnomalySeverity.CRITICAL: 0,
            AnomalySeverity.HIGH: 1,
            AnomalySeverity.MEDIUM: 2,
            AnomalySeverity.LOW: 3,
            AnomalySeverity.INFO: 4
        }
        all_anomalies.sort(key=lambda a: (severity_order.get(a.severity, 99), -a.score))

        return all_anomalies
