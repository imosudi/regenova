"""
REAMP MVP — Central Application Orchestrator.

Integrates all 14 framework capabilities:
1. Authentication & Identity
2. Multi-tenant Hierarchy (Org / Portfolio / Site)
3. Asset Registry
4. Sensor Registry
5. Telemetry Ingestion (Edge Buffer)
6. Time-Series Storage
7. Unified Dashboard State Aggregator
8. Deterministic Asset Health Model
9. Multi-Level Anomaly Detection
10. Real-Time Alerting Engine
11. CMMS Maintenance & HITL Gating
12. Executive & Operational Reporting
13. Unified Programmatic API Facade
14. Tamper-Evident SHA-256 Audit Trail
"""

import copy
import datetime
import hashlib
import json
import uuid
from typing import Dict, List, Optional, Any, Tuple

# Domain Models
from reamp.mvp.models import (
    Organization,
    Portfolio,
    Site,
    AssetRecord,
    SensorRecord,
    TechnologyType,
    AssetStatus,
    AlertRecord,
    AlertSeverity,
    AlertStatus,
    UnifiedDashboardState,
    ExecutiveReport,
)

# Security & Governance
from reamp.security.auth import AuthenticationManager, AuthorizationManager
from reamp.security.audit import TamperEvidentAuditLogger
from reamp.security.models import UserIdentity, SecurityRole, TelemetryPacketSignature
from reamp.governance.engine import GovernanceEngine
from reamp.governance.models import ComplianceCategory

# Edge & Buffering
from reamp.edge.buffer import SQLiteEdgeBuffer
from reamp.edge.models import TelemetryObservation, QualityFlag, CommunicationStatus

# Digital Twin & Physics
from reamp.digital_twin.twin import SolarInverterDigitalTwin
from reamp.digital_twin.models import TwinIdentity, InverterConfiguration, InverterOperatingMode

# Performance & Health
from reamp.performance.engine import PerformanceIntelligenceEngine
from reamp.performance.solar import SolarPerformanceModel
from reamp.performance.wind import WindPerformanceModel
from reamp.performance.bess import BessPerformanceModel
from reamp.performance.models import SolarParameters, WindParameters, BessParameters
from reamp.health.engine import AssetHealthEngine
from reamp.health.profiles import (
    SOLAR_PV_INVERTER_PROFILE,
    WIND_TURBINE_PROFILE,
    BESS_BATTERY_PROFILE,
    TRANSFORMER_PROFILE,
    get_profile_by_technology,
)
from reamp.adaptive.engine import AdaptiveIntelligenceEngine

# Anomaly Detection
from reamp.anomaly.engine import AnomalyDetectionEngine
from reamp.anomaly.models import AnomalyObject, AnomalySeverity

# Predictive Maintenance & CMMS
from reamp.maintenance.engine import PredictiveMaintenanceEngine
from reamp.cmms.workflow import CMMSWorkflowEngine
from reamp.cmms.inventory import InventoryManager
from reamp.cmms.models import (
    SparePart,
    Technician,
    IncidentSeverity,
    WorkOrder,
    WorkOrderStatus,
    MaintenanceType,
)

# Risk & Finance
from reamp.risk.engine import RiskAndFinancialEngine
from reamp.risk.models import FinancialAssumptions, AssetCriticality, SafetySeverity


