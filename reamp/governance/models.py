"""
REAMP Governance, Compliance and Explainability Data Models.
Standardized dataclasses and enums for the canonical 8-stage AI Decision Record,
model version registry, configuration change auditing, data provenance graphs,
and categorized regulatory compliance requirements.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, Optional, List
import datetime


class ComplianceCategory(str, Enum):
    """Categorized governance and regulatory requirements."""
    LEGAL_REQUIREMENT = "LEGAL_REQUIREMENT"             # Statutory law (EU AI Act, NERC CIP, NIS2, GDPR)
    INDUSTRY_PRACTICE = "INDUSTRY_PRACTICE"             # Consensus engineering standards (IEC 61724-1, IEC 62443, ISO 55000)
    RECOMMENDED_CONTROL = "RECOMMENDED_CONTROL"         # Security & AI best practices (Dual authorization, continuous SHAP)
    PROJECT_DESIGN_DECISION = "PROJECT_DESIGN_DECISION" # REAMP architectural invariants (Pure Python core, deterministic health first)


class DecisionStatus(str, Enum):
    """Status of human oversight on AI recommendations."""
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"


@dataclass
class ComplianceRequirement:
    """Regulatory or industry compliance control definition."""
    req_id: str
    title: str
    category: ComplianceCategory
    jurisdiction: str
    standard_reference: str
    description: str
    technical_control: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value if isinstance(self.category, ComplianceCategory) else self.category
        return d


@dataclass
class ModelVersionRecord:
    """Registered AI/ML model or algorithmic version with cryptographic weight/code digest."""
    model_id: str
    model_name: str
    version: str
    algorithm_type: str
    trained_date: str
    sha256_digest: str
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConfigChangeRecord:
    """Audited configuration or safety parameter modification."""
    change_id: str
    timestamp: str
    actor_id: str
    tenant_id: str
    target_setting: str
    old_value: Any
    new_value: Any
    approval_id: str
    justification: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DataProvenanceNode:
    """Single node in the directed acyclic graph (DAG) of data lineage."""
    node_id: str
    data_type: str
    source_id: str
    timestamp: str
    payload_checksum: str
    parent_node_ids: List[str] = field(default_factory=list)
    transformation_step: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AIDecisionRecord:
    """
    Canonical 8-Stage AI Decision Record:
    Input Data -> Model -> Model Version -> Output -> Confidence -> Evidence -> Recommendation -> Human Decision
    """
    decision_id: str
    timestamp: str
    asset_id: str
    provenance_chain_id: str
    input_data_summary: Dict[str, Any]
    model_name: str
    model_version: str
    model_digest: str
    raw_output: Dict[str, Any]
    confidence: float
    evidence_features: Dict[str, float]
    ai_recommendation: str
    human_decision: DecisionStatus = DecisionStatus.PENDING_REVIEW
    human_actor_id: Optional[str] = None
    decision_timestamp: Optional[str] = None
    decision_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["human_decision"] = self.human_decision.value if isinstance(self.human_decision, DecisionStatus) else self.human_decision
        return d
