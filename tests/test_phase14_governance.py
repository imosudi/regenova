"""
REAMP Phase 14 Automated Verification Suite - Governance, Compliance and Explainability.
Validates:
1. The Canonical 8-Stage AI Decision Record:
   Input Data -> Model -> Model Version -> Output -> Confidence -> Evidence -> Recommendation -> Human Decision.
2. Data Provenance Graph (DAG) upstream lineage traversal.
3. Model and Algorithm Version Registry with cryptographic digest pinning.
4. Configuration and safety parameter change auditing.
5. Strict regulatory compliance taxonomy:
   - Legal Requirement vs. Industry Practice vs. Recommended Control vs. Project Design Decision.
"""

import os
import sys
import unittest
import datetime

# Ensure reamp package is importable
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reamp.governance.models import (
    ComplianceCategory,
    DecisionStatus,
    AIDecisionRecord,
    DataProvenanceNode,
)
from reamp.governance.engine import GovernanceEngine
from reamp.security.audit import TamperEvidentAuditLogger


class TestPhase14GovernanceAndExplainability(unittest.TestCase):
    """Test suite validating Phase 14 Governance, Compliance and Explainability Framework."""

    def setUp(self):
        """Initializes audit logger and governance engine."""
        self.audit_logger = TamperEvidentAuditLogger()
        self.engine = GovernanceEngine(self.audit_logger)

        # Register reference model
        self.model = self.engine.register_model_version(
            model_name="reamp-cbm-inverter-thermal",
            version="1.4.2",
            algorithm_type="PHYSICAL_RESIDUAL_STATISTICAL",
            sha256_digest="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            hyperparameters={"ewma_alpha": 0.20, "cusum_threshold": 4.0},
        )

    def test_01_canonical_ai_decision_record_lifecycle(self):
        """
        Validates the complete 8-stage AI Decision Record:
        Input Data -> Model -> Model Version -> Output -> Confidence -> Evidence -> Recommendation -> Human Decision.
        """
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # 1. Create Decision Record
        input_data = {
            "telemetry_window": "15m",
            "samples": 30,
            "mean_irradiance_w_m2": 850.0,
            "mean_delta_t_c": 16.4,
            "quality": "VALID",
        }
        raw_output = {
            "failure_probability_30d": 0.42,
            "predicted_rul_hours": 640.0,
            "priority_score": 82.0,
        }
        evidence_features = {
            "temperature_residual_delta_t": 0.55,
            "ambient_heat_index": 0.25,
            "operating_hours": 0.20,
        }
        recommendation = "Dispatch technician Alice Morgan to replace secondary cooling fan FAN-48V-DC-120MM."

        record = self.engine.create_ai_decision_record(
            asset_id="INV-WEST-01",
            input_data_summary=input_data,
            model_name="reamp-cbm-inverter-thermal",
            model_version="1.4.2",
            raw_output=raw_output,
            confidence=0.94,
            evidence_features=evidence_features,
            ai_recommendation=recommendation,
            provenance_chain_id="PROV-NODE-ROOT-001",
            timestamp=now,
        )

        # Verify initial state
        self.assertIsInstance(record, AIDecisionRecord)
        self.assertEqual(record.human_decision, DecisionStatus.PENDING_REVIEW)
        self.assertEqual(record.model_digest, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        self.assertEqual(record.confidence, 0.94)
        self.assertEqual(record.evidence_features["temperature_residual_delta_t"], 0.55)

        # 2. Human Oversight Gate: Chief Engineer signs off
        approved_record = self.engine.record_human_decision(
            decision_id=record.decision_id,
            decision=DecisionStatus.APPROVED,
            human_actor_id="USR-ENG-01 (Lead Eng. Sarah Chen)",
            decision_notes="Confirmed thermal trend under high load; approved fan replacement.",
        )

        # Verify approved state
        self.assertEqual(approved_record.human_decision, DecisionStatus.APPROVED)
        self.assertEqual(approved_record.human_actor_id, "USR-ENG-01 (Lead Eng. Sarah Chen)")
        self.assertIsNotNone(approved_record.decision_timestamp)
        self.assertIn("approved fan replacement", approved_record.decision_notes)

        # Verify audit logger committed both events to hash chain
        entries = self.audit_logger.get_entries()
        self.assertGreaterEqual(len(entries), 2)
        is_intact, _ = self.audit_logger.verify_chain_integrity()
        self.assertTrue(is_intact)

    def test_02_data_provenance_dag_and_traversal(self):
        """
        Constructs a multi-tier data provenance tree and verifies upstream lineage traversal:
        Raw Sensor -> Preprocessing -> Anomaly Detection -> AI Decision Record.
        """
        # Node 1: Raw Pyranometer Sensor
        n1 = self.engine.record_provenance_node(
            data_type="RAW_SENSOR_TELEMETRY",
            source_id="PYRANOMETER-01",
            payload_checksum="sha256-sensor-pyrano-01",
            transformation_step="Raw Modbus polling at 1-second intervals",
        )

        # Node 2: Raw Inverter Temperature Sensor
        n2 = self.engine.record_provenance_node(
            data_type="RAW_SENSOR_TELEMETRY",
            source_id="INVERTER-HS-TEMP-01",
            payload_checksum="sha256-sensor-temp-01",
            transformation_step="Raw PT100 thermocouple measurement",
        )

        # Node 3: Weather-Normalized Residual (depends on n1 and n2)
        n3 = self.engine.record_provenance_node(
            data_type="WEATHER_NORMALIZED_RESIDUAL",
            source_id="PHYSICS_ENGINE_IEC61724",
            payload_checksum="sha256-residual-calc-01",
            parent_node_ids=[n1.node_id, n2.node_id],
            transformation_step="Calculated expected heatsink temperature and delta-T residual",
        )

        # Node 4: Anomaly Detection Event (depends on n3)
        n4 = self.engine.record_provenance_node(
            data_type="ANOMALY_DETECTION_EVENT",
            source_id="reamp-anomaly-l2-ewma",
            payload_checksum="sha256-anomaly-event-01",
            parent_node_ids=[n3.node_id],
            transformation_step="EWMA persistent residual drift detected (Z > 3.0)",
        )

        # Node 5: AI Decision Record (depends on n4)
        n5 = self.engine.record_provenance_node(
            data_type="AI_RECOMMENDATION",
            source_id="reamp-cbm-inverter-thermal",
            payload_checksum="sha256-ai-recommendation-01",
            parent_node_ids=[n4.node_id],
            transformation_step="Generated draft work order recommendation",
        )

        # Trace upstream from n5
        upstream_lineage = self.engine.trace_upstream_provenance(n5.node_id)
        lineage_ids = [node.node_id for node in upstream_lineage]

        # Verify complete upstream lineage includes all ancestor nodes
        self.assertEqual(len(upstream_lineage), 5)
        self.assertIn(n5.node_id, lineage_ids)
        self.assertIn(n4.node_id, lineage_ids)
        self.assertIn(n3.node_id, lineage_ids)
        self.assertIn(n2.node_id, lineage_ids)
        self.assertIn(n1.node_id, lineage_ids)

    def test_03_model_version_registry_and_digest_pinning(self):
        """
        Validates model registration, hyperparameter snapshots, and version retrieval.
        """
        v2 = self.engine.register_model_version(
            model_name="reamp-cbm-inverter-thermal",
            version="2.0.0",
            algorithm_type="MULTIVARIATE_ISOLATION_FOREST",
            sha256_digest="9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
            hyperparameters={"n_trees": 50, "max_depth": 8},
        )
        self.assertEqual(v2.version, "2.0.0")

        fetched = self.engine.get_model_version("reamp-cbm-inverter-thermal", "2.0.0")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.sha256_digest, "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08")

    def test_04_config_change_auditing(self):
        """
        Validates change control auditing for plant safety thresholds and settings.
        """
        change = self.engine.record_config_change(
            actor_id="USR-ENG-01",
            tenant_id="TENANT-ALPHA",
            target_setting="INVERTER_TRIP_TEMP_C",
            old_value=95.0,
            new_value=92.0,  # Lowering trip temp for summer safety
            approval_id="APPR-CHG-2026-001",
            justification="Precautionary seasonal derating for high summer heatwave.",
        )

        self.assertEqual(change.target_setting, "INVERTER_TRIP_TEMP_C")
        self.assertEqual(change.old_value, 95.0)
        self.assertEqual(change.new_value, 92.0)

        # Audit chain must remain valid
        is_intact, _ = self.audit_logger.verify_chain_integrity()
        self.assertTrue(is_intact)

    def test_05_regulatory_compliance_categorization(self):
        """
        Prompt Mandate:
        "Identify applicable legal, regulatory and industry requirements based on the deployment jurisdiction.
         Do not invent compliance claims.
         Clearly distinguish: legal requirement, industry practice, recommended control, project design decision."
        """
        catalog = self.engine.audit_compliance_catalog()

        # Check total requirement counts
        self.assertGreaterEqual(catalog["total_requirements"], 8)
        breakdown = catalog["breakdown"]

        # 1. Legal Requirements exist and are non-zero
        self.assertGreater(breakdown[ComplianceCategory.LEGAL_REQUIREMENT.value], 0)
        legal_reqs = self.engine.get_compliance_requirements(ComplianceCategory.LEGAL_REQUIREMENT)
        legal_titles = [r.title for r in legal_reqs]
        self.assertTrue(any("EU AI Act" in t for t in legal_titles))
        self.assertTrue(any("NERC CIP" in t for t in legal_titles))

        # 2. Industry Practices exist
        self.assertGreater(breakdown[ComplianceCategory.INDUSTRY_PRACTICE.value], 0)
        ind_reqs = self.engine.get_compliance_requirements(ComplianceCategory.INDUSTRY_PRACTICE)
        ind_titles = [r.title for r in ind_reqs]
        self.assertTrue(any("IEC 61724" in t for t in ind_titles))

        # 3. Recommended Controls exist
        self.assertGreater(breakdown[ComplianceCategory.RECOMMENDED_CONTROL.value], 0)

        # 4. Project Design Decisions exist
        self.assertGreater(breakdown[ComplianceCategory.PROJECT_DESIGN_DECISION.value], 0)
        prj_reqs = self.engine.get_compliance_requirements(ComplianceCategory.PROJECT_DESIGN_DECISION)
        prj_titles = [r.title for r in prj_reqs]
        self.assertTrue(any("Pure Python" in t for t in prj_titles))

        # Print catalog summary for report evidence
        print("\n================================================================")
        print("PHASE 14 COMPLIANCE REGISTRY BREAKDOWN:")
        for cat, count in breakdown.items():
            print(f"  {cat}: {count} verified requirements")
        print("================================================================\n")


if __name__ == "__main__":
    unittest.main()