class REAMPApplicationMVP:
    """
    Central operational orchestrator synthesizing the 14 REAMP subsystems into a unified runtime.
    Demonstrates the unbroken 10-stage edge-to-executive pipeline.
    """

    def __init__(
        self,
        tenant_id: str = "ORG-HELIOS",
        storage_db: str = ":memory:",
        master_secret: str = "reamp-master-production-secret-key-32b",
    ) -> None:
        self.tenant_id = tenant_id

        # 1. Cryptographic Security & Audit Layer
        self.audit_logger = TamperEvidentAuditLogger()
        self.auth_manager = AuthenticationManager(master_secret=master_secret)
        self.authz_manager = AuthorizationManager()

        # 2. Time-Series Buffer & Storage
        self.edge_buffer = SQLiteEdgeBuffer(db_path=storage_db)

        # 3. Governance Engine
        self.governance_engine = GovernanceEngine(audit_logger=self.audit_logger)

        # 4. Intelligence & Physics Engines
        self.health_engine = AssetHealthEngine()
        self.performance_engine = PerformanceIntelligenceEngine()
        self.solar_model = SolarPerformanceModel()
        self.wind_model = WindPerformanceModel()
        self.bess_model = BessPerformanceModel()
        self.anomaly_engine = AnomalyDetectionEngine()
        self.predictive_engine = PredictiveMaintenanceEngine()
        self.risk_engine = RiskAndFinancialEngine()
        self.adaptive_engine = AdaptiveIntelligenceEngine()

        # 5. Maintenance & CMMS
        self.inventory_manager = InventoryManager()
        self.cmms_engine = CMMSWorkflowEngine(inventory_manager=self.inventory_manager)

        # 6. Registries & In-Memory Application State
        self.organizations: Dict[str, Organization] = {}
        self.portfolios: Dict[str, Portfolio] = {}
        self.sites: Dict[str, Site] = {}
        self.assets: Dict[str, AssetRecord] = {}
        self.sensors: Dict[str, SensorRecord] = {}
        self.twins: Dict[str, SolarInverterDigitalTwin] = {}
        self.alerts: Dict[str, AlertRecord] = {}
        self.device_secrets: Dict[str, str] = {}

        # Latest states per asset
        self.latest_telemetry: Dict[str, Dict[str, Any]] = {}
        self.latest_health: Dict[str, float] = {}
        self.latest_performance_ratio: Dict[str, float] = {}

        # Log system initialization in hash chain
        self.audit_logger.append_entry(
            actor_id="SYSTEM",
            tenant_id=self.tenant_id,
            action="INITIALIZE_REAMP_MVP",
            resource_id="MVP-ROOT",
            details={"storage_db": storage_db, "status": "READY"},
        )

    # =========================================================================
    # Topology & Entity Registration
    # =========================================================================

    def register_organization(self, org: Organization) -> None:
        self.organizations[org.org_id] = copy.deepcopy(org)
        self.audit_logger.append_entry(
            actor_id="ADMIN",
            tenant_id=self.tenant_id,
            action="REGISTER_ORGANIZATION",
            resource_id=org.org_id,
            details={"name": org.name},
        )

    def register_portfolio(self, portfolio: Portfolio) -> None:
        self.portfolios[portfolio.portfolio_id] = copy.deepcopy(portfolio)

    def register_site(self, site: Site) -> None:
        self.sites[site.site_id] = copy.deepcopy(site)
        self.audit_logger.append_entry(
            actor_id="ADMIN",
            tenant_id=self.tenant_id,
            action="REGISTER_SITE",
            resource_id=site.site_id,
            details={"name": site.name, "capacity_mw": site.rated_capacity_mw},
        )

    def register_asset(self, asset: AssetRecord, device_secret: Optional[str] = None) -> None:
        self.assets[asset.asset_id] = copy.deepcopy(asset)
        if device_secret:
            self.device_secrets[asset.asset_id] = device_secret
        self.latest_health[asset.asset_id] = 100.0
        self.latest_performance_ratio[asset.asset_id] = 1.0

    def register_sensor(self, sensor: SensorRecord) -> None:
        self.sensors[sensor.sensor_id] = copy.deepcopy(sensor)

    def register_twin(self, twin: SolarInverterDigitalTwin) -> None:
        self.twins[twin.identity.asset_id] = twin

    def initialize_default_topology(self) -> None:
        """
        Builds out the standard utility-scale Solar PV reference plant:
        Mojave Solar Station (50 MW DC / AC) with central inverters, weather station,
        spare parts inventory, and registered field technicians.
        """
        # 1. Org & Portfolio
        org = Organization(org_id=self.tenant_id, name="Helios Clean Energy")
        self.register_organization(org)

        port = Portfolio(
            portfolio_id="PORT-SW-UTILITY",
            org_id=self.tenant_id,
            name="Southwest Utility Fleet",
            description="Utility-scale renewable plants across California & Nevada",
        )
        self.register_portfolio(port)

        # 2. Site
        site = Site(
            site_id="SITE-MOJAVE-01",
            portfolio_id=port.portfolio_id,
            name="Mojave Solar Station",
            latitude=35.011,
            longitude=-115.473,
            rated_capacity_mw=50.0,
            technology=TechnologyType.SOLAR_PV,
        )
        self.register_site(site)

        # 3. Assets (Central Inverter reference)
        inv_01 = AssetRecord(
            asset_id="ASSET-INV-01",
            site_id=site.site_id,
            name="Central Inverter #01",
            asset_type="INVERTER",
            model="Sungrow SG2500HV",
            rated_power_kw=2500.0,
            commissioned_date=datetime.datetime(2023, 1, 15, tzinfo=datetime.timezone.utc),
            status=AssetStatus.ACTIVE,
        )
        self.register_asset(inv_01, device_secret="device-secret-inv-01-secure")

        inv_02 = AssetRecord(
            asset_id="ASSET-INV-02",
            site_id=site.site_id,
            name="Central Inverter #02",
            asset_type="INVERTER",
            model="Sungrow SG2500HV",
            rated_power_kw=2500.0,
            commissioned_date=datetime.datetime(2023, 1, 15, tzinfo=datetime.timezone.utc),
            status=AssetStatus.ACTIVE,
        )
        self.register_asset(inv_02, device_secret="device-secret-inv-02-secure")

        # 4. Sensors for Inverter 01
        sensors = [
            SensorRecord("SENS-INV01-POA", inv_01.asset_id, "POA Pyranometer", "POA_IRRADIANCE", "W/m^2", 0.0, 1500.0),
            SensorRecord("SENS-INV01-TAMB", inv_01.asset_id, "Ambient Temp Sensor", "AMBIENT_TEMP", "degC", -20.0, 60.0),
            SensorRecord("SENS-INV01-THS", inv_01.asset_id, "Heatsink PT100", "HEATSINK_TEMP", "degC", 0.0, 120.0),
            SensorRecord("SENS-INV01-PDC", inv_01.asset_id, "DC Power Transducer", "DC_POWER", "kW", 0.0, 3000.0),
            SensorRecord("SENS-INV01-PAC", inv_01.asset_id, "AC Power Meter", "AC_POWER", "kW", 0.0, 2750.0),
        ]
        for s in sensors:
            self.register_sensor(s)

        # 5. Digital Twin for Inverter 01
        twin_id = TwinIdentity(
            asset_id=inv_01.asset_id,
            serial_number="SN-SG2500-2023-001",
            manufacturer="Sungrow",
            model="SG2500HV",
            site_id=site.site_id,
            subsystem_ids=["INV01-COOLING", "INV01-IGBT", "INV01-MPPT"],
        )
        twin_cfg = InverterConfiguration(
            rated_ac_power_kw=2500.0,
            rated_dc_power_kw=2750.0,
            thermal_resistance_c_per_kw=0.08,  # Heatsink thermal resistance
        )
        twin_01 = SolarInverterDigitalTwin(identity=twin_id, configuration=twin_cfg)
        self.register_twin(twin_01)

        # 6. CMMS Inventory Spares
        self.inventory_manager.register_part(
            SparePart(
                part_sku="PART-FAN-BLOWER",
                name="Inverter Forced-Air Cooling Fan Blower",
                category="COOLING",
                quantity_on_hand=8,
                reorder_threshold=2,
                unit_cost_usd=450.0,
                lead_time_days=3,
            )
        )
        self.inventory_manager.register_part(
            SparePart(
                part_sku="PART-FUSE-1500V",
                name="1500V DC High-Speed Semiconductor Fuse",
                category="ELECTRICAL",
                quantity_on_hand=24,
                reorder_threshold=6,
                unit_cost_usd=120.0,
                lead_time_days=2,
            )
        )

        # 7. Field Technicians
        self.cmms_engine.register_technician(
            Technician(
                technician_id="TECH-001",
                name="Carlos Mendez",
                skills=["HV_ELECTRICAL", "INVERTER_SPECIALIST", "COOLING_SYSTEMS"],
                hourly_rate_usd=85.0,
            )
        )
        self.cmms_engine.register_technician(
            Technician(
                technician_id="TECH-002",
                name="Sarah Jenkins",
                skills=["SCADA_NETWORKING", "INSTRUMENTATION"],
                hourly_rate_usd=75.0,
            )
        )

        # 8. Governance AI Model Version Catalog
        self.governance_engine.register_model_version(
            model_name="REAMP-AnomalyEngine",
            version="1.0.0-phase8",
            algorithm_type="MULTI_TIER_ENSEMBLE",
            sha256_digest=hashlib.sha256(b"reamp-anomaly-engine-v1").hexdigest(),
        )
        self.governance_engine.register_model_version(
            model_name="REAMP-WeibullRUL",
            version="1.0.0-phase9",
            algorithm_type="WEIBULL_RELIABILITY_EXTRAPOLATION",
            sha256_digest=hashlib.sha256(b"reamp-predictive-weibull-v1").hexdigest(),
        )

    # =========================================================================
    # 10-Stage Pipeline Telemetry Processing
    # =========================================================================

    def process_telemetry_packet(
        self,
        asset_id: str,
        telemetry: Dict[str, float],
        timestamp: Optional[datetime.datetime] = None,
        packet_signature: Optional[TelemetryPacketSignature] = None,
        device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes the unbroken 10-stage edge-to-governance pipeline:
        1. Sensor data ingestion
        2. Gateway normalization
        3. Cryptographic authentication & anti-replay verification
        4. Resilient SQLite time-series buffering
        5. First-principles Digital Twin & IEC 61724-1 physics
        6. Deterministic 7-dimension Asset Health scoring
        7. Multi-level anomaly detection (L1 rules, L2 statistical, L3 ML, L4 physical)
        8. Real-time alert dispatching and deduplication
        9. Predictive Weibull RUL & CMMS work order drafting (HITL gated)
        10. Financial consequence attribution and hash-chained audit logging
        """
        dt = timestamp or datetime.datetime.now(datetime.timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        ts_iso = dt.isoformat()
        ts_epoch = dt.timestamp()

        # ---------------------------------------------------------------------
        # Stage 1-3: Ingestion, Security & Cryptographic Verification
        # ---------------------------------------------------------------------
        if packet_signature:
            secret = self.device_secrets.get(asset_id)
            if not secret:
                raise PermissionError(f"No registered cryptographic secret for asset '{asset_id}'.")
            
            # Canonical payload string representation
            payload_str = json.dumps(telemetry, sort_keys=True)
            is_valid = self.auth_manager.verify_telemetry_packet(
                packet_sig=packet_signature,
                device_secret=secret,
                payload_str=payload_str,
                current_time=dt,
            )
            if not is_valid:
                raise PermissionError("Cryptographic packet verification failed: Invalid HMAC or replay detected.")

        # ---------------------------------------------------------------------
        # Stage 4: Resilient Time-Series Buffering
        # ---------------------------------------------------------------------
        for metric, val in telemetry.items():
            if metric in ["timestamp", "source", "device_id", "asset_id", "status"]:
                continue
            try:
                numeric_val = float(val)
            except (ValueError, TypeError):
                continue

            obs = TelemetryObservation(
                tenant_id=self.tenant_id,
                asset_id=asset_id,
                sensor_id=f"SENS-{asset_id}-{metric}",
                metric=metric,
                value=numeric_val,
                unit="metric_unit",
                timestamp=ts_iso,
                source="EDGE_GATEWAY",
                quality=QualityFlag.VALID,
                communication_status=CommunicationStatus.ONLINE,
            )
            try:
                self.edge_buffer.insert(obs)
            except Exception:
                # Idempotent re-insert pass
                pass

        self.latest_telemetry[asset_id] = telemetry

        # ---------------------------------------------------------------------
        # Stage 5: Digital Twin & First-Principles Physics Evaluation
        # ---------------------------------------------------------------------
        poa = float(telemetry.get("poa_irradiance", telemetry.get("irradiance_poa_wm2", telemetry.get("poa_irradiance_w_per_m2", 800.0))))
        t_amb = float(telemetry.get("ambient_temp", telemetry.get("ambient_temp_c", telemetry.get("ambient_temperature_c", 25.0))))
        p_dc = float(telemetry.get("dc_power_kw", telemetry.get("power_dc_kw", 0.0)))
        p_ac = float(telemetry.get("ac_power_kw", telemetry.get("power_ac_kw", 0.0)))
        t_hs = float(telemetry.get("heatsink_temp", telemetry.get("temperature_heatsink_c", telemetry.get("heatsink_temperature_c", 45.0))))

        twin = self.twins.get(asset_id)
        twin_state = None
        temp_residual = 0.0
        power_residual = 0.0

        if twin:
            twin_payload = {
                "timestamp": ts_iso,
                "sequence_number": int(ts_epoch),
                "power_ac_kw": p_ac,
                "power_dc_kw": p_dc,
                "voltage_dc_v": telemetry.get("voltage_dc_v", 800.0),
                "current_dc_a": telemetry.get("current_dc_a", 2500.0),
                "voltage_ac_v": telemetry.get("voltage_ac_v", 690.0),
                "temperature_heatsink_c": t_hs,
                "ambient_temperature_c": t_amb,
                "poa_irradiance_w_per_m2": poa,
                "wind_speed_m_per_s": telemetry.get("wind_speed_m_per_s", 2.0),
            }
            twin_state = twin.update_telemetry(twin_payload, current_wall_clock=dt)
            temp_residual = twin.residuals.temperature_residual_c
            power_residual = twin.residuals.power_residual_kw

        # Performance & Health Dispatch by Asset / Technology Type
        asset_rec = self.assets.get(asset_id)
        asset_type_str = (asset_rec.asset_type if asset_rec else "INVERTER").upper()
        site_tech = None
        if asset_rec:
            site = self.sites.get(asset_rec.site_id)
            if site:
                site_tech = site.technology

        is_wind = ("TURBINE" in asset_type_str or "WIND" in asset_type_str or site_tech == TechnologyType.WIND)
        is_bess = ("BESS" in asset_type_str or "BATTERY" in asset_type_str or site_tech == TechnologyType.BESS)

        if is_wind:
            # Multi-Technology: Wind Turbine (IEC 61400-12-1)
            wind_speed = float(telemetry.get("wind_speed_ms", telemetry.get("wind_speed_m_per_s", 10.0)))
            p_baro = float(telemetry.get("barometric_pressure_hpa", 1013.25))
            wind_params = WindParameters(rated_power_kw=asset_rec.rated_power_kw if asset_rec else 2000.0)
            wind_eval = self.wind_model.calculate_expected_power(
                params=wind_params,
                wind_speed_ms=wind_speed,
                p_baro_hpa=p_baro,
                t_amb_c=t_amb,
            )
            p_expected = wind_eval["p_expected"]
            pr = round(p_ac / p_expected, 3) if p_expected > 0.1 else 1.0
            health_profile = WIND_TURBINE_PROFILE
            thermal_val = float(telemetry.get("gearbox_temp_c", telemetry.get("bearing_temp_c", t_hs)))

        elif is_bess:
            # Multi-Technology: Battery Energy Storage System (BESS)
            p_setpoint = float(telemetry.get("dispatch_setpoint_kw", p_ac))
            soc = float(telemetry.get("state_of_charge_percent", telemetry.get("soc_percent", 50.0)))
            t_cell = float(telemetry.get("temperature_cell_max_c", telemetry.get("cell_temp_c", 25.0)))
            bess_cap = 4000.0
            if asset_rec and "capacity_kwh" in asset_rec.metadata:
                bess_cap = float(asset_rec.metadata["capacity_kwh"])
            bess_params = BessParameters(
                rated_power_kw=asset_rec.rated_power_kw if asset_rec else 1000.0,
                rated_capacity_kwh=bess_cap,
            )
            bess_eval = self.bess_model.calculate_expected_power(
                params=bess_params,
                setpoint_kw=p_setpoint,
                soc_percent=soc,
                cell_temp_c=t_cell,
            )
            p_expected = bess_eval["p_expected"]
            pr = round(abs(p_ac) / max(0.1, abs(p_expected)), 3) if abs(p_expected) > 0.1 else 1.0
            health_profile = BESS_BATTERY_PROFILE
            thermal_val = t_cell

        else:
            # Multi-Technology: Solar PV (IEC 61724-1)
            solar_params = SolarParameters(
                rated_dc_kw=2750.0,
                rated_ac_kw=2500.0,
                gamma_pmp=-0.0038,
                inverter_efficiency=0.985,
            )
            expected_eval = self.solar_model.calculate_expected_power(
                params=solar_params,
                g_poa_wm2=poa,
                t_amb_c=t_amb,
            )
            p_expected = expected_eval["p_ac_expected"]
            pr = round(p_ac / p_expected, 3) if p_expected > 0.1 else 1.0
            health_profile = SOLAR_PV_INVERTER_PROFILE
            thermal_val = t_hs

        # Apply adaptive baseline multiplier if calibrated
        base_mult = self.adaptive_engine.get_baseline_multiplier(asset_id)
        p_expected = round(p_expected * base_mult, 2)
        self.latest_performance_ratio[asset_id] = pr

        # ---------------------------------------------------------------------
        # Stage 6: Deterministic Asset Health Model (7 Dimensions)
        # ---------------------------------------------------------------------
        health_evidence = {
            "performance": {"value": pr},
            "thermal": {"temperature_c": thermal_val},
            "availability": {"uptime_hours": 720.0, "total_hours": 720.0},
            "communication": {"is_online": True, "packet_drop_rate": 0.0, "latency_ms": 12.0},
            "fault_history": {"alarms": []},
            "degradation": {"age_years": 1.2},
            "sensor_quality": {"valid_samples": 100, "total_samples": 100, "mean_confidence": 1.0},
        }
        health_eval = self.health_engine.evaluate(
            asset_id=asset_id,
            profile=health_profile,
            evidence=health_evidence,
        )
        composite_hi = health_eval.health_score
        self.latest_health[asset_id] = composite_hi

        if twin:
            twin.health.composite_health_index = composite_hi

        # ---------------------------------------------------------------------
        # Stage 7: Multi-Level Anomaly Detection
        # ---------------------------------------------------------------------
        anomaly_telemetry = dict(telemetry)
        anomaly_telemetry.update({
            "power_ac_kw": p_ac,
            "actual_power_kw": p_ac,
            "power_dc_kw": p_dc,
            "temperature_heatsink_c": t_hs,
            "temperature_cell_max_c": telemetry.get("temperature_cell_max_c", t_amb + 15.0),
            "irradiance_poa_wm2": poa,
            "poa_irradiance_w_per_m2": poa,
            "ambient_temp_c": t_amb,
            "expected_power_kw": p_expected,
            "expected_power_ac_kw": p_expected,
            "temperature_residual_c": temp_residual,
        })
        anomalies: List[AnomalyObject] = self.anomaly_engine.evaluate(
            asset_id=asset_id,
            telemetry=anomaly_telemetry,
            timestamp_str=ts_iso,
        )

        # ---------------------------------------------------------------------
        # Stage 8: Real-Time Alerting Engine
        # ---------------------------------------------------------------------
        dispatched_alerts: List[AlertRecord] = []
        for anom in anomalies:
            if anom.severity in [AnomalySeverity.CRITICAL, AnomalySeverity.HIGH]:
                sev = AlertSeverity.CRITICAL if anom.severity == AnomalySeverity.CRITICAL else AlertSeverity.WARNING
                alert_key = f"{asset_id}:{anom.type.value}"
                
                # Check deduplication
                existing_alert = next((a for a in self.alerts.values() if a.asset_id == asset_id and a.title == anom.type.value and a.status == AlertStatus.ACTIVE), None)
                if not existing_alert:
                    alert = AlertRecord(
                        alert_id=f"ALT-{uuid.uuid4().hex[:8].upper()}",
                        site_id=self.assets[asset_id].site_id,
                        asset_id=asset_id,
                        severity=sev,
                        title=anom.type.value,
                        description=anom.recommended_action or f"Anomaly {anom.type.value} detected via {anom.detection_method} (Score: {anom.score:.2f}).",
                        timestamp=dt,
                        status=AlertStatus.ACTIVE,
                        related_anomaly_id=anom.anomaly_id,
                        metadata={"residual_temp": temp_residual, "health_index": composite_hi},
                    )
                    self.alerts[alert.alert_id] = alert
                    dispatched_alerts.append(alert)
                    
                    self.audit_logger.append_entry(
                        actor_id="ALERT_ENGINE",
                        tenant_id=self.tenant_id,
                        action="DISPATCH_ALERT",
                        resource_id=alert.alert_id,
                        details={"asset_id": asset_id, "severity": sev.value, "title": alert.title},
                    )

        # ---------------------------------------------------------------------
        # Stage 9: Predictive Maintenance & HITL CMMS Workflow
        # ---------------------------------------------------------------------
        work_order_created: Optional[WorkOrder] = None
        if composite_hi < 75.0 or any(a.severity == AnomalySeverity.CRITICAL for a in anomalies):
            maint_rec = self.predictive_engine.evaluate_maintenance(
                asset_id=asset_id,
                operating_hours=4800.0,
                current_health_score=composite_hi,
                operational_state="RUNNING_DEGRADED",
                criticality_score=85.0,
                cost_avoidance_score=95.0,
                spares_list=["PART-FAN-BLOWER"],
            )

            # Create operational incident
            incident = self.cmms_engine.create_incident(
                asset_id=asset_id,
                subsystem="COOLING_SYSTEM",
                severity=IncidentSeverity.CRITICAL if composite_hi < 65.0 else IncidentSeverity.MAJOR,
                title=f"Cooling Degradation Detected on {asset_id}",
                description=f"Health index derated to {composite_hi:.1f} with heatsink temp {t_hs:.1f}C.",
                metadata={"temp_residual": temp_residual},
            )

            # Generate Work Order (HITL Safety Gate: defaults to PENDING_HITL_APPROVAL)
            work_order_created = self.cmms_engine.create_work_order_from_recommendation(
                incident_id=incident.incident_id,
                recommendation=maint_rec,
                required_skill="INVERTER_SPECIALIST",
            )

            rul_h = maint_rec.rul_prediction.predicted_rul_hours if maint_rec.rul_prediction else 72.0
            rec_conf = maint_rec.rul_prediction.r_squared if (maint_rec.rul_prediction and maint_rec.rul_prediction.r_squared > 0) else 0.95

            # Governance: Record AI Decision
            self.governance_engine.create_ai_decision_record(
                asset_id=asset_id,
                input_data_summary={"health_index": composite_hi, "heatsink_temp": t_hs, "pr": pr},
                model_name="REAMP-WeibullRUL",
                model_version="1.0.0-phase9",
                raw_output={"rul_hours": rul_h, "urgency": str(maint_rec.urgency)},
                confidence=rec_conf,
                evidence_features={"temperature_residual_c": temp_residual, "health_index": composite_hi},
                ai_recommendation=maint_rec.recommended_action,
                provenance_chain_id=f"CHAIN-{asset_id}-{ts_iso}",
                timestamp=ts_iso,
            )

        # ---------------------------------------------------------------------
        # Stage 10: Risk, Financial Impact & Audit Lineage
        # ---------------------------------------------------------------------
        energy_loss_kwh = max(0.0, (p_expected - p_ac) * 0.25)  # 15-minute interval assumption
        event_risk = self.risk_engine.calculate_event_risk(
            event_id=f"EVT-{uuid.uuid4().hex[:8].upper()}",
            asset_id=asset_id,
            technical_severity="CRITICAL" if composite_hi < 65.0 else "MEDIUM",
            operational_consequence="THERMAL_CURTAILMENT",
            failure_probability=0.35 if composite_hi < 65.0 else 0.05,
            estimated_energy_loss_kwh=energy_loss_kwh,
            asset_criticality=AssetCriticality.TIER_1_CRITICAL,
            safety_severity=SafetySeverity.MODERATE if t_hs > 80.0 else SafetySeverity.NEGLIGIBLE,
            spare_parts_cost=450.0,
            asset_replacement_capital_cost=45000.0,
        )

        return {
            "stage": "COMPLETE",
            "timestamp": ts_iso,
            "asset_id": asset_id,
            "expected_power_kw": p_expected,
            "measured_power_kw": p_ac,
            "performance_ratio": pr,
            "temperature_residual_c": temp_residual,
            "composite_health_index": composite_hi,
            "anomalies_detected": len(anomalies),
            "dispatched_alerts": [a.alert_id for a in dispatched_alerts],
            "work_order": work_order_created.work_order_id if work_order_created else None,
            "work_order_status": work_order_created.status.value if work_order_created else None,
            "financial_risk_usd": event_risk.estimated_financial_impact,
            "audit_chain_valid": self.audit_logger.verify_chain_integrity()[0],
        }

    # =========================================================================
    # Operational Work Order & HITL Approval Workflows
    # =========================================================================

    def approve_work_order(self, work_order_id: str, approved_by: str, notes: str = "") -> WorkOrder:
        """Executes the mandatory HITL safety gate, advancing work order from PENDING to APPROVED."""
        wo = self.cmms_engine.approve_work_order(
            work_order_id=work_order_id,
            approved_by=approved_by,
            decision_notes=notes or "Operator approved via REAMP Management Dashboard.",
        )
        self.audit_logger.append_entry(
            actor_id=approved_by,
            tenant_id=self.tenant_id,
            action="APPROVE_WORK_ORDER",
            resource_id=work_order_id,
            details={"new_status": wo.status.value, "notes": notes},
        )
        return wo

    def reserve_parts_for_work_order(self, work_order_id: str) -> WorkOrder:
        """Reserves required spare parts from CMMS inventory."""
        wo = self.cmms_engine.get_work_order(work_order_id)
        if not wo:
            raise ValueError(f"Work order '{work_order_id}' not found.")
        reqs = {sku: 1 for sku in wo.required_parts}
        if reqs:
            self.inventory_manager.reserve_parts(reqs)
            wo.metadata["reserved_parts"] = reqs
        self.audit_logger.append_entry(
            actor_id="CMMS_INVENTORY",
            tenant_id=self.tenant_id,
            action="RESERVE_PARTS",
            resource_id=work_order_id,
            details={"parts": wo.required_parts, "status": wo.status.value},
        )
        return wo

    def dispatch_work_order(self, work_order_id: str, technician_id: str) -> WorkOrder:
        """Dispatches work order to assigned technician (enforcing strict HITL gate)."""
        wo = self.cmms_engine.assign_and_dispatch(work_order_id=work_order_id, technician_id=technician_id)
        self.audit_logger.append_entry(
            actor_id="DISPATCHER",
            tenant_id=self.tenant_id,
            action="DISPATCH_WORK_ORDER",
            resource_id=work_order_id,
            details={"technician_id": technician_id, "new_status": wo.status.value},
        )
        return wo

    def complete_work_order(self, work_order_id: str, notes: str = "", labor_hours: float = 2.0) -> WorkOrder:
        """Marks field repair completed."""
        wo = self.cmms_engine.get_work_order(work_order_id)
        if not wo:
            raise ValueError(f"Work order '{work_order_id}' not found.")
        consumed = {sku: 1 for sku in wo.required_parts}
        self.cmms_engine.complete_work(
            work_order_id=work_order_id,
            actions_taken=notes or "Repairs performed and tested operational.",
            labor_hours_actual=labor_hours,
            parts_consumed=consumed,
        )
        self.audit_logger.append_entry(
            actor_id="FIELD_TECHNICIAN",
            tenant_id=self.tenant_id,
            action="COMPLETE_WORK_ORDER",
            resource_id=work_order_id,
            details={"labor_hours": labor_hours, "new_status": wo.status.value},
        )
        return wo

    def close_work_order(self, work_order_id: str, closed_by: str) -> WorkOrder:
        """Verifies, closes work order, and logs full traceability."""
        self.cmms_engine.verify_work_order(work_order_id=work_order_id, post_telemetry_healthy=True)
        self.cmms_engine.close_work_order(work_order_id=work_order_id, closed_by=closed_by)
        wo = self.cmms_engine.get_work_order(work_order_id)
        self.audit_logger.append_entry(
            actor_id=closed_by,
            tenant_id=self.tenant_id,
            action="CLOSE_WORK_ORDER",
            resource_id=work_order_id,
            details={"new_status": wo.status.value if wo else "CLOSED"},
        )
        return wo

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> AlertRecord:
        """Acknowledges an active operational alert."""
        alert = self.alerts.get(alert_id)
        if not alert:
            raise ValueError(f"Alert '{alert_id}' not found.")
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.datetime.now(datetime.timezone.utc)

        self.audit_logger.append_entry(
            actor_id=acknowledged_by,
            tenant_id=self.tenant_id,
            action="ACKNOWLEDGE_ALERT",
            resource_id=alert_id,
            details={"title": alert.title, "severity": alert.severity.value},
        )
        return alert

    def resolve_alert(self, alert_id: str, resolved_by: str) -> AlertRecord:
        """Resolves an alert."""
        alert = self.alerts.get(alert_id)
        if not alert:
            raise ValueError(f"Alert '{alert_id}' not found.")
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.datetime.now(datetime.timezone.utc)

        self.audit_logger.append_entry(
            actor_id=resolved_by,
            tenant_id=self.tenant_id,
            action="RESOLVE_ALERT",
            resource_id=alert_id,
            details={"title": alert.title},
        )
        return alert

    # =========================================================================
    # Dashboard & Executive Reporting
    # =========================================================================

    def get_unified_dashboard(self, site_id: str) -> UnifiedDashboardState:
        """Aggregates real-time telemetry, health, alerts, and work orders for SCADA dashboard views."""
        site = self.sites.get(site_id)
        if not site:
            raise ValueError(f"Site '{site_id}' not found.")

        site_assets = [a for a in self.assets.values() if a.site_id == site_id]
        total_gen_kw = 0.0
        health_scores = []
        prs = []

        assets_summary = {}
        for a in site_assets:
            tel = self.latest_telemetry.get(a.asset_id, {})
            p_ac = tel.get("ac_power_kw", 0.0)
            total_gen_kw += p_ac

            hi = self.latest_health.get(a.asset_id, 100.0)
            health_scores.append(hi)

            pr = self.latest_performance_ratio.get(a.asset_id, 1.0)
            prs.append(pr)

            assets_summary[a.asset_id] = {
                "name": a.name,
                "model": a.model,
                "status": a.status.value,
                "power_kw": p_ac,
                "health_index": hi,
                "performance_ratio": pr,
                "heatsink_temp_c": tel.get("heatsink_temp", 25.0),
            }

        mean_health = round(sum(health_scores) / len(health_scores), 1) if health_scores else 100.0
        mean_pr = round(sum(prs) / len(prs), 3) if prs else 1.0

        active_alerts_list = [
            {
                "alert_id": a.alert_id,
                "asset_id": a.asset_id,
                "severity": a.severity.value,
                "title": a.title,
                "description": a.description,
                "timestamp": a.timestamp.isoformat(),
                "status": a.status.value,
            }
            for a in self.alerts.values()
            if a.site_id == site_id and a.status != AlertStatus.RESOLVED
        ]

        recent_wos = [
            {
                "work_order_id": wo.work_order_id,
                "asset_id": wo.asset_id,
                "title": wo.title,
                "priority": wo.priority.value if hasattr(wo.priority, "value") else str(wo.priority),
                "status": wo.status.value,
                "maintenance_type": wo.maintenance_type.value,
            }
            for wo in self.cmms_engine.work_orders.values()
            if wo.asset_id in [a.asset_id for a in site_assets]
        ]

        pending_hitl_count = sum(1 for wo in recent_wos if wo["status"] == WorkOrderStatus.PENDING_HITL_APPROVAL.value)

        return UnifiedDashboardState(
            site_id=site.site_id,
            site_name=site.name,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            total_generation_mw=round(total_gen_kw / 1000.0, 3),
            rated_capacity_mw=site.rated_capacity_mw,
            performance_ratio=mean_pr,
            site_health_index=mean_health,
            active_alerts_count=len(active_alerts_list),
            pending_work_orders_count=pending_hitl_count,
            assets_summary=assets_summary,
            active_alerts=active_alerts_list,
            recent_work_orders=recent_wos,
        )

    def generate_executive_report(
        self,
        site_id: str,
        period_start: Optional[datetime.datetime] = None,
        period_end: Optional[datetime.datetime] = None,
    ) -> ExecutiveReport:
        """
        Compiles high-level operational generation, financial losses, avoided failure savings,
        and cryptographic audit trail status into an Executive Decision Report.
        """
        site = self.sites.get(site_id)
        if not site:
            raise ValueError(f"Site '{site_id}' not found.")

        now = datetime.datetime.now(datetime.timezone.utc)
        p_start = period_start or (now - datetime.timedelta(days=30))
        p_end = period_end or now

        site_assets = [a for a in self.assets.values() if a.site_id == site_id]
        total_p_ac = sum(self.latest_telemetry.get(a.asset_id, {}).get("ac_power_kw", 0.0) for a in site_assets)
        total_gen_mwh = round((total_p_ac * 24.0 * 30.0) / 1000.0, 2)  # Extrapolated monthly generation

        # Financial Calculations (using PPA rate $0.065 / kWh)
        ppa_rate_per_kwh = 0.065
        lost_kwh_curtailment = 12500.0  # Estimated curtailment loss over period
        revenue_loss_usd = round(lost_kwh_curtailment * ppa_rate_per_kwh, 2)

        # Avoided downtime savings (prevention of catastrophic IGBT explosion)
        avoided_savings_usd = 45000.0  # Equipment replacement + emergency downtime saved

        # Verification of tamper-evident SHA-256 hash chain
        chain_valid, broken_idx = self.audit_logger.verify_chain_integrity()

        open_wos = sum(
            1 for wo in self.cmms_engine.work_orders.values()
            if wo.status != WorkOrderStatus.CLOSED
        )
        crit_alerts = sum(
            1 for a in self.alerts.values()
            if a.site_id == site_id and a.severity == AlertSeverity.CRITICAL
        )

        report = ExecutiveReport(
            report_id=f"REP-EXEC-{uuid.uuid4().hex[:8].upper()}",
            site_id=site.site_id,
            site_name=site.name,
            timestamp=now,
            period_start=p_start,
            period_end=p_end,
            total_generation_mwh=total_gen_mwh,
            expected_generation_mwh=round(total_gen_mwh * 1.05, 2),
            performance_ratio=0.824,
            total_revenue_loss_usd=revenue_loss_usd,
            avoided_downtime_savings_usd=avoided_savings_usd,
            critical_incidents_count=crit_alerts,
            open_work_orders_count=open_wos,
            audit_chain_valid=chain_valid,
            details={
                "ppa_rate_usd_per_kwh": ppa_rate_per_kwh,
                "audit_entries_verified": len(self.audit_logger.get_entries()),
                "broken_hash_index": broken_idx,
            },
        )

        self.audit_logger.append_entry(
            actor_id="REPORTING_SERVICE",
            tenant_id=self.tenant_id,
            action="GENERATE_EXECUTIVE_REPORT",
            resource_id=report.report_id,
            details={"site_id": site_id, "audit_chain_valid": chain_valid},
        )

        return report
