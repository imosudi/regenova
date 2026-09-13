"""
REGENOVA Onboarding Manager.
Orchestrates end-to-end user, facility (site), and device (asset/sensor) onboarding
with cryptographic identity generation, RBAC authorization, and tamper-evident audit logging.
"""

import uuid
import secrets
import datetime
from typing import Dict, Any, List, Optional

from reamp.onboarding.models import (
    UserRecord,
    TenantOnboardingRequest,
    TenantRecord,
    FacilityOnboardingRequest,
    DeviceOnboardingRequest,
    OnboardingResult,
)
from reamp.security.models import SecurityRole, DEFAULT_ROLE_PERMISSIONS
from reamp.mvp.models import Site, AssetRecord, SensorRecord, TechnologyType, AssetStatus
from reamp.digital_twin.twin import SolarInverterDigitalTwin
from reamp.digital_twin.models import TwinIdentity, InverterConfiguration


class OnboardingManager:
    """Manages lifecycle provisioning for organizations, users, facilities, and physical devices."""

    def __init__(self):
        self.users: Dict[str, UserRecord] = {}
        self.tenants: Dict[str, TenantRecord] = {}

    def onboard_user(
        self,
        name: str,
        email: str,
        role: SecurityRole,
        tenant_id: str,
        actor_id: str = "SYSTEM_ADMIN",
        audit_logger: Optional[Any] = None,
        auth_manager: Optional[Any] = None,
    ) -> UserRecord:
        """
        Onboards a new platform user with role-based access control (RBAC).
        Generates security token and records audit event.
        """
        user_id = f"USR-{uuid.uuid4().hex[:8].upper()}"
        perms = [p.value for p in DEFAULT_ROLE_PERMISSIONS.get(role, [])]

        user = UserRecord(
            user_id=user_id,
            name=name,
            email=email,
            role=role,
            tenant_id=tenant_id,
            status="ACTIVE",
            permissions=perms,
        )
        self.users[user_id] = user

        token_str = None
        if auth_manager:
            from reamp.security.models import UserIdentity
            user_ident = UserIdentity(
                user_id=user_id,
                username=name,
                tenant_id=tenant_id,
                role=role,
            )
            token = auth_manager.generate_token(user_ident)
            token_str = token.token_id
            user.token = token_str

        if audit_logger:
            audit_logger.append_entry(
                actor_id=actor_id,
                tenant_id=tenant_id,
                action="USER_ONBOARDED",
                resource_id=user_id,
                outcome="SUCCESS",
                details={
                    "name": name,
                    "email": email,
                    "role": role.value,
                    "token_id": token_str,
                },
            )

        return user

    @staticmethod
    def derive_facility_prefix(tenant_id: str, tenant_code: Optional[str] = None) -> str:
        """
        Derives standard facility site ID prefix based on the tenant partition ID.
        Examples:
        - ORG-HELIOS-GLOBAL -> SITE-HELIOS-
        - ORG-AURORA-NORDIC -> SITE-AURORA-
        - ORG-SOLARIA-ESP -> SITE-SOLARIA-
        """
        if tenant_code and tenant_code.strip():
            code = tenant_code.strip().upper().replace("SITE-", "").strip("-")
        elif tenant_id.startswith("ORG-"):
            parts = tenant_id.split("-")
            code = parts[1].upper() if len(parts) > 1 else tenant_id.replace("ORG-", "").upper()
        else:
            code = tenant_id.strip().upper()
        return f"SITE-{code}-"

    @classmethod
    def validate_or_apply_facility_prefix(
        cls,
        facility_id: str,
        tenant_id: str,
        tenant_code: Optional[str] = None,
        enforce: bool = True,
    ) -> str:
        """
        Ensures the facility site ID code begins with the fixed prefix based on tenant partition ID.
        If only the suffix is supplied, automatically prepends the prefix.
        If a conflicting prefix is supplied and enforce is True, raises ValueError.
        """
        prefix = cls.derive_facility_prefix(tenant_id, tenant_code)
        fid = facility_id.strip().upper()
        if not fid or not fid.replace("-", "").strip():
            raise ValueError("Facility Site ID cannot be empty.")

        # Deduplicate repeated prefix if user entered or pasted it twice (e.g. SITE-HELIOS-SITE-HELIOS-ATACAMA)
        while fid.startswith(f"{prefix}{prefix}"):
            fid = fid[len(prefix):]

        # Exact match with standard prefix
        if fid.startswith(prefix):
            suffix = fid[len(prefix):].lstrip("-")
            if not suffix:
                raise ValueError("Facility Site ID cannot be empty after prefix.")
            return f"{prefix}{suffix}"

        # If user entered code without SITE- (e.g. HELIOS-ATACAMA-03)
        code = prefix.replace("SITE-", "").rstrip("-")
        if fid.startswith(f"{code}-"):
            suffix = fid[len(code) + 1:].lstrip("-")
            if not suffix:
                raise ValueError("Facility Site ID cannot be empty after prefix.")
            return f"{prefix}{suffix}"

        # Match with tenant_id directly (e.g. SITE-ORG-HELIOS-GLOBAL- or ORG-HELIOS-GLOBAL-)
        if fid.startswith(f"SITE-{tenant_id.upper()}-"):
            suffix = fid[len(f"SITE-{tenant_id.upper()}-"):].lstrip("-")
            return f"SITE-{tenant_id.upper()}-{suffix}"
        if fid.startswith(f"{tenant_id.upper()}-"):
            suffix = fid[len(f"{tenant_id.upper()}-"):].lstrip("-")
            return f"SITE-{tenant_id.upper()}-{suffix}"

        # Suffix-only provided (e.g. ATACAMA-03 or -ATACAMA-03)
        if not fid.startswith("SITE-"):
            clean_suffix = fid.lstrip("-")
            return f"{prefix}{clean_suffix}"

        # If not enforced and already formatted as a SITE- ID (e.g. legacy/test SITE-SONORA-SOLAR)
        if not enforce:
            return fid

        # Starts with SITE- but does not match tenant partition prefix
        raise ValueError(
            f"Facility Site ID '{fid}' violates tenant partition rules: "
            f"must have fixed prefix '{prefix}' based on tenant partition '{tenant_id}'."
        )

    @staticmethod
    def derive_device_prefix(facility_id: str) -> str:
        """
        Derives standard device asset ID prefix based on the selected parent facility.
        Examples:
        - SITE-MOJAVE-01 -> SITE-MOJAVE-01-
        - SITE-HELIOS-ATACAMA-03 -> SITE-HELIOS-ATACAMA-03-
        """
        clean_fac = facility_id.strip().upper().rstrip("-")
        return f"{clean_fac}-"

    @classmethod
    def validate_or_apply_device_prefix(
        cls,
        device_id: str,
        facility_id: str,
        enforce: bool = True,
    ) -> str:
        """
        Ensures the device asset ID begins with the fixed prefix based on the selected parent facility.
        If only the suffix is supplied, automatically prepends the prefix.
        If a conflicting prefix is supplied and enforce is True, raises ValueError.
        """
        prefix = cls.derive_device_prefix(facility_id)
        did = device_id.strip().upper()
        if not did or not did.replace("-", "").strip():
            raise ValueError("Device Asset ID cannot be empty.")

        # Deduplicate repeated prefix if user pasted or typed it twice (e.g. SITE-MOJAVE-01-SITE-MOJAVE-01-INV-04)
        while did.startswith(f"{prefix}{prefix}"):
            did = did[len(prefix):]

        # Exact match with facility prefix
        if did.startswith(prefix):
            suffix = did[len(prefix):].lstrip("-")
            if not suffix:
                raise ValueError("Device Asset ID cannot be empty after prefix.")
            return f"{prefix}{suffix}"

        # Match with short facility code if facility starts with SITE- (e.g. MOJAVE-01-INV-01)
        if facility_id.upper().startswith("SITE-"):
            short_fac = facility_id.upper()[5:].rstrip("-")
            if did.startswith(f"{short_fac}-"):
                suffix = did[len(short_fac) + 1:].lstrip("-")
                return f"{prefix}{suffix}"

        # If not enforced and already formatted as an asset ID (e.g. ASSET-INV-SONORA-01)
        if not enforce and did.startswith("ASSET-"):
            return did

        # Suffix-only provided (e.g. INV-04 or WTG-02 or -INV-04)
        if not did.startswith("SITE-") and not did.startswith("ASSET-"):
            clean_suffix = did.lstrip("-")
            return f"{prefix}{clean_suffix}"

        # Starts with a foreign facility prefix or non-matching asset ID when enforced
        if enforce:
            raise ValueError(
                f"Device Asset ID '{did}' violates parent facility rules: "
                f"must have fixed prefix '{prefix}' based on selected parent facility '{facility_id}'."
            )
        return did

    def onboard_facility(
        self,
        app: Any,
        request: FacilityOnboardingRequest,
        actor_id: str = "SYSTEM_ADMIN",
        enforce_prefix: bool = False,
    ) -> OnboardingResult:
        """
        Onboards a new renewable energy power plant / facility.
        Registers site within the tenant topology.
        """
        request.facility_id = self.validate_or_apply_facility_prefix(
            request.facility_id,
            app.tenant_id,
            enforce=enforce_prefix,
        )
        if request.facility_id in app.sites:
            return OnboardingResult(
                status="ERROR",
                entity_id=request.facility_id,
                entity_type="FACILITY",
                message=f"Facility '{request.facility_id}' already exists.",
            )

        site = Site(
            site_id=request.facility_id,
            portfolio_id=request.portfolio_id,
            name=request.name,
            latitude=request.latitude,
            longitude=request.longitude,
            rated_capacity_mw=request.rated_capacity_mw,
            technology=request.technology,
            metadata=request.metadata,
        )
        app.register_site(site)

        if hasattr(app, "audit_logger") and app.audit_logger:
            app.audit_logger.append_entry(
                actor_id=actor_id,
                tenant_id=app.tenant_id,
                action="FACILITY_ONBOARDED",
                resource_id=request.facility_id,
                outcome="SUCCESS",
                details={
                    "name": request.name,
                    "technology": request.technology.value if hasattr(request.technology, "value") else str(request.technology),
                    "rated_capacity_mw": request.rated_capacity_mw,
                    "coordinates": [request.latitude, request.longitude],
                },
            )

        return OnboardingResult(
            status="SUCCESS",
            entity_id=request.facility_id,
            entity_type="FACILITY",
            message=f"Facility '{request.name}' successfully provisioned.",
            details={
                "site_id": site.site_id,
                "technology": site.technology.value,
                "rated_capacity_mw": site.rated_capacity_mw,
            }
        )

    def onboard_device(
        self,
        app: Any,
        request: DeviceOnboardingRequest,
        actor_id: str = "SYSTEM_ADMIN",
        enforce_prefix: bool = False,
    ) -> OnboardingResult:
        """
        Onboards a new generation or storage device (e.g. Inverter, Turbine, BESS).
        Provisions device secret for edge signing, default telemetry sensors, and Digital Twin.
        """
        if request.facility_id not in app.sites:
            return OnboardingResult(
                status="ERROR",
                entity_id=request.device_id,
                entity_type="DEVICE",
                message=f"Parent facility '{request.facility_id}' does not exist.",
            )

        request.device_id = self.validate_or_apply_device_prefix(
            request.device_id,
            request.facility_id,
            enforce=enforce_prefix,
        )

        if request.device_id in app.assets:
            return OnboardingResult(
                status="ERROR",
                entity_id=request.device_id,
                entity_type="DEVICE",
                message=f"Device '{request.device_id}' already registered.",
            )

        # 1. Device Secret for HMAC signing
        secret = request.device_secret or f"sec-{secrets.token_hex(16)}"

        # 2. Asset Record Registration
        asset = AssetRecord(
            asset_id=request.device_id,
            site_id=request.facility_id,
            name=request.name,
            asset_type=request.asset_type.upper(),
            model=request.model,
            rated_power_kw=request.rated_power_kw,
            commissioned_date=datetime.datetime.now(datetime.timezone.utc),
            status=AssetStatus.ACTIVE,
            metadata=request.metadata,
        )
        app.register_asset(asset, device_secret=secret)

        # 3. Default Sensors Provisioning
        sensor_list = []
        atype = request.asset_type.upper()
        if "INVERTER" in atype or "SOLAR" in atype:
            sensor_list = [
                SensorRecord(f"SENS-{request.device_id}-POA", request.device_id, "POA Pyranometer", "POA_IRRADIANCE", "W/m^2", 0.0, 1500.0),
                SensorRecord(f"SENS-{request.device_id}-THS", request.device_id, "Heatsink PT100", "HEATSINK_TEMP", "degC", 0.0, 120.0),
                SensorRecord(f"SENS-{request.device_id}-PAC", request.device_id, "AC Power Meter", "AC_POWER", "kW", 0.0, request.rated_power_kw * 1.1),
                SensorRecord(f"SENS-{request.device_id}-PDC", request.device_id, "DC Transducer", "DC_POWER", "kW", 0.0, request.rated_power_kw * 1.2),
            ]
        elif "TURBINE" in atype or "WIND" in atype:
            sensor_list = [
                SensorRecord(f"SENS-{request.device_id}-WS", request.device_id, "Anemometer", "WIND_SPEED", "m/s", 0.0, 50.0),
                SensorRecord(f"SENS-{request.device_id}-TGB", request.device_id, "Gearbox Temp RTD", "GEARBOX_TEMP", "degC", 0.0, 130.0),
                SensorRecord(f"SENS-{request.device_id}-TBRG", request.device_id, "Main Bearing RTD", "BEARING_TEMP", "degC", 0.0, 120.0),
                SensorRecord(f"SENS-{request.device_id}-PAC", request.device_id, "AC Power Meter", "AC_POWER", "kW", 0.0, request.rated_power_kw * 1.1),
            ]
        elif "BESS" in atype or "BATTERY" in atype:
            sensor_list = [
                SensorRecord(f"SENS-{request.device_id}-SOC", request.device_id, "Battery BMS SoC", "SOC", "%", 0.0, 100.0),
                SensorRecord(f"SENS-{request.device_id}-TCELL", request.device_id, "Cell Temp Matrix", "CELL_TEMP", "degC", -10.0, 80.0),
                SensorRecord(f"SENS-{request.device_id}-PAC", request.device_id, "PCS Bi-directional Power", "AC_POWER", "kW", -request.rated_power_kw, request.rated_power_kw),
            ]

        for s in sensor_list:
            app.register_sensor(s)

        # 4. Provision Digital Twin if Solar Inverter
        twin_provisioned = False
        if request.provision_digital_twin and ("INVERTER" in atype or "SOLAR" in atype):
            twin_id = TwinIdentity(
                asset_id=request.device_id,
                serial_number=f"SN-{request.device_id}-2026",
                manufacturer="Sungrow",
                model=request.model,
                site_id=request.facility_id,
                subsystem_ids=[f"{request.device_id}-COOLING", f"{request.device_id}-IGBT"],
            )
            twin_cfg = InverterConfiguration(
                rated_ac_power_kw=request.rated_power_kw,
                rated_dc_power_kw=request.rated_power_kw * 1.1,
                thermal_resistance_c_per_kw=0.08,
            )
            twin = SolarInverterDigitalTwin(identity=twin_id, configuration=twin_cfg)
            app.register_twin(twin)
            twin_provisioned = True

        if hasattr(app, "audit_logger") and app.audit_logger:
            app.audit_logger.append_entry(
                actor_id=actor_id,
                tenant_id=app.tenant_id,
                action="DEVICE_ONBOARDED",
                resource_id=request.device_id,
                outcome="SUCCESS",
                details={
                    "name": request.name,
                    "asset_type": request.asset_type,
                    "site_id": request.facility_id,
                    "rated_power_kw": request.rated_power_kw,
                    "sensors_provisioned": len(sensor_list),
                    "digital_twin": twin_provisioned,
                },
            )

        return OnboardingResult(
            status="SUCCESS",
            entity_id=request.device_id,
            entity_type="DEVICE",
            message=f"Device '{request.name}' successfully onboarded with {len(sensor_list)} sensor channels.",
            details={
                "device_id": request.device_id,
                "site_id": request.facility_id,
                "device_secret": secret,
                "sensors_count": len(sensor_list),
                "digital_twin_active": twin_provisioned,
            }
        )

    def onboard_tenant(
        self,
        request: TenantOnboardingRequest,
        actor_id: str = "SYSTEM_ADMIN",
        audit_logger: Optional[Any] = None,
    ) -> OnboardingResult:
        """
        Onboards a new corporate organization / tenant with isolation boundaries.
        """
        if request.tenant_id in self.tenants:
            return OnboardingResult(
                status="ERROR",
                entity_id=request.tenant_id,
                entity_type="TENANT",
                message=f"Tenant '{request.tenant_id}' already exists.",
            )

        tenant = TenantRecord(
            tenant_id=request.tenant_id,
            name=request.name,
            code=request.code,
            billing_tier=request.billing_tier,
            metadata=request.metadata,
        )
        self.tenants[request.tenant_id] = tenant

        if audit_logger:
            audit_logger.append_entry(
                actor_id=actor_id,
                tenant_id=request.tenant_id,
                action="TENANT_ONBOARDED",
                resource_id=request.tenant_id,
                outcome="SUCCESS",
                details={
                    "name": request.name,
                    "code": request.code,
                    "billing_tier": request.billing_tier,
                    "admin_email": request.admin_email,
                },
            )

        return OnboardingResult(
            status="SUCCESS",
            entity_id=request.tenant_id,
            entity_type="TENANT",
            message=f"Tenant '{request.name}' ({request.tenant_id}) successfully enrolled.",
            details={
                "tenant_id": request.tenant_id,
                "name": request.name,
                "code": request.code,
                "billing_tier": request.billing_tier,
            },
        )

    def list_tenants(self) -> List[Dict[str, Any]]:
        """Returns all enrolled tenants as dictionaries."""
        return [
            {
                "tenant_id": t.tenant_id,
                "name": t.name,
                "code": t.code,
                "billing_tier": t.billing_tier,
                "created_at": t.created_at,
                "status": t.status,
                "sites_count": t.sites_count,
                "assets_count": t.assets_count,
                "users_count": sum(1 for u in self.users.values() if u.tenant_id == t.tenant_id),
                "metadata": t.metadata,
            }
            for t in self.tenants.values()
        ]

    def get_tenant(self, tenant_id: str) -> Optional[TenantRecord]:
        """Retrieves tenant record by ID."""
        return self.tenants.get(tenant_id)

    def update_user_role(
        self,
        user_id: str,
        new_role: SecurityRole,
        actor_id: str = "SYSTEM_ADMIN",
        audit_logger: Optional[Any] = None,
    ) -> UserRecord:
        """
        Updates a user's RBAC role and refreshes permissions.
        """
        user = self.users.get(user_id)
        if not user:
            raise ValueError(f"User '{user_id}' does not exist.")

        old_role = user.role
        user.role = new_role
        user.permissions = [p.value for p in DEFAULT_ROLE_PERMISSIONS.get(new_role, [])]
        user.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if audit_logger:
            audit_logger.append_entry(
                actor_id=actor_id,
                tenant_id=user.tenant_id,
                action="USER_ROLE_UPDATED",
                resource_id=user_id,
                outcome="SUCCESS",
                details={
                    "old_role": old_role.value if hasattr(old_role, "value") else str(old_role),
                    "new_role": new_role.value if hasattr(new_role, "value") else str(new_role),
                    "permissions_count": len(user.permissions),
                },
            )

        return user

    def update_user_status(
        self,
        user_id: str,
        status: str,
        actor_id: str = "SYSTEM_ADMIN",
        audit_logger: Optional[Any] = None,
    ) -> UserRecord:
        """
        Toggles a user's status between ACTIVE and SUSPENDED.
        """
        user = self.users.get(user_id)
        if not user:
            raise ValueError(f"User '{user_id}' does not exist.")

        valid_statuses = ("ACTIVE", "SUSPENDED", "REVOKED")
        if status.upper() not in valid_statuses:
            raise ValueError(f"Invalid status '{status}'. Must be one of {valid_statuses}.")

        old_status = user.status
        user.status = status.upper()
        user.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if audit_logger:
            audit_logger.append_entry(
                actor_id=actor_id,
                tenant_id=user.tenant_id,
                action="USER_STATUS_UPDATED",
                resource_id=user_id,
                outcome="SUCCESS",
                details={
                    "old_status": old_status,
                    "new_status": user.status,
                },
            )

        return user

    def regenerate_user_token(
        self,
        user_id: str,
        auth_manager: Any,
        actor_id: str = "SYSTEM_ADMIN",
        audit_logger: Optional[Any] = None,
    ) -> str:
        """
        Regenerates HMAC security token for an active user.
        """
        user = self.users.get(user_id)
        if not user:
            raise ValueError(f"User '{user_id}' does not exist.")

        from reamp.security.models import UserIdentity
        user_ident = UserIdentity(
            user_id=user.user_id,
            username=user.name,
            tenant_id=user.tenant_id,
            role=user.role,
        )
        token = auth_manager.generate_token(user_ident)
        user.token = token.token_id
        user.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if audit_logger:
            audit_logger.append_entry(
                actor_id=actor_id,
                tenant_id=user.tenant_id,
                action="USER_TOKEN_REGENERATED",
                resource_id=user_id,
                outcome="SUCCESS",
                details={"new_token_id": token.token_id},
            )

        return user.token

    def list_users(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns all registered users as dictionaries, optionally filtered by tenant.
        """
        users_iter = self.users.values()
        if tenant_id:
            users_iter = [u for u in users_iter if u.tenant_id == tenant_id]

        return [
            {
                "user_id": u.user_id,
                "name": u.name,
                "email": u.email,
                "role": u.role.value if hasattr(u.role, "value") else str(u.role),
                "tenant_id": u.tenant_id,
                "status": u.status,
                "token": u.token,
                "created_at": u.created_at,
                "updated_at": getattr(u, "updated_at", u.created_at),
                "last_active": getattr(u, "last_active", None),
                "permissions": u.permissions,
            }
            for u in users_iter
        ]

    def get_user(self, user_id: str) -> Optional[UserRecord]:
        """Retrieves user by ID."""
        return self.users.get(user_id)

