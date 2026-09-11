"""
REAMP Governance Engine.
Orchestrates AI Decision Records, data provenance tracing, model version registry,
configuration change auditing, and regulatory compliance categorization.
"""

from typing import Dict, Any, List, Optional, Set
import datetime
import hashlib
import uuid
import copy

from reamp.governance.models import (
    ComplianceCategory,
    ComplianceRequirement,
    DecisionStatus,
    ModelVersionRecord,
    ConfigChangeRecord,
    DataProvenanceNode,
    AIDecisionRecord,
)
from reamp.security.audit import TamperEvidentAuditLogger


class GovernanceEngine:
    """
    Central governance manager ensuring trustworthy, explainable, and compliant AI operations.
    Enforces the 8-stage AI Decision Record, maintains provenance DAGs, and audits configuration changes.
    """

    def __init__(self, audit_logger: Optional[TamperEvidentAuditLogger] = None) -> None:
        self.audit_logger = audit_logger or TamperEvidentAuditLogger()
        self.models: Dict[str, ModelVersionRecord] = {}  # key: f"{name}:{version}"
        self.decision_records: Dict[str, AIDecisionRecord] = {}
        self.config_changes: Dict[str, ConfigChangeRecord] = {}
        self.provenance_nodes: Dict[str, DataProvenanceNode] = {}
        self.compliance_requirements: Dict[str, ComplianceRequirement] = {}

        self._initialize_default_compliance_catalog()

    # -------------------------------------------------------------------------
    # 1. Model & Algorithm Version Registry
    # -------------------------------------------------------------------------

    def register_model_version(
        self,
        model_name: str,
        version: str,
        algorithm_type: str,
        sha256_digest: str,
        hyperparameters: Optional[Dict[str, Any]] = None,
        trained_date: Optional[str] = None,
    ) -> ModelVersionRecord:
        """Registers an AI/ML algorithm or model version with cryptographic digest."""
        key = f"{model_name}:{version}"
        model_id = f"MOD-{uuid.uuid4().hex[:8].upper()}"
        now_str = trained_date or datetime.datetime.now(datetime.timezone.utc).isoformat()

        record = ModelVersionRecord(
            model_id=model_id,
            model_name=model_name,
            version=version,
            algorithm_type=algorithm_type,
            trained_date=now_str,
            sha256_digest=sha256_digest,
            hyperparameters=hyperparameters or {},
            is_active=True,
        )

        self.models[key] = record
        self.audit_logger.append_entry(
            actor_id="SYS-ADMIN",
            tenant_id="SYSTEM",
            action="REGISTER_MODEL_VERSION",
            resource_id=key,
            details={"model_id": model_id, "digest": sha256_digest},
        )
        return record

    def get_model_version(self, model_name: str, version: str) -> Optional[ModelVersionRecord]:
        """Retrieves a registered model version record."""
        return self.models.get(f"{model_name}:{version}")

    # -------------------------------------------------------------------------
    # 2. Data Provenance Graph (DAG)
    # -------------------------------------------------------------------------

    def record_provenance_node(
        self,
        data_type: str,
        source_id: str,
        payload_checksum: str,
        parent_node_ids: Optional[List[str]] = None,
        transformation_step: str = "",
        timestamp: Optional[str] = None,
    ) -> DataProvenanceNode:
        """Adds a node to the data lineage DAG."""
        node_id = f"PROV-{uuid.uuid4().hex[:10].upper()}"
        ts = timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat()

        node = DataProvenanceNode(
            node_id=node_id,
            data_type=data_type,
            source_id=source_id,
            timestamp=ts,
            payload_checksum=payload_checksum,
            parent_node_ids=parent_node_ids or [],
            transformation_step=transformation_step,
        )
        self.provenance_nodes[node_id] = node
        return node

    def trace_upstream_provenance(self, start_node_id: str) -> List[DataProvenanceNode]:
        """
        Traverses upstream from a decision or anomaly node back to original sensor inputs.
        Breadth-first search over parent links.
        """
        visited: Set[str] = set()
        queue = [start_node_id]
        lineage: List[DataProvenanceNode] = []

        while queue:
            curr_id = queue.pop(0)
            if curr_id in visited or curr_id not in self.provenance_nodes:
                continue
            visited.add(curr_id)
            node = self.provenance_nodes[curr_id]
            lineage.append(node)
            for parent_id in node.parent_node_ids:
                if parent_id not in visited:
                    queue.append(parent_id)

        return lineage

    # -------------------------------------------------------------------------
    # 3. Canonical 8-Stage AI Decision Record
    # -------------------------------------------------------------------------

    def create_ai_decision_record(
        self,
        asset_id: str,
        input_data_summary: Dict[str, Any],
        model_name: str,
        model_version: str,
        raw_output: Dict[str, Any],
        confidence: float,
        evidence_features: Dict[str, float],
        ai_recommendation: str,
        provenance_chain_id: str,
        timestamp: Optional[str] = None,
    ) -> AIDecisionRecord:
        """
        Instantiates the complete 8-stage AI Decision Record:
        Input Data -> Model -> Model Version -> Output -> Confidence -> Evidence -> Recommendation -> Human Decision
        """
        decision_id = f"AIDEC-{uuid.uuid4().hex[:8].upper()}"
        now_str = timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Resolve model digest from registry or compute fallback
        mod_key = f"{model_name}:{model_version}"
        registered_model = self.models.get(mod_key)
        digest = (
            registered_model.sha256_digest
            if registered_model
            else hashlib.sha256(mod_key.encode("utf-8")).hexdigest()
        )

        record = AIDecisionRecord(
            decision_id=decision_id,
            timestamp=now_str,
            asset_id=asset_id,
            provenance_chain_id=provenance_chain_id,
            input_data_summary=input_data_summary,
            model_name=model_name,
            model_version=model_version,
            model_digest=digest,
            raw_output=raw_output,
            confidence=round(confidence, 2),
            evidence_features=evidence_features,
            ai_recommendation=ai_recommendation,
            human_decision=DecisionStatus.PENDING_REVIEW,
        )

        self.decision_records[decision_id] = record

        self.audit_logger.append_entry(
            actor_id=f"AI-MODEL:{model_name}",
            tenant_id="SYSTEM",
            action="CREATE_AI_DECISION_RECORD",
            resource_id=decision_id,
            details={"asset_id": asset_id, "confidence": confidence, "recommendation": ai_recommendation},
        )
        return record

    def record_human_decision(
        self,
        decision_id: str,
        decision: DecisionStatus,
        human_actor_id: str,
        decision_notes: str = "",
        timestamp: Optional[str] = None,
    ) -> AIDecisionRecord:
        """
        Closes the loop by capturing explicit human authorization on an AI Decision Record.
        """
        record = self.decision_records.get(decision_id)
        if not record:
            raise ValueError(f"AI Decision Record '{decision_id}' not found.")

        now_str = timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat()
        record.human_decision = decision
        record.human_actor_id = human_actor_id
        record.decision_timestamp = now_str
        record.decision_notes = decision_notes

        self.audit_logger.append_entry(
            actor_id=human_actor_id,
            tenant_id="SYSTEM",
            action="HUMAN_OVERSIGHT_DECISION",
            resource_id=decision_id,
            details={"decision": decision.value, "notes": decision_notes},
        )
        return record

    # -------------------------------------------------------------------------
    # 4. Configuration Change Auditing
    # -------------------------------------------------------------------------

    def record_config_change(
        self,
        actor_id: str,
        tenant_id: str,
        target_setting: str,
        old_value: Any,
        new_value: Any,
        approval_id: str,
        justification: str,
        timestamp: Optional[str] = None,
    ) -> ConfigChangeRecord:
        """Audits a change to plant safety limits or algorithm configuration."""
        change_id = f"CFG-{uuid.uuid4().hex[:8].upper()}"
        now_str = timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat()

        record = ConfigChangeRecord(
            change_id=change_id,
            timestamp=now_str,
            actor_id=actor_id,
            tenant_id=tenant_id,
            target_setting=target_setting,
            old_value=old_value,
            new_value=new_value,
            approval_id=approval_id,
            justification=justification,
        )

        self.config_changes[change_id] = record
        self.audit_logger.append_entry(
            actor_id=actor_id,
            tenant_id=tenant_id,
            action="CONFIG_CHANGE",
            resource_id=target_setting,
            details={"old": str(old_value), "new": str(new_value), "justification": justification},
        )
        return record

    # -------------------------------------------------------------------------
    # 5. Regulatory & Compliance Governance Catalog
    # -------------------------------------------------------------------------

    def _initialize_default_compliance_catalog(self) -> None:
        """Initializes the baseline compliance requirement catalog."""
        # 1. Legal Requirements
        self.register_compliance_requirement(
            req_id="REG-EU-AIACT-01",
            title="EU AI Act High-Risk System Human Oversight",
            category=ComplianceCategory.LEGAL_REQUIREMENT,
            jurisdiction="European Union",
            standard_reference="EU AI Act (Regulation 2024/1689), Article 14",
            description="High-risk AI systems must support human-in-the-loop oversight to prevent autonomous harm.",
            technical_control="reamp.security.auth.AuthorizationManager + reamp.cmms.workflow HITL Gating",
        )
        self.register_compliance_requirement(
            req_id="REG-NERC-CIP-01",
            title="NERC CIP Configuration Change Management",
            category=ComplianceCategory.LEGAL_REQUIREMENT,
            jurisdiction="North America (FERC/NERC)",
            standard_reference="NERC CIP-010-3 R1",
            description="Mandatory baseline change logging and verification for bulk electric control systems.",
            technical_control="reamp.governance.engine.ConfigChangeRecord + TamperEvidentAuditLogger",
        )

        # 2. Industry Practices
        self.register_compliance_requirement(
            req_id="STD-IEC-61724-01",
            title="IEC 61724-1 Photovoltaic System Performance Monitoring",
            category=ComplianceCategory.INDUSTRY_PRACTICE,
            jurisdiction="Global",
            standard_reference="IEC 61724-1:2021",
            description="Standardized formulas for reference yield, performance ratio, and temperature compensation.",
            technical_control="reamp.performance.solar IEC 61724-1 model",
        )
        self.register_compliance_requirement(
            req_id="STD-IEC-62443-01",
            title="IEC 62443 Industrial Automation Security Zones & Conduits",
            category=ComplianceCategory.INDUSTRY_PRACTICE,
            jurisdiction="Global",
            standard_reference="IEC 62443-3-3",
            description="Segmentation of control channels from general IT and telemetry collection networks.",
            technical_control="reamp.security network segmentation & TLS 1.3 reverse proxy",
        )

        # 3. Recommended Controls
        self.register_compliance_requirement(
            req_id="REC-DUAL-AUTH-01",
            title="Dual-Authorization for High-Voltage Setpoints",
            category=ComplianceCategory.RECOMMENDED_CONTROL,
            jurisdiction="Global",
            standard_reference="Energy Cyber Best Practice Guide 2023",
            description="Two authorized operators must sign off before supervisory trip limits are elevated.",
            technical_control="reamp.governance.engine dual approval gating",
        )
        self.register_compliance_requirement(
            req_id="REC-SHAP-EXPLAIN-01",
            title="Continuous Mathematical Feature Attribution",
            category=ComplianceCategory.RECOMMENDED_CONTROL,
            jurisdiction="Global",
            standard_reference="NIST AI Risk Management Framework 1.0",
            description="Every anomaly detection must isolate mathematical percentage contributions.",
            technical_control="reamp.risk.engine.explain_prioritization + AIDecisionRecord.evidence_features",
        )

        # 4. Project Design Decisions
        self.register_compliance_requirement(
            req_id="PRJ-PURE-PYTHON-01",
            title="Pure Python Core without Compiled C-Dependencies",
            category=ComplianceCategory.PROJECT_DESIGN_DECISION,
            jurisdiction="Internal Architecture",
            standard_reference="REAMP Global Operating Contract (AGENTS.md)",
            description="Implementation in pure Python 3.12 with numpy; no scipy/sklearn binaries.",
            technical_control="reamp algorithmic implementations",
        )
        self.register_compliance_requirement(
            req_id="PRJ-DETERMINISTIC-FIRST-01",
            title="Deterministic Physical Models Prior to Stochastic ML",
            category=ComplianceCategory.PROJECT_DESIGN_DECISION,
            jurisdiction="Internal Architecture",
            standard_reference="REAMP Global Operating Contract (AGENTS.md)",
            description="Deterministic physical and statistical rules precede black-box machine learning.",
            technical_control="reamp.health.deterministic and reamp.digital_twin physics models",
        )

    def register_compliance_requirement(
        self,
        req_id: str,
        title: str,
        category: ComplianceCategory,
        jurisdiction: str,
        standard_reference: str,
        description: str,
        technical_control: str,
    ) -> ComplianceRequirement:
        """Registers a categorized regulatory, industry, or project requirement."""
        req = ComplianceRequirement(
            req_id=req_id,
            title=title,
            category=category,
            jurisdiction=jurisdiction,
            standard_reference=standard_reference,
            description=description,
            technical_control=technical_control,
        )
        self.compliance_requirements[req_id] = req
        return req

    def get_compliance_requirements(
        self,
        category: Optional[ComplianceCategory] = None,
    ) -> List[ComplianceRequirement]:
        """Retrieves requirements filtered by category."""
        if category is None:
            return list(self.compliance_requirements.values())
        return [r for r in self.compliance_requirements.values() if r.category == category]

    def audit_compliance_catalog(self) -> Dict[str, Any]:
        """Summarizes requirements across the four strict categories."""
        summary: Dict[str, int] = {
            ComplianceCategory.LEGAL_REQUIREMENT.value: 0,
            ComplianceCategory.INDUSTRY_PRACTICE.value: 0,
            ComplianceCategory.RECOMMENDED_CONTROL.value: 0,
            ComplianceCategory.PROJECT_DESIGN_DECISION.value: 0,
        }
        for req in self.compliance_requirements.values():
            summary[req.category.value] += 1

        return {
            "total_requirements": len(self.compliance_requirements),
            "breakdown": summary,
        }
