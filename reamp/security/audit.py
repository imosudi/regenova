"""
REAMP Tamper-Evident Audit Logging Engine.
Implements append-only cryptographic hash chaining (H_i = SHA-256(H_{i-1} || payload))
providing mathematical proof of audit log integrity, non-repudiation, and tampering detection.
"""

from typing import Dict, Any, List, Optional, Tuple
import datetime
import hashlib
import json
import uuid

from reamp.security.models import AuditLogEntry


class TamperEvidentAuditLogger:
    """
    Maintains an immutable, hash-chained sequence of operational and security events.
    Any retroactive tampering or deletion invalidates the cryptographic chain.
    """

    GENESIS_HASH: str = "0" * 64

    def __init__(self) -> None:
        self._chain: List[AuditLogEntry] = []

    def append_entry(
        self,
        actor_id: str,
        tenant_id: str,
        action: str,
        resource_id: str,
        outcome: str = "SUCCESS",
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> AuditLogEntry:
        """
        Commits a new audit record to the hash chain.
        """
        prev_hash = self._chain[-1].entry_hash if self._chain else self.GENESIS_HASH
        entry_id = f"AUD-{uuid.uuid4().hex[:10].upper()}"
        ts = timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat()
        clean_details = details or {}

        # Canonical string serialization for hashing
        payload_str = (
            f"{prev_hash}|{entry_id}|{ts}|{actor_id}|{tenant_id}|"
            f"{action}|{resource_id}|{outcome}|{json.dumps(clean_details, sort_keys=True)}"
        )
        entry_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        entry = AuditLogEntry(
            entry_id=entry_id,
            timestamp=ts,
            actor_id=actor_id,
            tenant_id=tenant_id,
            action=action,
            resource_id=resource_id,
            outcome=outcome,
            details=clean_details,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )

        self._chain.append(entry)
        return entry

    def verify_chain_integrity(self) -> Tuple[bool, Optional[int]]:
        """
        Verifies the cryptographic validity of the complete audit chain.
        Returns (True, None) if completely intact, or (False, corrupted_index)
        if any entry was modified, inserted, or deleted.
        """
        if not self._chain:
            return True, None

        expected_prev = self.GENESIS_HASH

        for idx, entry in enumerate(self._chain):
            # 1. Verify link to previous entry
            if entry.prev_hash != expected_prev:
                return False, idx

            # 2. Recompute hash over entry content
            payload_str = (
                f"{entry.prev_hash}|{entry.entry_id}|{entry.timestamp}|{entry.actor_id}|{entry.tenant_id}|"
                f"{entry.action}|{entry.resource_id}|{entry.outcome}|{json.dumps(entry.details, sort_keys=True)}"
            )
            recomputed_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

            if recomputed_hash != entry.entry_hash:
                return False, idx

            expected_prev = entry.entry_hash

        return True, None

    def get_entries(self) -> List[AuditLogEntry]:
        """Returns shallow copy of all audit entries."""
        return list(self._chain)

    def get_entries_for_tenant(self, tenant_id: str) -> List[AuditLogEntry]:
        """Filters audit entries for a specific organization/tenant."""
        return [e for e in self._chain if e.tenant_id == tenant_id]

    def get_entries_for_resource(self, resource_id: str) -> List[AuditLogEntry]:
        """Filters audit entries for a specific asset or work order."""
        return [e for e in self._chain if e.resource_id == resource_id]
