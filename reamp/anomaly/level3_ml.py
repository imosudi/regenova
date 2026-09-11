"""
REAMP Level 3 Anomaly Detector: Unsupervised Machine Learning Engine.
Production-grade, zero-C-dependency Isolation Forest implemented with pure Python / NumPy.
Conforms to Liu, Ting, Zhou (2008) "Isolation Forest", IEEE ICDM.
"""

import math
import uuid
import datetime
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from reamp.anomaly.models import (
    AnomalyObject,
    AnomalyType,
    AnomalySeverity,
    Level3MLConfig
)


def _c_factor(n: int) -> float:
    """Average path length of unsuccessful searches in a Binary Search Tree."""
    if n <= 1:
        return 0.0
    if n == 2:
        return 1.0
    euler_mascheroni = 0.5772156649
    return 2.0 * (math.log(n - 1) + euler_mascheroni) - (2.0 * (n - 1) / n)


class _IsolationTreeNode:
    """Node in an Isolation Tree."""
    def __init__(
        self,
        is_leaf: bool = False,
        size: int = 0,
        split_feature: int = -1,
        split_value: float = 0.0,
        left: Optional["_IsolationTreeNode"] = None,
        right: Optional["_IsolationTreeNode"] = None
    ):
        self.is_leaf = is_leaf
        self.size = size
        self.split_feature = split_feature
        self.split_value = split_value
        self.left = left
        self.right = right


class IsolationTree:
    """Single randomized isolation tree partitioning feature space."""

    def __init__(self, max_depth: int, rng: np.random.Generator):
        self.max_depth = max_depth
        self.rng = rng
        self.root: Optional[_IsolationTreeNode] = None

    def fit(self, X: np.ndarray):
        self.root = self._build_tree(X, depth=0)
        return self

    def _build_tree(self, X: np.ndarray, depth: int) -> _IsolationTreeNode:
        n_samples, n_features = X.shape
        if depth >= self.max_depth or n_samples <= 1:
            return _IsolationTreeNode(is_leaf=True, size=n_samples)

        # Randomly choose a feature with non-zero variance
        valid_features = [f for f in range(n_features) if np.min(X[:, f]) < np.max(X[:, f])]
        if not valid_features:
            return _IsolationTreeNode(is_leaf=True, size=n_samples)

        feature = int(self.rng.choice(valid_features))
        min_val = float(np.min(X[:, feature]))
        max_val = float(np.max(X[:, feature]))
        split_val = float(self.rng.uniform(min_val, max_val))

        left_mask = X[:, feature] < split_val
        right_mask = ~left_mask

        if np.sum(left_mask) == 0 or np.sum(right_mask) == 0:
            return _IsolationTreeNode(is_leaf=True, size=n_samples)

        left_child = self._build_tree(X[left_mask], depth + 1)
        right_child = self._build_tree(X[right_mask], depth + 1)

        return _IsolationTreeNode(
            is_leaf=False,
            size=n_samples,
            split_feature=feature,
            split_value=split_val,
            left=left_child,
            right=right_child
        )

    def path_length(self, x: np.ndarray) -> float:
        node = self.root
        depth = 0.0
        while node is not None and not node.is_leaf:
            if x[node.split_feature] < node.split_value:
                node = node.left
            else:
                node = node.right
            depth += 1.0

        if node is not None and node.size > 1:
            return depth + _c_factor(node.size)
        return depth


