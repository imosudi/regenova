"""
REAMP MVP — Programmatic API Facade.

Provides a clean, uniform interface for external SCADA, IoT edge gateways,
and management web applications to interact with the REAMP MVP runtime.
"""

from typing import Dict, List, Optional, Any
from dataclasses import asdict
import datetime

from reamp.mvp.orchestrator import REAMPApplicationMVP
from reamp.mvp.models import AlertStatus
from reamp.security.models import UserIdentity, SecurityRole, TelemetryPacketSignature


class REAMPAppAPI:
    """
    Programmatic REST-like API facade over the central REAMP Application MVP.
    """

    def __init__(self, app: REAMPApplicationMVP) -> None:
        self.app = app

    # =========================================================================
    # Authentication & Security
    # =========================================================================

    def authenticate(
        self,
        client_id: str,
        role: SecurityRole = SecurityRole.OPERATOR,
        tenant_id: Optional[str] = None,
    ) -> str:
        """Issues an authenticated HMAC-signed bearer token for client operations."""
        t_id = tenant_id or self.app.tenant_id
        identity = UserIdentity(
            user_id=client_id,
            username=client_id,
            tenant_id=t_id,
            role=role,
        )
        token_obj = self.app.auth_manager.generate_token(identity)
        import json
        return json.dumps(token_obj.to_dict())

    def _validate_token(self, auth_token: Optional[Any]) -> UserIdentity:
        """Validates incoming token and returns authenticated user identity."""
        if not auth_token:
            raise PermissionError("Authorization required: No bearer token provided.")
        import json
        from reamp.security.models import SecurityToken, Permission
        if isinstance(auth_token, SecurityToken):
            token_obj = auth_token
        elif isinstance(auth_token, str):
            try:
                data = json.loads(auth_token)
                token_obj = SecurityToken(
                    token_id=data["token_id"],
                    subject_id=data["subject_id"],
                    tenant_id=data["tenant_id"],
                    role=SecurityRole(data["role"]),
                    permissions=[Permission(p) for p in data.get("permissions", [])],
                    issued_at=data["issued_at"],
                    expires_at=data["expires_at"],
                    signature=data["signature"],
                )
            except Exception as e:
                raise PermissionError(f"Malformed authentication token: {e}")
        else:
            raise PermissionError("Invalid token format.")
        return self.app.auth_manager.verify_token(token_obj)

    # =========================================================================
    # Telemetry Ingestion
    # =========================================================================

    def ingest_telemetry(
        self,
        asset_id: str,
        telemetry_data: Dict[str, float],
        auth_token: Optional[str] = None,
        packet_signature: Optional[TelemetryPacketSignature] = None,
        timestamp: Optional[datetime.datetime] = None,
    ) -> Dict[str, Any]:
        """Ingests raw or signed edge telemetry through the complete 10-stage pipeline."""
        if auth_token:
            self._validate_token(auth_token)

        return self.app.process_telemetry_packet(
            asset_id=asset_id,
            telemetry=telemetry_data,
            timestamp=timestamp,
            packet_signature=packet_signature,
        )

    # =========================================================================
    # Unified Dashboard State
    # =========================================================================

    def get_unified_dashboard(
        self,
        site_id: str,
        auth_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieves aggregated plant telemetry, active alarms, and work orders."""
        if auth_token:
            self._validate_token(auth_token)

        dashboard = self.app.get_unified_dashboard(site_id=site_id)
        return asdict(dashboard)

    # =========================================================================
    # Real-Time Alerts
    # =========================================================================

    def get_alerts(
        self,
        site_id: Optional[str] = None,
        status: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries active or historical alarms."""
        if auth_token:
            self._validate_token(auth_token)

        results = []
        for a in self.app.alerts.values():
            if site_id and a.site_id != site_id:
                continue
            if status and a.status.value != status:
                continue
            results.append(asdict(a))
        return results

    def acknowledge_alert(self, alert_id: str, auth_token: str) -> Dict[str, Any]:
        """Marks an alert as acknowledged by the calling operator."""
        user = self._validate_token(auth_token)
        alert = self.app.acknowledge_alert(alert_id=alert_id, acknowledged_by=user.user_id)
        return asdict(alert)

    def resolve_alert(self, alert_id: str, auth_token: str) -> Dict[str, Any]:
        """Marks an alert as resolved."""
        user = self._validate_token(auth_token)
        alert = self.app.resolve_alert(alert_id=alert_id, resolved_by=user.user_id)
        return asdict(alert)

    # =========================================================================
    # CMMS Work Orders & HITL Operations
    # =========================================================================

    def get_work_orders(
        self,
        site_id: Optional[str] = None,
        status: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lists maintenance work orders."""
        if auth_token:
            self._validate_token(auth_token)

        site_asset_ids = {a.asset_id for a in self.app.assets.values() if not site_id or a.site_id == site_id}
        wos = []
        for wo in self.app.cmms_engine.work_orders.values():
            if wo.asset_id in site_asset_ids:
                if status and wo.status.value != status:
                    continue
                wos.append(asdict(wo))
        return wos

    def approve_work_order(self, work_order_id: str, auth_token: str, notes: str = "") -> Dict[str, Any]:
        """Executes human-in-the-loop authorization to approve a draft work order."""
        user = self._validate_token(auth_token)
        wo = self.app.approve_work_order(
            work_order_id=work_order_id,
            approved_by=user.user_id,
            notes=notes,
        )
        return asdict(wo)

    def reserve_parts(self, work_order_id: str, auth_token: str) -> Dict[str, Any]:
        """Reserves required parts from inventory for an approved work order."""
        self._validate_token(auth_token)
        wo = self.app.reserve_parts_for_work_order(work_order_id=work_order_id)
        return asdict(wo)

    def dispatch_work_order(self, work_order_id: str, technician_id: str, auth_token: str) -> Dict[str, Any]:
        """Dispatches an approved work order with allocated parts to a qualified technician."""
        self._validate_token(auth_token)
        wo = self.app.dispatch_work_order(work_order_id=work_order_id, technician_id=technician_id)
        return asdict(wo)

    def complete_work_order(
        self,
        work_order_id: str,
        auth_token: str,
        notes: str = "",
        labor_hours: float = 2.0,
    ) -> Dict[str, Any]:
        """Marks maintenance work completed."""
        self._validate_token(auth_token)
        wo = self.app.complete_work_order(work_order_id=work_order_id, notes=notes, labor_hours=labor_hours)
        return asdict(wo)

    def close_work_order(self, work_order_id: str, auth_token: str) -> Dict[str, Any]:
        """Closes work order and finalizes full audit history."""
        user = self._validate_token(auth_token)
        wo = self.app.close_work_order(work_order_id=work_order_id, closed_by=user.user_id)
        return asdict(wo)

    # =========================================================================
    # Executive & Audit Governance
    # =========================================================================

    def get_executive_report(
        self,
        site_id: str,
        auth_token: Optional[str] = None,
        period_start: Optional[datetime.datetime] = None,
        period_end: Optional[datetime.datetime] = None,
    ) -> Dict[str, Any]:
        """Compiles the Executive Decision and Performance Report."""
        if auth_token:
            self._validate_token(auth_token)

        rep = self.app.generate_executive_report(
            site_id=site_id,
            period_start=period_start,
            period_end=period_end,
        )
        return asdict(rep)

    def verify_audit_trail(self, auth_token: Optional[str] = None) -> Dict[str, Any]:
        """Verifies cryptographic SHA-256 hash chaining across the entire system audit trail."""
        if auth_token:
            self._validate_token(auth_token)

        valid, broken_idx = self.app.audit_logger.verify_chain_integrity()
        chain = self.app.audit_logger.get_entries()
        return {
            "is_valid": valid,
            "total_entries": len(chain),
            "broken_entry_index": broken_idx,
            "genesis_hash": self.app.audit_logger.GENESIS_HASH,
            "latest_hash": chain[-1].entry_hash if chain else self.app.audit_logger.GENESIS_HASH,
        }
