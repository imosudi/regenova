#!/usr/bin/env python3
"""
REGENOVA Production Web Application & WSGI Server.
Serves the modern, interactive SCADA & Fleet Intelligence Web Application.
Supports both standalone execution (http.server) and Apache mod_wsgi.
Connects directly to REAMPApplicationMVP, REAMPAppAPI, and AdaptiveIntelligenceEngine.
"""

import sys
import os
import json
import datetime
import mimetypes
from typing import Dict, List, Optional, Any, Tuple
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from reamp.mvp import (
    REAMPApplicationMVP,
    REAMPAppAPI,
    Site,
    AssetRecord,
    TechnologyType,
    AssetStatus,
    AlertStatus,
)
from reamp.security.models import SecurityRole
from reamp.cmms.models import WorkOrderStatus
from reamp.adaptive.models import AdaptationType
from reamp.onboarding import (
    OnboardingManager,
    TenantOnboardingRequest,
    TenantRecord,
    FacilityOnboardingRequest,
    DeviceOnboardingRequest,
)
from reamp.storage import PostgresDatabaseManager


class REAMPWebServerState:
    def __init__(self):
        self.default_tenant_id = "ORG-HELIOS-GLOBAL"
        self.tenants: Dict[str, REAMPApplicationMVP] = {}

        # Primary Tenant: Helios Global Renewables
        self.app = REAMPApplicationMVP(
            tenant_id=self.default_tenant_id,
            storage_db=":memory:",
            master_secret="reamp-web-master-secret-key-32b",
        )
        self.app.initialize_default_topology()
        self.tenants[self.default_tenant_id] = self.app
        self.api = REAMPAppAPI(self.app)
        self.admin_token = self.api.authenticate("chief-eng-web", SecurityRole.CHIEF_ENGINEER)

        # Database persistence layer (PostgreSQL)
        self.db = PostgresDatabaseManager()

        # Onboarding lifecycle manager
        self.onboarding = OnboardingManager()
        self.onboarding.onboard_tenant(
            TenantOnboardingRequest(
                tenant_id=self.default_tenant_id,
                name="Helios Global Renewables",
                code="HELIOS",
                billing_tier="ENTERPRISE",
                admin_name="Dr. Elena Rostova",
                admin_email="elena.rostova@helios.energy",
            )
        )
        self._seed_default_users()

        # Provision full multi-technology sites & assets for Helios
        self._provision_multi_tech_fleet()

        # Seed initial nominal telemetry for all assets
        self._seed_fleet_telemetry()

        # Provision Secondary Pre-seeded Tenants (Aurora Nordic & Solaria Iberia)
        self._provision_secondary_tenants()

        # Synchronize topology & seed entities to PostgreSQL
        self._sync_to_database()

    def get_tenant_app(self, tenant_id: Optional[str] = None) -> REAMPApplicationMVP:
        """Retrieves or dynamically instantiates an application orchestrator for a tenant."""
        t_id = tenant_id or self.default_tenant_id
        if t_id not in self.tenants:
            t_rec = self.onboarding.get_tenant(t_id)
            app = REAMPApplicationMVP(
                tenant_id=t_id,
                storage_db=":memory:",
                master_secret=f"reamp-master-secret-{t_id}",
            )
            self.tenants[t_id] = app
        return self.tenants[t_id]

    def _sync_to_database(self):
        """Synchronizes in-memory topology and seeded users to PostgreSQL if available."""
        try:
            if not self.db.test_connection():
                return
            for t_id, app in self.tenants.items():
                t_rec = self.onboarding.get_tenant(t_id)
                t_name = t_rec.name if t_rec else f"Organization {t_id}"
                t_code = t_rec.code if t_rec else t_id.replace("ORG-", "")
                t_tier = t_rec.billing_tier if t_rec else "ENTERPRISE"
                self.db.sync_organisation(t_id, name=t_name, code=t_code, billing_tier=t_tier)
                for s in app.sites.values():
                    tech_val = s.technology.value if hasattr(s.technology, 'value') else str(s.technology)
                    self.db.sync_site(
                        site_id=s.site_id,
                        tenant_id=t_id,
                        portfolio_id=s.portfolio_id,
                        name=s.name,
                        code=s.site_id,
                        latitude=s.latitude,
                        longitude=s.longitude,
                        rated_capacity_mw=s.rated_capacity_mw,
                        technology=tech_val,
                    )
                for a in app.assets.values():
                    self.db.sync_asset(
                        asset_id=a.asset_id,
                        tenant_id=t_id,
                        site_id=a.site_id,
                        name=a.name,
                        code=a.asset_id,
                        asset_type=a.asset_type,
                        model=a.model,
                        rated_power_kw=a.rated_power_kw,
                    )
            for u in self.onboarding.list_users():
                role_val = u["role"]
                self.db.sync_user(
                    user_id=u["user_id"],
                    tenant_id=u["tenant_id"],
                    email=u["email"],
                    full_name=u["name"],
                    role=role_val,
                    is_active=(u.get("status") == "ACTIVE"),
                    metadata={"token": u.get("token"), "permissions": u.get("permissions")},
                )
        except Exception:
            pass

    def _seed_default_users(self):
        self.onboarding.onboard_user(
            name="Dr. Elena Rostova",
            email="elena.rostova@helios.energy",
            role=SecurityRole.CHIEF_ENGINEER,
            tenant_id=self.app.tenant_id,
            actor_id="SYSTEM_INIT",
            audit_logger=self.app.audit_logger,
            auth_manager=self.app.auth_manager,
        )
        self.onboarding.onboard_user(
            name="Marcus Vance",
            email="marcus.vance@helios.energy",
            role=SecurityRole.OPERATOR,
            tenant_id=self.app.tenant_id,
            actor_id="SYSTEM_INIT",
            audit_logger=self.app.audit_logger,
            auth_manager=self.app.auth_manager,
        )
        self.onboarding.onboard_user(
            name="Sarah Chen",
            email="sarah.chen@helios.energy",
            role=SecurityRole.SECURITY_ADMIN,
            tenant_id=self.app.tenant_id,
            actor_id="SYSTEM_INIT",
            audit_logger=self.app.audit_logger,
            auth_manager=self.app.auth_manager,
        )
        self.onboarding.onboard_user(
            name="David Kim",
            email="david.kim@helios.energy",
            role=SecurityRole.VIEWER,
            tenant_id=self.app.tenant_id,
            actor_id="SYSTEM_INIT",
            audit_logger=self.app.audit_logger,
            auth_manager=self.app.auth_manager,
        )

    def _provision_multi_tech_fleet(self):
        # 1. Wind Farm
        wind_site = Site(
            site_id="SITE-WIND-NORTH",
            portfolio_id="PORT-SW-UTILITY",
            name="North Sea Offshore Wind Farm",
            latitude=55.5,
            longitude=7.2,
            rated_capacity_mw=80.0,
            technology=TechnologyType.WIND,
        )
        self.app.register_site(wind_site)
        wind_asset = AssetRecord(
            asset_id="WTG-NORTH-01",
            site_id=wind_site.site_id,
            name="Vestas V164 2.5MW Nacelle 01",
            asset_type="WIND_TURBINE",
            model="V164-2500",
            rated_power_kw=2500.0,
            status=AssetStatus.ACTIVE,
            commissioned_date=datetime.datetime(2024, 6, 1, tzinfo=datetime.timezone.utc),
            metadata={"hub_height_m": 105.0, "rotor_diameter_m": 120.0},
        )
        self.app.register_asset(wind_asset, device_secret="sec-wtg-01")

        # 2. BESS Station
        bess_site = Site(
            site_id="SITE-BESS-WEST",
            portfolio_id="PORT-SW-UTILITY",
            name="West Grid BESS Station",
            latitude=34.2,
            longitude=-118.3,
            rated_capacity_mw=20.0,
            technology=TechnologyType.BESS,
        )
        self.app.register_site(bess_site)
        bess_asset = AssetRecord(
            asset_id="BESS-WEST-01",
            site_id=bess_site.site_id,
            name="Tesla Megapack 2XL Enclosure 01",
            asset_type="BESS_CONTAINER",
            model="MP-2XL-1000",
            rated_power_kw=1000.0,
            status=AssetStatus.ACTIVE,
            commissioned_date=datetime.datetime(2025, 1, 15, tzinfo=datetime.timezone.utc),
            metadata={"capacity_kwh": 4000.0, "chemistry": "LFP"},
        )
        self.app.register_asset(bess_asset, device_secret="sec-bess-01")

        # 3. Hybrid Plant
        hybrid_site = Site(
            site_id="SITE-HYBRID-HUB",
            portfolio_id="PORT-SW-UTILITY",
            name="Desert Wind & Sun Hybrid Hub",
            latitude=35.0,
            longitude=-115.0,
            rated_capacity_mw=150.0,
            technology=TechnologyType.HYBRID,
        )
        self.app.register_site(hybrid_site)
        hybrid_solar = AssetRecord(
            asset_id="HYBRID-SOLAR-01",
            site_id=hybrid_site.site_id,
            name="Central Solar Inverter Array",
            asset_type="INVERTER",
            model="PV-INV-2500",
            rated_power_kw=2500.0,
            status=AssetStatus.ACTIVE,
            commissioned_date=datetime.datetime(2025, 5, 1, tzinfo=datetime.timezone.utc),
        )
        hybrid_wind = AssetRecord(
            asset_id="HYBRID-WIND-01",
            site_id=hybrid_site.site_id,
            name="Co-located Wind Turbine 01",
            asset_type="WIND_TURBINE",
            model="WT-2000",
            rated_power_kw=2000.0,
            status=AssetStatus.ACTIVE,
            commissioned_date=datetime.datetime(2025, 5, 1, tzinfo=datetime.timezone.utc),
        )
        hybrid_bess = AssetRecord(
            asset_id="HYBRID-BESS-01",
            site_id=hybrid_site.site_id,
            name="Grid Balancing BESS Pack",
            asset_type="BESS_CONTAINER",
            model="BESS-1000",
            rated_power_kw=1000.0,
            status=AssetStatus.ACTIVE,
            commissioned_date=datetime.datetime(2025, 5, 1, tzinfo=datetime.timezone.utc),
        )
        for a in [hybrid_solar, hybrid_wind, hybrid_bess]:
            self.app.register_asset(a, device_secret=f"sec-{a.asset_id.lower()}")

    def _seed_fleet_telemetry(self):
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # Invert 1 (Mojave)
        self.app.process_telemetry_packet("ASSET-INV-01", {
            "timestamp": now_iso, "poa_irradiance": 860.0, "ambient_temp": 28.0,
            "dc_power_kw": 2150.0, "ac_power_kw": 2085.0, "heatsink_temp": 48.0,
        })
        # Invert 2 (Mojave)
        self.app.process_telemetry_packet("ASSET-INV-02", {
            "timestamp": now_iso, "poa_irradiance": 860.0, "ambient_temp": 28.0,
            "dc_power_kw": 2130.0, "ac_power_kw": 2068.0, "heatsink_temp": 47.5,
        })
        # Wind North
        self.app.process_telemetry_packet("WTG-NORTH-01", {
            "timestamp": now_iso, "wind_speed_ms": 11.2, "power_ac_kw": 2100.0,
            "barometric_pressure_hpa": 1014.0, "ambient_temp_c": 13.0, "gearbox_temp_c": 62.0,
        })
        # BESS West
        self.app.process_telemetry_packet("BESS-WEST-01", {
            "timestamp": now_iso, "power_ac_kw": 750.0, "dispatch_setpoint_kw": 750.0,
            "state_of_charge_percent": 68.0, "temperature_cell_max_c": 27.5,
        })
        # Hybrid Hub Solar
        self.app.process_telemetry_packet("HYBRID-SOLAR-01", {
            "timestamp": now_iso, "poa_irradiance": 890.0, "ambient_temp": 29.0,
            "dc_power_kw": 2250.0, "ac_power_kw": 2180.0, "heatsink_temp": 49.0,
        })
        # Hybrid Hub Wind
        self.app.process_telemetry_packet("HYBRID-WIND-01", {
            "timestamp": now_iso, "wind_speed_ms": 10.5, "power_ac_kw": 1820.0,
            "barometric_pressure_hpa": 1012.0, "ambient_temp_c": 29.0, "gearbox_temp_c": 63.0,
        })
        # Hybrid Hub BESS
        self.app.process_telemetry_packet("HYBRID-BESS-01", {
            "timestamp": now_iso, "power_ac_kw": 400.0, "dispatch_setpoint_kw": 400.0,
            "state_of_charge_percent": 74.0, "temperature_cell_max_c": 26.0,
        })

    def _provision_secondary_tenants(self):
        """Provisions secondary tenants (Aurora Nordic and Solaria Iberia) for cross-tenant isolation."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # 1. ORG-AURORA-NORDIC (Wind & BESS)
        aurora_id = "ORG-AURORA-NORDIC"
        self.onboarding.onboard_tenant(
            TenantOnboardingRequest(
                tenant_id=aurora_id,
                name="Aurora Nordic Clean Energy",
                code="AURORA",
                billing_tier="UTILITY",
                admin_name="Astrid Lindgren",
                admin_email="astrid.lindgren@aurora.energy",
            )
        )
        app_aurora = self.get_tenant_app(aurora_id)

        site_fjord = Site(
            site_id="SITE-FJORD-WIND",
            portfolio_id="PORT-NORDIC-CLEAN",
            name="Fjord Coastal Wind Park",
            latitude=62.47,
            longitude=6.15,
            rated_capacity_mw=120.0,
            technology=TechnologyType.WIND,
        )
        site_arctic_bess = Site(
            site_id="SITE-ARCTIC-BESS",
            portfolio_id="PORT-NORDIC-CLEAN",
            name="Arctic Sub-Zero BESS Facility",
            latitude=68.44,
            longitude=17.56,
            rated_capacity_mw=40.0,
            technology=TechnologyType.BESS,
        )
        app_aurora.register_site(site_fjord)
        app_aurora.register_site(site_arctic_bess)

        asset_t1 = AssetRecord("TURB-FJORD-01", "SITE-FJORD-WIND", "Vestas V162 Wind Turbine #1", "WIND_TURBINE", "Vestas V162 EnVentus", 5600.0, datetime.datetime.now(datetime.timezone.utc), AssetStatus.ACTIVE)
        asset_t2 = AssetRecord("TURB-FJORD-02", "SITE-FJORD-WIND", "Vestas V162 Wind Turbine #2", "WIND_TURBINE", "Vestas V162 EnVentus", 5600.0, datetime.datetime.now(datetime.timezone.utc), AssetStatus.ACTIVE)
        asset_b1 = AssetRecord("BESS-ARCTIC-01", "SITE-ARCTIC-BESS", "Tesla Megapack 2XL #1", "BESS_CONTAINER", "Tesla Megapack 2XL", 3000.0, datetime.datetime.now(datetime.timezone.utc), AssetStatus.ACTIVE)
        app_aurora.register_asset(asset_t1, device_secret="sec-turb-fjord-01")
        app_aurora.register_asset(asset_t2, device_secret="sec-turb-fjord-02")
        app_aurora.register_asset(asset_b1, device_secret="sec-bess-arctic-01")

        app_aurora.process_telemetry_packet("TURB-FJORD-01", {
            "timestamp": now_iso, "wind_speed_ms": 11.8, "power_ac_kw": 5120.0,
            "barometric_pressure_hpa": 1010.0, "ambient_temp_c": 8.5, "gearbox_temp_c": 59.0,
        })
        app_aurora.process_telemetry_packet("TURB-FJORD-02", {
            "timestamp": now_iso, "wind_speed_ms": 11.6, "power_ac_kw": 5080.0,
            "barometric_pressure_hpa": 1010.0, "ambient_temp_c": 8.5, "gearbox_temp_c": 60.2,
        })
        app_aurora.process_telemetry_packet("BESS-ARCTIC-01", {
            "timestamp": now_iso, "power_ac_kw": 1800.0, "dispatch_setpoint_kw": 1800.0,
            "state_of_charge_percent": 82.0, "temperature_cell_max_c": 22.0,
        })

        self.onboarding.onboard_user("Astrid Lindgren", "astrid.lindgren@aurora.energy", SecurityRole.CHIEF_ENGINEER, aurora_id, "SYSTEM_INIT", app_aurora.audit_logger, app_aurora.auth_manager)
        self.onboarding.onboard_user("Henrik Holm", "henrik.holm@aurora.energy", SecurityRole.OPERATOR, aurora_id, "SYSTEM_INIT", app_aurora.audit_logger, app_aurora.auth_manager)
        self.onboarding.onboard_user("Freja Jensen", "freja.jensen@aurora.energy", SecurityRole.VIEWER, aurora_id, "SYSTEM_INIT", app_aurora.audit_logger, app_aurora.auth_manager)

        # 2. ORG-SOLARIA-ESP (Solar PV)
        solaria_id = "ORG-SOLARIA-ESP"
        self.onboarding.onboard_tenant(
            TenantOnboardingRequest(
                tenant_id=solaria_id,
                name="Solaria Iberia Energia",
                code="SOLARIA",
                billing_tier="ENTERPRISE",
                admin_name="Javier Morales",
                admin_email="javier.morales@solaria.energy",
            )
        )
        app_solaria = self.get_tenant_app(solaria_id)

        site_andalusia = Site(
            site_id="SITE-SOLARIA-AND",
            portfolio_id="PORT-IBERIA-SOLAR",
            name="Andalusia Solar Generation Hub",
            latitude=37.38,
            longitude=-5.98,
            rated_capacity_mw=80.0,
            technology=TechnologyType.SOLAR_PV,
        )
        app_solaria.register_site(site_andalusia)

        asset_s1 = AssetRecord("INV-SOLARIA-01", "SITE-SOLARIA-AND", "SMA Solar Central #1", "SOLAR_INVERTER", "SMA Central 2500-EV", 2500.0, datetime.datetime.now(datetime.timezone.utc), AssetStatus.ACTIVE)
        asset_s2 = AssetRecord("INV-SOLARIA-02", "SITE-SOLARIA-AND", "SMA Solar Central #2", "SOLAR_INVERTER", "SMA Central 2500-EV", 2500.0, datetime.datetime.now(datetime.timezone.utc), AssetStatus.ACTIVE)
        app_solaria.register_asset(asset_s1, device_secret="sec-inv-solaria-01")
        app_solaria.register_asset(asset_s2, device_secret="sec-inv-solaria-02")

        app_solaria.process_telemetry_packet("INV-SOLARIA-01", {
            "timestamp": now_iso, "poa_irradiance": 885.0, "ambient_temp": 31.0,
            "dc_power_kw": 2400.0, "ac_power_kw": 2340.0, "heatsink_temp": 49.5,
        })
        app_solaria.process_telemetry_packet("INV-SOLARIA-02", {
            "timestamp": now_iso, "poa_irradiance": 885.0, "ambient_temp": 31.0,
            "dc_power_kw": 2380.0, "ac_power_kw": 2320.0, "heatsink_temp": 48.8,
        })

        self.onboarding.onboard_user("Javier Morales", "javier.morales@solaria.energy", SecurityRole.CHIEF_ENGINEER, solaria_id, "SYSTEM_INIT", app_solaria.audit_logger, app_solaria.auth_manager)
        self.onboarding.onboard_user("Lucia Gomez", "lucia.gomez@solaria.energy", SecurityRole.OPERATOR, solaria_id, "SYSTEM_INIT", app_solaria.audit_logger, app_solaria.auth_manager)

    # -------------------------------------------------------------------------
    # Core Data & Action Handlers (Multi-Tenant Scoped)
    # -------------------------------------------------------------------------

    def get_tenants_data(self) -> dict:
        """Returns all registered corporate tenants with live metrics."""
        tenants = self.onboarding.list_tenants()
        for t in tenants:
            t_id = t["tenant_id"]
            if t_id in self.tenants:
                app = self.tenants[t_id]
                t["sites_count"] = len(app.sites)
                t["assets_count"] = len(app.assets)
                t["capacity_mw"] = round(sum(s.rated_capacity_mw for s in app.sites.values()), 1)
                t["active_alerts_count"] = len([a for a in app.alerts.values() if a.status == AlertStatus.ACTIVE])
        return {"tenants": tenants, "default_tenant_id": self.default_tenant_id}

    def get_overview_data(self, tenant_id: Optional[str] = None) -> dict:
        app = self.get_tenant_app(tenant_id)
        total_gen_kw = sum(app.latest_performance_ratio.get(a, 0.0) * (app.assets[a].rated_power_kw if a in app.assets else 2000.0) for a in app.assets)
        total_cap_mw = sum(s.rated_capacity_mw for s in app.sites.values())
        healths = list(app.latest_health.values())
        avg_health = sum(healths) / len(healths) if healths else 95.0
        prs = list(app.latest_performance_ratio.values())
        avg_pr = sum(prs) / len(prs) if prs else 0.95
        active_alerts = len([a for a in app.alerts.values() if a.status == AlertStatus.ACTIVE])
        pending_wo = len([w for w in app.cmms_engine.work_orders.values() if w.status == WorkOrderStatus.PENDING_HITL_APPROVAL])

        return {
            "tenant_id": app.tenant_id,
            "total_generation_mw": round(total_gen_kw / 1000.0, 2),
            "total_capacity_mw": round(total_cap_mw, 1),
            "fleet_health_index": round(avg_health, 1),
            "fleet_performance_ratio": round(avg_pr, 3),
            "active_alerts_count": active_alerts,
            "pending_hitl_work_orders": pending_wo,
            "total_sites": len(app.sites),
            "total_assets": len(app.assets),
            "co2_avoided_tons": round(total_gen_kw * 0.00042 * 24, 1),
            "audit_chain_length": len(app.audit_logger._chain),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    def get_sites_data(self, tenant_id: Optional[str] = None) -> list:
        app = self.get_tenant_app(tenant_id)
        sites = []
        for s in app.sites.values():
            assets = [a for a in app.assets.values() if a.site_id == s.site_id]
            gen_kw = 0.0
            for a in assets:
                twin = app.twins.get(a.asset_id)
                if twin and twin.telemetry:
                    gen_kw += twin.telemetry.power_ac_kw
                elif a.asset_id in app.latest_health:
                    gen_kw += a.rated_power_kw * 0.85

            sites.append({
                "site_id": s.site_id,
                "name": s.name,
                "technology": s.technology.value if hasattr(s.technology, "value") else str(s.technology),
                "latitude": s.latitude,
                "longitude": s.longitude,
                "rated_capacity_mw": s.rated_capacity_mw,
                "active_generation_mw": round(gen_kw / 1000.0, 2),
                "asset_count": len(assets),
            })
        return sites

    def get_assets_data(self, tenant_id: Optional[str] = None) -> list:
        app = self.get_tenant_app(tenant_id)
        result = []
        for a in app.assets.values():
            site = app.sites.get(a.site_id)
            twin = app.twins.get(a.asset_id)
            power_kw = 0.0
            if twin and twin.telemetry and twin.telemetry.power_ac_kw > 0.1:
                power_kw = twin.telemetry.power_ac_kw
            else:
                power_kw = a.rated_power_kw * app.latest_performance_ratio.get(a.asset_id, 0.85)

            result.append({
                "asset_id": a.asset_id,
                "name": a.name,
                "site_id": a.site_id,
                "site_name": site.name if site else a.site_id,
                "technology": site.technology.value if site and hasattr(site.technology, "value") else "SOLAR_PV",
                "asset_type": a.asset_type,
                "model": a.model,
                "rated_power_kw": a.rated_power_kw,
                "current_power_kw": round(power_kw, 1),
                "health_index": round(app.latest_health.get(a.asset_id, 95.0), 1),
                "performance_ratio": round(app.latest_performance_ratio.get(a.asset_id, 0.95), 3),
                "status": a.status.value if hasattr(a.status, "value") else str(a.status),
            })
        return result

    def get_asset_detail_data(self, asset_id: str, tenant_id: Optional[str] = None) -> tuple:
        app = self.get_tenant_app(tenant_id)
        if asset_id not in app.assets:
            for other_app in self.tenants.values():
                if asset_id in other_app.assets:
                    app = other_app
                    break

        if asset_id not in app.assets:
            return 404, {"error": f"Asset {asset_id} not found"}

        a = app.assets[asset_id]
        site = app.sites.get(a.site_id)
        twin = app.twins.get(asset_id)

        hi = app.latest_health.get(asset_id, 95.0)
        pr = app.latest_performance_ratio.get(asset_id, 0.95)

        twin_data = {}
        if twin:
            twin_data = {
                "sync_status": twin.sync_status.value if hasattr(twin.sync_status, "value") else str(twin.sync_status),
                "power_ac_kw": twin.telemetry.power_ac_kw,
                "power_dc_kw": twin.telemetry.power_dc_kw,
                "temperature_heatsink_c": twin.telemetry.temperature_heatsink_c,
                "ambient_temperature_c": twin.telemetry.ambient_temperature_c,
                "poa_irradiance_w_per_m2": twin.telemetry.poa_irradiance_w_per_m2,
                "power_residual_kw": round(twin.residuals.power_residual_kw, 2),
                "temperature_residual_c": round(twin.residuals.temperature_residual_c, 2),
                "is_thermal_deviating": twin.residuals.is_thermal_deviating,
            }

        tech = site.technology.value if site and hasattr(site.technology, "value") else "SOLAR_PV"

        detail = {
            "asset_id": a.asset_id,
            "tenant_id": app.tenant_id,
            "name": a.name,
            "site_id": a.site_id,
            "site_name": site.name if site else a.site_id,
            "technology": tech,
            "asset_type": a.asset_type,
            "model": a.model,
            "rated_power_kw": a.rated_power_kw,
            "health_index": round(hi, 1),
            "performance_ratio": round(pr, 3),
            "baseline_multiplier": app.adaptive_engine.get_baseline_multiplier(asset_id),
            "digital_twin": twin_data,
            "digital_twin_state": "FAULT" if (twin_data.get("is_thermal_deviating") or hi < 85.0) else "RUNNING",
            "revenue_loss": {
                "lost_energy_kwh": round(max(0.0, (1.0 - pr) * a.rated_power_kw), 1),
                "ppa_rate_usd_per_kwh": 0.10,
                "revenue_loss_usd": round(max(0.0, (1.0 - pr) * a.rated_power_kw * 0.10), 2),
            },
            "shap_explanation": [
                {"rank": 1, "feature": "temperature_heatsink_c", "shap_value": 0.428, "direction": "POSITIVE_DEVIATION", "sensor_name": "Thermal Sensor", "description": "Thermal dissipation divergence from first-principles model"},
                {"rank": 2, "feature": "poa_irradiance_w_per_m2", "shap_value": -0.215, "direction": "NEGATIVE_DEVIATION", "sensor_name": "Irradiance / Wind", "description": "Resource ratio deviation from baseline expected"},
                {"rank": 3, "feature": "power_ac_kw", "shap_value": 0.182, "direction": "GAP_EXCURSION", "sensor_name": "AC Power Meter", "description": "Measured active power vs reference model"},
            ],
            "health_dimensions": {
                "performance": round(min(100.0, pr * 100.0), 1),
                "thermal_arrhenius": round(max(30.0, 100.0 - (twin_data.get("temperature_residual_c", 0.0) * 1.5)), 1),
                "availability": 100.0,
                "communication": 98.5,
                "fault_history": 95.0,
                "degradation_age": 96.0,
                "sensor_confidence": 100.0,
            },
            "alerts": [
                {
                    "alert_id": al.alert_id,
                    "title": al.title,
                    "description": al.description,
                    "severity": al.severity.value,
                    "status": al.status.value,
                    "timestamp": al.timestamp.isoformat(),
                }
                for al in app.alerts.values() if al.asset_id == asset_id
            ],
            "work_orders": [
                {
                    "work_order_id": wo.work_order_id,
                    "title": wo.title,
                    "status": wo.status.value,
                    "priority": wo.priority.value,
                    "failure_mode": wo.failure_mode,
                    "created_at": wo.created_at.isoformat(),
                }
                for wo in app.cmms_engine.work_orders.values() if wo.asset_id == asset_id
            ]
        }
        return 200, detail

    def get_alerts_data(self, tenant_id: Optional[str] = None) -> list:
        app = self.get_tenant_app(tenant_id)
        return [
            {
                "alert_id": a.alert_id,
                "tenant_id": app.tenant_id,
                "site_id": a.site_id,
                "asset_id": a.asset_id,
                "title": a.title,
                "description": a.description,
                "severity": a.severity.value if hasattr(a.severity, "value") else str(a.severity),
                "status": a.status.value if hasattr(a.status, "value") else str(a.status),
                "timestamp": a.timestamp.isoformat() if hasattr(a.timestamp, "isoformat") else str(a.timestamp),
            }
            for a in app.alerts.values()
        ]

    def get_work_orders_data(self, tenant_id: Optional[str] = None) -> list:
        app = self.get_tenant_app(tenant_id)
        return [
            {
                "work_order_id": wo.work_order_id,
                "tenant_id": app.tenant_id,
                "asset_id": wo.asset_id,
                "title": wo.title,
                "description": wo.description,
                "status": wo.status.value if hasattr(wo.status, "value") else str(wo.status),
                "priority": wo.priority.value if hasattr(wo.priority, "value") else str(wo.priority),
                "failure_mode": wo.failure_mode,
                "assigned_technician_id": wo.assigned_technician_id,
                "created_at": wo.created_at.isoformat() if hasattr(wo.created_at, "isoformat") else str(wo.created_at),
                "requires_hitl": (wo.status == WorkOrderStatus.PENDING_HITL_APPROVAL),
            }
            for wo in app.cmms_engine.work_orders.values()
        ]

    def get_adaptations_data(self, tenant_id: Optional[str] = None) -> list:
        app = self.get_tenant_app(tenant_id)
        return [
            {
                "action_id": a.action_id,
                "tenant_id": app.tenant_id,
                "asset_id": a.asset_id,
                "type": a.adaptation_type.value,
                "target_metric": a.target_metric,
                "previous_value": a.previous_value,
                "adapted_value": a.adapted_value,
                "percentage_shift": a.percentage_shift,
                "requires_hitl": a.requires_hitl,
                "status": a.status.value,
                "reason": a.reason,
                "timestamp": a.timestamp,
            }
            for a in app.adaptive_engine.adaptation_history.values()
        ]

    def get_audit_chain_data(self, tenant_id: Optional[str] = None) -> dict:
        app = self.get_tenant_app(tenant_id)
        chain = app.audit_logger._chain
        intact, err_idx = app.audit_logger.verify_chain_integrity()
        recent = [
            {
                "entry_id": e.entry_id,
                "timestamp": e.timestamp,
                "actor_id": e.actor_id,
                "tenant_id": getattr(e, "tenant_id", app.tenant_id),
                "action": e.action,
                "resource_id": e.resource_id,
                "outcome": e.outcome,
                "entry_hash": e.entry_hash,
                "prev_hash": e.prev_hash,
            }
            for e in reversed(chain[-20:])
        ]
        return {
            "tenant_id": app.tenant_id,
            "is_valid": intact,
            "corrupted_index": err_idx,
            "total_entries": len(chain),
            "recent_entries": recent,
        }

    def get_users_data(self, tenant_id: Optional[str] = None) -> dict:
        return {"users": self.onboarding.list_users(tenant_id=tenant_id)}

    def inject_telemetry(self, payload: dict, tenant_id: Optional[str] = None) -> dict:
        t_id = payload.get("tenant_id") or tenant_id or self.default_tenant_id
        app = self.get_tenant_app(t_id)
        asset_id = payload.get("asset_id") or list(app.assets.keys())[0]
        scenario = payload.get("scenario", "nominal")
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if scenario == "blower_fault":
            telemetry = {
                "timestamp": now_iso, "poa_irradiance": 930.0, "ambient_temp": 32.0,
                "dc_power_kw": 2200.0, "ac_power_kw": 1850.0, "heatsink_temp": 87.5,
            }
        elif scenario == "soiling_derate":
            telemetry = {
                "timestamp": now_iso, "poa_irradiance": 900.0, "ambient_temp": 27.0,
                "dc_power_kw": 1800.0, "ac_power_kw": 1740.0, "heatsink_temp": 47.0,
            }
        elif scenario == "wind_gust":
            telemetry = {
                "timestamp": now_iso, "wind_speed_ms": 14.5, "power_ac_kw": 2480.0,
                "barometric_pressure_hpa": 1010.0, "ambient_temp_c": 12.0, "gearbox_temp_c": 68.0,
            }
        elif scenario == "bess_discharge":
            telemetry = {
                "timestamp": now_iso, "power_ac_kw": 950.0, "dispatch_setpoint_kw": 950.0,
                "state_of_charge_percent": 45.0, "temperature_cell_max_c": 31.0,
            }
        else:
            telemetry = {
                "timestamp": now_iso, "poa_irradiance": 850.0, "ambient_temp": 26.0,
                "dc_power_kw": 2100.0, "ac_power_kw": 2045.0, "heatsink_temp": 46.5,
            }

        res = app.process_telemetry_packet(asset_id, telemetry)

        if self.db.test_connection():
            try:
                for metric in ("ac_power_kw", "heatsink_temp"):
                    if metric in telemetry:
                        self.db.record_telemetry_observation(
                            timestamp_str=now_iso,
                            tenant_id=app.tenant_id,
                            asset_id=asset_id,
                            metric=metric,
                            sensor_id=f"SNS-{asset_id}-{metric}",
                            value=float(telemetry[metric]),
                            unit="kW" if "power" in metric else "C",
                        )
            except Exception:
                pass

        return {
            "status": "INGESTED",
            "tenant_id": app.tenant_id,
            "asset_id": asset_id,
            "scenario": scenario,
            "result": res,
        }

    def acknowledge_alert(self, payload: dict, tenant_id: Optional[str] = None) -> dict:
        alert_id = payload.get("alert_id")
        app = self.get_tenant_app(tenant_id)
        api = REAMPAppAPI(app)
        return api.acknowledge_alert(alert_id=alert_id, auth_token=self.admin_token)

    def resolve_alert(self, payload: dict, tenant_id: Optional[str] = None) -> dict:
        alert_id = payload.get("alert_id")
        app = self.get_tenant_app(tenant_id)
        api = REAMPAppAPI(app)
        return api.resolve_alert(alert_id=alert_id, auth_token=self.admin_token)

    def approve_work_order(self, payload: dict, tenant_id: Optional[str] = None) -> dict:
        wo_id = payload.get("work_order_id")
        app = self.get_tenant_app(tenant_id)
        api = REAMPAppAPI(app)
        return api.approve_work_order(work_order_id=wo_id, auth_token=self.admin_token)

    def propose_adaptation(self, payload: dict, tenant_id: Optional[str] = None) -> dict:
        app = self.get_tenant_app(tenant_id)
        asset_id = payload.get("asset_id") or list(app.assets.keys())[0]
        shift = float(payload.get("shift_pct", -15.0))
        cur = app.adaptive_engine.get_baseline_multiplier(asset_id)
        new_val = round(cur * (1.0 + (shift / 100.0)), 4)
        action = app.adaptive_engine.propose_adaptation(
            asset_id=asset_id,
            adaptation_type=AdaptationType.BASELINE_DRIFT,
            target_metric="expected_power_multiplier",
            current_value=cur,
            adapted_value=new_val,
            reason=f"Interactive simulation of drift ({shift:+.1f}%)",
            audit_logger=app.audit_logger,
        )
        return {
            "action_id": action.action_id,
            "requires_hitl": action.requires_hitl,
            "status": action.status.value,
            "previous_value": action.previous_value,
            "adapted_value": action.adapted_value,
        }

    def approve_adaptation(self, payload: dict, tenant_id: Optional[str] = None) -> dict:
        app = self.get_tenant_app(tenant_id)
        action_id = payload.get("action_id")
        action = app.adaptive_engine.approve_adaptation(
            action_id=action_id,
            approver_id="chief-eng-web",
            approver_role=SecurityRole.CHIEF_ENGINEER,
            audit_logger=app.audit_logger,
        )
        return {
            "action_id": action.action_id,
            "status": action.status.value,
            "approved_by": action.approved_by,
        }

    def onboard_user_api(self, payload: dict, tenant_id: Optional[str] = None) -> tuple:
        try:
            name = payload.get("name", "").strip()
            email = payload.get("email", "").strip()
            role_str = payload.get("role", "OPERATOR").upper()
            role = SecurityRole[role_str]
            t_id = payload.get("tenant_id") or tenant_id or self.default_tenant_id
            app = self.get_tenant_app(t_id)

            user = self.onboarding.onboard_user(
                name=name,
                email=email,
                role=role,
                tenant_id=t_id,
                actor_id="admin-web",
                audit_logger=app.audit_logger,
                auth_manager=app.auth_manager,
            )
            if self.db.test_connection():
                try:
                    self.db.sync_user(
                        user_id=user.user_id,
                        tenant_id=user.tenant_id,
                        email=user.email,
                        full_name=user.name,
                        role=user.role.value,
                        is_active=True,
                        metadata={"token": user.token, "permissions": user.permissions},
                    )
                except Exception:
                    pass

            return 200, {
                "status": "SUCCESS",
                "message": f"User '{user.name}' successfully onboarded.",
                "user": {
                    "user_id": user.user_id,
                    "name": user.name,
                    "email": user.email,
                    "role": user.role.value,
                    "tenant_id": user.tenant_id,
                    "status": user.status,
                    "token": user.token,
                    "permissions": user.permissions,
                }
            }
        except Exception as e:
            return 400, {"status": "ERROR", "message": str(e)}

    def onboard_facility_api(self, payload: dict, tenant_id: Optional[str] = None) -> tuple:
        try:
            t_id = payload.get("tenant_id") or tenant_id or self.default_tenant_id
            app = self.get_tenant_app(t_id)
            tech_str = payload.get("technology", "SOLAR_PV").upper()
            tech = TechnologyType[tech_str]
            req = FacilityOnboardingRequest(
                facility_id=payload.get("facility_id", "").strip(),
                name=payload.get("name", "").strip(),
                portfolio_id=payload.get("portfolio_id", "PORT-SW-UTILITY").strip(),
                technology=tech,
                latitude=float(payload.get("latitude", 0.0)),
                longitude=float(payload.get("longitude", 0.0)),
                rated_capacity_mw=float(payload.get("rated_capacity_mw", 10.0)),
                metadata=payload.get("metadata", {}),
            )
            res = self.onboarding.onboard_facility(
                app,
                req,
                actor_id="admin-web",
            )
            status_code = 200 if res.status == "SUCCESS" else 400

            if res.status == "SUCCESS" and self.db.test_connection():
                try:
                    self.db.sync_site(
                        site_id=req.facility_id,
                        tenant_id=t_id,
                        portfolio_id=req.portfolio_id,
                        name=req.name,
                        code=req.facility_id,
                        latitude=req.latitude,
                        longitude=req.longitude,
                        rated_capacity_mw=req.rated_capacity_mw,
                        technology=req.technology.value,
                    )
                except Exception:
                    pass

            return status_code, {
                "status": res.status,
                "entity_id": res.entity_id,
                "entity_type": res.entity_type,
                "message": res.message,
                "details": res.details,
            }
        except Exception as e:
            return 400, {"status": "ERROR", "message": str(e)}

    def onboard_device_api(self, payload: dict, tenant_id: Optional[str] = None) -> tuple:
        try:
            t_id = payload.get("tenant_id") or tenant_id or self.default_tenant_id
            app = self.get_tenant_app(t_id)
            req = DeviceOnboardingRequest(
                device_id=payload.get("device_id", "").strip(),
                facility_id=payload.get("facility_id", "").strip(),
                name=payload.get("name", "").strip(),
                asset_type=payload.get("asset_type", "INVERTER").strip(),
                model=payload.get("model", "Generic-2026").strip(),
                rated_power_kw=float(payload.get("rated_power_kw", 1000.0)),
                device_secret=payload.get("device_secret") or None,
                provision_digital_twin=bool(payload.get("provision_digital_twin", True)),
                metadata=payload.get("metadata", {}),
            )
            res = self.onboarding.onboard_device(
                app,
                req,
                actor_id="admin-web",
            )
            status_code = 200 if res.status == "SUCCESS" else 400

            if res.status == "SUCCESS" and self.db.test_connection():
                try:
                    self.db.sync_asset(
                        asset_id=req.device_id,
                        tenant_id=t_id,
                        site_id=req.facility_id,
                        name=req.name,
                        code=req.device_id,
                        asset_type=req.asset_type,
                        model=req.model,
                        rated_power_kw=req.rated_power_kw,
                    )
                except Exception:
                    pass

            return status_code, {
                "status": res.status,
                "entity_id": res.entity_id,
                "entity_type": res.entity_type,
                "message": res.message,
                "details": res.details,
            }
        except Exception as e:
            return 400, {"status": "ERROR", "message": str(e)}

    def onboard_tenant_api(self, payload: dict) -> tuple:
        """Onboards a new corporate organization tenant with administrative contact."""
        try:
            tenant_id = payload.get("tenant_id", "").strip().upper()
            if not tenant_id:
                return 400, {"status": "ERROR", "message": "Tenant ID is required"}
            if not tenant_id.startswith("ORG-"):
                tenant_id = f"ORG-{tenant_id}"

            name = payload.get("name", "").strip() or f"Organization {tenant_id}"
            code = payload.get("code", "").strip().upper() or tenant_id.replace("ORG-", "")
            tier = payload.get("billing_tier", "ENTERPRISE").upper()
            admin_name = payload.get("admin_name", "Chief Engineer").strip()
            admin_email = payload.get("admin_email", f"admin@{code.lower()}.energy").strip()

            req = TenantOnboardingRequest(
                tenant_id=tenant_id,
                name=name,
                code=code,
                billing_tier=tier,
                admin_name=admin_name,
                admin_email=admin_email,
            )
            res = self.onboarding.onboard_tenant(req)
            if res.status != "SUCCESS":
                return 400, {"status": "ERROR", "message": res.message}

            app = self.get_tenant_app(tenant_id)
            admin_user = self.onboarding.onboard_user(
                name=admin_name,
                email=admin_email,
                role=SecurityRole.CHIEF_ENGINEER,
                tenant_id=tenant_id,
                actor_id="TENANT_PROVISIONER",
                audit_logger=app.audit_logger,
                auth_manager=app.auth_manager,
            )

            if self.db.test_connection():
                self.db.sync_organisation(tenant_id=tenant_id, name=name, code=code, billing_tier=tier)
                self.db.sync_user(
                    user_id=admin_user.user_id,
                    tenant_id=tenant_id,
                    email=admin_user.email,
                    full_name=admin_user.name,
                    role=admin_user.role.value,
                    is_active=True,
                    metadata={"token": admin_user.token, "permissions": admin_user.permissions},
                )

            return 200, {
                "status": "SUCCESS",
                "tenant_id": tenant_id,
                "name": name,
                "admin_user_id": admin_user.user_id,
                "admin_email": admin_user.email,
                "admin_token": admin_user.token,
                "message": f"Tenant '{name}' ({tenant_id}) successfully enrolled with administrator {admin_name}.",
            }
        except Exception as e:
            return 400, {"status": "ERROR", "message": str(e)}

    def update_user_role_api(self, payload: dict, tenant_id: Optional[str] = None) -> tuple:
        """Updates a user's role and permissions."""
        user_id = payload.get("user_id")
        new_role_str = payload.get("role")
        if not user_id or not new_role_str:
            return 400, {"status": "ERROR", "message": "user_id and role are required"}

        try:
            role_enum = SecurityRole[new_role_str.upper()]
        except KeyError:
            return 400, {"status": "ERROR", "message": f"Invalid role '{new_role_str}'. Valid roles: {[r.value for r in SecurityRole]}"}

        user = self.onboarding.get_user(user_id)
        if not user:
            return 404, {"status": "ERROR", "message": f"User '{user_id}' not found"}

        app = self.get_tenant_app(user.tenant_id)
        updated_user = self.onboarding.update_user_role(
            user_id=user_id,
            new_role=role_enum,
            actor_id=payload.get("actor_id", "SECURITY_ADMIN"),
            audit_logger=app.audit_logger,
        )
        if self.db.test_connection():
            self.db.update_user_role_pg(user_id=user_id, role=role_enum.value)

        return 200, {
            "status": "SUCCESS",
            "user_id": user_id,
            "role": updated_user.role.value,
            "permissions": updated_user.permissions,
            "message": f"Role updated to {updated_user.role.value} for user {updated_user.name}.",
        }

    def toggle_user_status_api(self, payload: dict, tenant_id: Optional[str] = None) -> tuple:
        """Toggles user between ACTIVE and SUSPENDED status."""
        user_id = payload.get("user_id")
        target_status = payload.get("status")
        if not user_id or not target_status:
            return 400, {"status": "ERROR", "message": "user_id and status are required"}

        user = self.onboarding.get_user(user_id)
        if not user:
            return 404, {"status": "ERROR", "message": f"User '{user_id}' not found"}

        app = self.get_tenant_app(user.tenant_id)
        try:
            updated_user = self.onboarding.update_user_status(
                user_id=user_id,
                status=target_status,
                actor_id=payload.get("actor_id", "SECURITY_ADMIN"),
                audit_logger=app.audit_logger,
            )
            is_active = (updated_user.status == "ACTIVE")
            if self.db.test_connection():
                self.db.update_user_status_pg(user_id=user_id, is_active=is_active)

            return 200, {
                "status": "SUCCESS",
                "user_id": user_id,
                "new_status": updated_user.status,
                "message": f"User {updated_user.name} status updated to {updated_user.status}.",
            }
        except ValueError as ve:
            return 400, {"status": "ERROR", "message": str(ve)}

    def regenerate_user_token_api(self, payload: dict, tenant_id: Optional[str] = None) -> tuple:
        """Issues a new HMAC security token for a user."""
        user_id = payload.get("user_id")
        if not user_id:
            return 400, {"status": "ERROR", "message": "user_id is required"}

        user = self.onboarding.get_user(user_id)
        if not user:
            return 404, {"status": "ERROR", "message": f"User '{user_id}' not found"}

        app = self.get_tenant_app(user.tenant_id)
        new_token = self.onboarding.regenerate_user_token(
            user_id=user_id,
            auth_manager=app.auth_manager,
            actor_id=payload.get("actor_id", "SECURITY_ADMIN"),
            audit_logger=app.audit_logger,
        )
        if self.db.test_connection():
            self.db.sync_user(
                user_id=user.user_id,
                tenant_id=user.tenant_id,
                email=user.email,
                full_name=user.name,
                role=user.role.value,
                is_active=(user.status == "ACTIVE"),
                metadata={"token": new_token, "permissions": user.permissions},
            )

        return 200, {
            "status": "SUCCESS",
            "user_id": user_id,
            "token": new_token,
            "message": f"New HMAC security token issued for {user.name}.",
        }

    def get_database_status_data(self) -> dict:
        """Returns PostgreSQL diagnostic status."""
        return self.db.get_status()


