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
    FacilityOnboardingRequest,
    DeviceOnboardingRequest,
    OnboardingResult,
)
from reamp.security.models import SecurityRole, DEFAULT_ROLE_PERMISSIONS
from reamp.mvp.models import Site, AssetRecord, SensorRecord, TechnologyType, AssetStatus
from reamp.digital_twin.twin import SolarInverterDigitalTwin
from reamp.digital_twin.models import TwinIdentity, InverterConfiguration


class OnboardingManager:
    """Manages lifecycle provisioning for users, facilities, and physical devices."""

    def __init__(self):
        self.users: Dict[str, UserRecord] = {}

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

    def onboard_facility(
        self,
        app: Any,
        request: FacilityOnboardingRequest,
        actor_id: str = "SYSTEM_ADMIN",
    ) -> OnboardingResult:
        """
        Onboards a new renewable energy power plant / facility.
        Registers site within the tenant topology.
        """
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

    def list_users(self) -> List[Dict[str, Any]]:
        """Returns all registered users as dictionaries."""
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
                "permissions": u.permissions,
            }
            for u in self.users.values()
        ]

    def get_user(self, user_id: str) -> Optional[UserRecord]:
        """Retrieves user by ID."""
        return self.users.get(user_id)

