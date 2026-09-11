"""
REAMP Cybersecurity Data Models.
Standardized dataclasses and enums for authentication, role-based authorization,
multi-tenant isolation, cryptographic signatures, tamper-evident audit logging,
and security incident reporting.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, Optional, List
import datetime
import uuid


class SecurityRole(str, Enum):
    """Hierarchical security roles for human operators and microservices."""
    VIEWER = "VIEWER"                     # Read-only telemetry and health dashboards
    OPERATOR = "OPERATOR"                 # Acknowledge alerts, view work orders, initiate requests
    CHIEF_ENGINEER = "CHIEF_ENGINEER"     # Full operational control, HITL work order approval
    SECURITY_ADMIN = "SECURITY_ADMIN"     # User management, policy configuration, audit inspection
    SYSTEM_SERVICE = "SYSTEM_SERVICE"     # Automated backend daemon / edge ingestion service


class Permission(str, Enum):
    """Granular operational capabilities."""
    READ_TELEMETRY = "READ_TELEMETRY"
    READ_HEALTH = "READ_HEALTH"
    DISPATCH_WORK_ORDER = "DISPATCH_WORK_ORDER"
    APPROVE_HITL = "APPROVE_HITL"
    MODIFY_CONFIG = "MODIFY_CONFIG"
    ADMIN_USERS = "ADMIN_USERS"
    VIEW_AUDIT_LOGS = "VIEW_AUDIT_LOGS"
    EMIT_TELEMETRY = "EMIT_TELEMETRY"


class ThreatCategory(str, Enum):
    """STRIDE threat classification categories."""
    SPOOFING = "SPOOFING"
    TAMPERING = "TAMPERING"
    REPUDIATION = "REPUDIATION"
    INFORMATION_DISCLOSURE = "INFORMATION_DISCLOSURE"
    DENIAL_OF_SERVICE = "DENIAL_OF_SERVICE"
    ELEVATION_OF_PRIVILEGE = "ELEVATION_OF_PRIVILEGE"


# Default Role-Permission Mappings
DEFAULT_ROLE_PERMISSIONS: Dict[SecurityRole, List[Permission]] = {
    SecurityRole.VIEWER: [
        Permission.READ_TELEMETRY,
        Permission.READ_HEALTH,
    ],
    SecurityRole.OPERATOR: [
        Permission.READ_TELEMETRY,
        Permission.READ_HEALTH,
        Permission.DISPATCH_WORK_ORDER,
    ],
    SecurityRole.CHIEF_ENGINEER: [
        Permission.READ_TELEMETRY,
        Permission.READ_HEALTH,
        Permission.DISPATCH_WORK_ORDER,
        Permission.APPROVE_HITL,
        Permission.MODIFY_CONFIG,
    ],
    SecurityRole.SECURITY_ADMIN: [
        Permission.READ_TELEMETRY,
        Permission.READ_HEALTH,
        Permission.MODIFY_CONFIG,
        Permission.ADMIN_USERS,
        Permission.VIEW_AUDIT_LOGS,
    ],
    SecurityRole.SYSTEM_SERVICE: [
        Permission.READ_TELEMETRY,
        Permission.READ_HEALTH,
        Permission.EMIT_TELEMETRY,
    ],
}


@dataclass
class UserIdentity:
    """Authenticated user or service identity."""
    user_id: str
    username: str
    tenant_id: str
    role: SecurityRole
    permissions: List[Permission] = field(default_factory=list)
    mfa_enabled: bool = True

    def __post_init__(self):
        if not self.permissions and self.role in DEFAULT_ROLE_PERMISSIONS:
            self.permissions = list(DEFAULT_ROLE_PERMISSIONS[self.role])

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "tenant_id": self.tenant_id,
            "role": self.role.value if isinstance(self.role, SecurityRole) else self.role,
            "permissions": [p.value if isinstance(p, Permission) else p for p in self.permissions],
            "mfa_enabled": self.mfa_enabled,
        }


@dataclass
class SecurityToken:
    """Cryptographic API / session token."""
    token_id: str
    subject_id: str
    tenant_id: str
    role: SecurityRole
    permissions: List[Permission]
    issued_at: str
    expires_at: str
    signature: str

    def is_expired(self, current_time: Optional[datetime.datetime] = None) -> bool:
        now = current_time or datetime.datetime.now(datetime.timezone.utc)
        exp_dt = datetime.datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        return now >= exp_dt

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_id": self.token_id,
            "subject_id": self.subject_id,
            "tenant_id": self.tenant_id,
            "role": self.role.value if isinstance(self.role, SecurityRole) else self.role,
            "permissions": [p.value if isinstance(p, Permission) else p for p in self.permissions],
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "signature": self.signature,
        }


@dataclass
class TelemetryPacketSignature:
    """Cryptographic signature guaranteeing edge packet authenticity and non-replay."""
    device_id: str
    timestamp: str
    nonce: str
    payload_hash: str
    signature: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditLogEntry:
    """
    Immutable, hash-chained audit log entry.
    H_i = SHA-256(H_{i-1} || timestamp || actor_id || action || resource_id || outcome)
    """
    entry_id: str
    timestamp: str
    actor_id: str
    tenant_id: str
    action: str
    resource_id: str
    outcome: str  # "SUCCESS", "DENIED", "FAILED"
    details: Dict[str, Any]
    prev_hash: str
    entry_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SecurityIncident:
    """Structured SIEM-compatible security incident alert."""
    incident_id: str
    timestamp: str
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    threat_category: ThreatCategory
    source_ip: str
    actor: str
    description: str
    mitigation_action: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["threat_category"] = self.threat_category.value if isinstance(self.threat_category, ThreatCategory) else self.threat_category
        return d