GLOBAL_STATE = REAMPWebServerState()


def dispatch_api_request(method: str, path: str, payload: dict = None, headers: dict = None, query_params: dict = None) -> tuple:
    """
    Unified router for REGENOVA API requests with multi-tenant isolation.
    Returns (status_code: int, data: dict/list).
    Used by both standalone HTTP server and Apache mod_wsgi.
    """
    headers = headers or {}
    query_params = query_params or {}
    p = payload or {}

    tenant_id = (
        headers.get("X-Tenant-ID")
        or headers.get("x-tenant-id")
        or query_params.get("tenant_id")
        or (p.get("tenant_id") if isinstance(p, dict) else None)
        or GLOBAL_STATE.default_tenant_id
    )

    if method in ("GET", "HEAD"):
        if path == "/api/tenants":
            return 200, GLOBAL_STATE.get_tenants_data()
        elif path == "/api/overview":
            return 200, GLOBAL_STATE.get_overview_data(tenant_id)
        elif path == "/api/sites":
            return 200, GLOBAL_STATE.get_sites_data(tenant_id)
        elif path == "/api/assets":
            return 200, GLOBAL_STATE.get_assets_data(tenant_id)
        elif path.startswith("/api/asset/"):
            asset_id = path.split("/")[-1]
            return GLOBAL_STATE.get_asset_detail_data(asset_id, tenant_id)
        elif path == "/api/alerts":
            return 200, GLOBAL_STATE.get_alerts_data(tenant_id)
        elif path == "/api/work-orders":
            return 200, GLOBAL_STATE.get_work_orders_data(tenant_id)
        elif path == "/api/adaptations":
            return 200, GLOBAL_STATE.get_adaptations_data(tenant_id)
        elif path == "/api/audit-chain":
            return 200, GLOBAL_STATE.get_audit_chain_data(tenant_id)
        elif path == "/api/users":
            return 200, GLOBAL_STATE.get_users_data(tenant_id)
        elif path == "/api/database/status":
            return 200, GLOBAL_STATE.get_database_status_data()
    elif method == "POST":
        if path == "/api/onboarding/tenant":
            return GLOBAL_STATE.onboard_tenant_api(p)
        elif path == "/api/users/update-role":
            return GLOBAL_STATE.update_user_role_api(p, tenant_id)
        elif path == "/api/users/toggle-status":
            return GLOBAL_STATE.toggle_user_status_api(p, tenant_id)
        elif path == "/api/users/regenerate-token":
            return GLOBAL_STATE.regenerate_user_token_api(p, tenant_id)
        elif path == "/api/telemetry/inject":
            return 200, GLOBAL_STATE.inject_telemetry(p, tenant_id)
        elif path == "/api/alerts/acknowledge":
            return 200, GLOBAL_STATE.acknowledge_alert(p, tenant_id)
        elif path == "/api/alerts/resolve":
            return 200, GLOBAL_STATE.resolve_alert(p, tenant_id)
        elif path == "/api/work-orders/approve":
            return 200, GLOBAL_STATE.approve_work_order(p, tenant_id)
        elif path == "/api/adaptations/propose":
            return 200, GLOBAL_STATE.propose_adaptation(p, tenant_id)
        elif path == "/api/adaptations/approve":
            return 200, GLOBAL_STATE.approve_adaptation(p, tenant_id)
        elif path == "/api/onboarding/user":
            return GLOBAL_STATE.onboard_user_api(p, tenant_id)
        elif path == "/api/onboarding/facility":
            return GLOBAL_STATE.onboard_facility_api(p, tenant_id)
        elif path == "/api/onboarding/device":
            return GLOBAL_STATE.onboard_device_api(p, tenant_id)

    return 404, {"error": f"Endpoint '{path}' not found"}