class Level3MLDetector:
    """Multi-variate unsupervised Isolation Forest anomaly detector."""

    MODEL_VERSION = "1.0.0-phase8"

    def __init__(self, config: Optional[Level3MLConfig] = None):
        self.config = config or Level3MLConfig()
        self.rng = np.random.default_rng(self.config.random_seed)
        self.trees: List[IsolationTree] = []
        self.feature_names = [
            "irradiance_poa_wm2",
            "actual_power_kw",
            "voltage_ac_v",
            "current_ac_a",
            "temperature_cell_max_c",
            "temperature_heatsink_c"
        ]
        self.sub_sample_size = self.config.sub_sample_size
        self.c_n = _c_factor(self.sub_sample_size)
        self.is_fitted = False
        self.feature_medians: np.ndarray = np.zeros(len(self.feature_names))
        self.feature_iqrs: np.ndarray = np.ones(len(self.feature_names))

        # Train on canonical nominal baseline distribution
        self._fit_default_baseline()

    def _fit_default_baseline(self):
        """Fit the isolation forest ensemble on a synthetic nominal multi-variate baseline."""
        n_samples = 300
        # Diurnal distribution under nominal operation
        g_poa = self.rng.uniform(200.0, 1000.0, n_samples)
        # AC power: ~ 0.8 * g_poa with slight thermal noise
        p_ac = 0.8 * g_poa + self.rng.normal(0, 10.0, n_samples)
        v_ac = self.rng.normal(480.0, 4.0, n_samples)
        i_ac = (p_ac * 1000.0) / (math.sqrt(3) * v_ac * 0.99)
        t_cell = 25.0 + (g_poa / 800.0) * 25.0 + self.rng.normal(0, 2.0, n_samples)
        t_hs = 35.0 + 35.0 * ((p_ac / 800.0) ** 2) + self.rng.normal(0, 2.0, n_samples)

        X_train = np.column_stack([g_poa, p_ac, v_ac, i_ac, t_cell, t_hs])
        self.fit(X_train)

    def fit(self, X: np.ndarray):
        """Train the ensemble of Isolation Trees."""
        n_samples = len(X)
        sub_sample = min(self.config.sub_sample_size, n_samples)
        max_depth = int(math.ceil(math.log2(max(sub_sample, 2))))
        self.c_n = _c_factor(sub_sample)

        self.trees = []
        for _ in range(self.config.n_trees):
            indices = self.rng.choice(n_samples, size=sub_sample, replace=False)
            tree = IsolationTree(max_depth=max_depth, rng=self.rng)
            tree.fit(X[indices])
            self.trees.append(tree)

        self.feature_medians = np.median(X, axis=0)
        q75, q25 = np.percentile(X, [75, 25], axis=0)
        self.feature_iqrs = np.maximum(q75 - q25, 1e-4)
        self.is_fitted = True

    def score_sample(self, x: np.ndarray) -> float:
        """Compute normalized anomaly score s in [0.0, 1.0]."""
        if not self.is_fitted or not self.trees or self.c_n <= 0:
            return 0.50

        avg_path_length = sum(t.path_length(x) for t in self.trees) / len(self.trees)
        score = 2.0 ** (- (avg_path_length / self.c_n))
        return round(float(score), 4)

    def attribute_features(self, x: np.ndarray) -> Tuple[str, float]:
        """Isolate dominant driving feature using robust median/IQR deviation."""
        deviations = np.abs(x - self.feature_medians) / self.feature_iqrs
        dominant_idx = int(np.argmax(deviations))
        return self.feature_names[dominant_idx], round(float(deviations[dominant_idx]), 2)

    def evaluate(
        self,
        asset_id: str,
        telemetry: Dict[str, Any],
        timestamp_str: Optional[str] = None
    ) -> List[AnomalyObject]:
        """Evaluate multivariate telemetry instance using the trained Isolation Forest."""
        now_str = timestamp_str or datetime.datetime.now(datetime.timezone.utc).isoformat()
        conf = float(telemetry.get("confidence", 1.0))

        # Inverters operate in standby / waking mode below operational irradiance threshold
        g_poa = telemetry.get("irradiance_poa_wm2")
        if g_poa is not None and float(g_poa) < 150.0:
            return []

        # Extract features
        row = []
        for fname in self.feature_names:
            val = telemetry.get(fname)
            if val is None or not isinstance(val, (int, float)):
                # Missing telemetry dimension suppresses Level 3 ML evaluation
                return []
            row.append(float(val))

        x_vec = np.array(row, dtype=float)
        score = self.score_sample(x_vec)

        if score >= self.config.anomaly_threshold:
            dominant_feature, dev_ratio = self.attribute_features(x_vec)
            sev = AnomalySeverity.CRITICAL if score >= 0.80 else AnomalySeverity.HIGH if score >= 0.70 else AnomalySeverity.MEDIUM

            return [
                AnomalyObject(
                    anomaly_id=f"ANOM-L3-IFOREST-{uuid.uuid4().hex[:8]}",
                    asset_id=asset_id,
                    timestamp=now_str,
                    type=AnomalyType.ML_ISOLATION_FOREST,
                    severity=sev,
                    score=score,
                    evidence={
                        "anomaly_score": score,
                        "threshold": self.config.anomaly_threshold,
                        "dominant_feature": dominant_feature,
                        "deviation_ratio_iqr": dev_ratio,
                        "feature_vector": {fn: round(row[i], 2) for i, fn in enumerate(self.feature_names)}
                    },
                    confidence=conf,
                    detection_method="LEVEL_3_ISOLATION_FOREST",
                    model_version=self.MODEL_VERSION,
                    recommended_action=f"Unsupervised multi-variate anomaly detected (Score={score:.2f}). Dominant feature: {dominant_feature}. Investigate non-linear operating state."
                )
            ]

        return []