class REAMPRequestHandler(SimpleHTTPRequestHandler):
    """HTTP Request Handler for standalone development server."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join(os.path.dirname(__file__), "web"), **kwargs)

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Tenant-ID")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Tenant-ID")
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            from urllib.parse import parse_qs
            query_params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            headers_dict = dict(self.headers)
            status_code, data = dispatch_api_request("GET", path, headers=headers_dict, query_params=query_params)
            self._send_json(data, status_code)
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body) if body else {}
        except Exception as e:
            self._send_json({"error": f"Invalid JSON body: {e}"}, status=400)
            return

        from urllib.parse import parse_qs
        query_params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        headers_dict = dict(self.headers)
        status_code, data = dispatch_api_request("POST", path, payload, headers=headers_dict, query_params=query_params)
        self._send_json(data, status_code)


def application(environ, start_response):
    """
    Standard WSGI application interface for Apache mod_wsgi.
    Handles API endpoints with JSON serialization and serves static UI assets.
    """
    method = environ.get("REQUEST_METHOD", "GET").upper()
    raw_path = environ.get("PATH_INFO", "/")

    # 1. CORS Preflight
    if method == "OPTIONS":
        headers = [
            ("Content-Type", "text/plain"),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Tenant-ID"),
        ]
        start_response("204 No Content", headers)
        return [b""]

    # 2. API Endpoints
    if raw_path.startswith("/api/"):
        payload = {}
        if method == "POST":
            try:
                content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
                if content_length > 0:
                    body = environ["wsgi.input"].read(content_length).decode("utf-8")
                    payload = json.loads(body) if body else {}
            except Exception as e:
                resp_bytes = json.dumps({"error": f"Invalid JSON payload: {e}"}).encode("utf-8")
                start_response("400 Bad Request", [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(resp_bytes))),
                ])
                return [resp_bytes]

        headers_dict = {
            "X-Tenant-ID": environ.get("HTTP_X_TENANT_ID"),
            "Authorization": environ.get("HTTP_AUTHORIZATION"),
            "Content-Type": environ.get("CONTENT_TYPE"),
        }
        from urllib.parse import parse_qs
        query_params = {k: v[0] for k, v in parse_qs(environ.get("QUERY_STRING", "")).items()}

        status_code, data = dispatch_api_request(method, raw_path, payload, headers=headers_dict, query_params=query_params)
        resp_bytes = json.dumps(data, default=str).encode("utf-8")
        status_text = "200 OK" if status_code == 200 else ("404 Not Found" if status_code == 404 else f"{status_code} Error")
        headers = [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(resp_bytes))),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Tenant-ID"),
        ]
        start_response(status_text, headers)
        if method == "HEAD":
            return [b""]
        return [resp_bytes]


    # 3. Static UI Assets
    web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
    subpath = raw_path.lstrip("/")
    if not subpath or subpath == "":
        subpath = "index.html"

    file_path = os.path.abspath(os.path.join(web_dir, subpath))
    # Path traversal protection
    if not file_path.startswith(web_dir) or not os.path.isfile(file_path):
        resp = b"404 Not Found"
        start_response("404 Not Found", [
            ("Content-Type", "text/plain"),
            ("Content-Length", str(len(resp))),
        ])
        return [resp]

    mime, _ = mimetypes.guess_type(file_path)
    if not mime:
        if file_path.endswith(".css"):
            mime = "text/css"
        elif file_path.endswith(".js"):
            mime = "application/javascript"
        else:
            mime = "application/octet-stream"

    with open(file_path, "rb") as f:
        file_content = f.read()

    headers = [
        ("Content-Type", mime),
        ("Content-Length", str(len(file_content))),
    ]
    start_response("200 OK", headers)
    return [file_content]


def run_server(port=8000):
    server_address = ("", port)
    httpd = HTTPServer(server_address, REAMPRequestHandler)
    print(f"================================================================")
    print(f" REGENOVA Web Application & WSGI Server Running")
    print(f" URL: http://localhost:{port}")
    print(f"================================================================")
    httpd.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port)
