# REAMP — Canonical Data Dictionary

**Document Identifier**: `REAMP-DAT-04`  
**Phase**: Phase 4 — Data Architecture and Telemetry Model  
**Status**: Approved / Canonical Design  
**Last Updated**: 2026-09-11  

---

## 1. Overview & Data Conventions

This document specifies the complete attribute dictionary for all 20 relational domain tables, the canonical telemetry hypertable, continuous aggregates, and standardized metric types in REAMP.

### Column Naming Standards:
- All identifiers use lowercase `snake_case`.
- Identifiers ending in `_id` denote UUID foreign keys or primary keys.
- Identifiers ending in `_at` denote `TIMESTAMPTZ` (UTC ISO-8601 timestamps).
- Numerical metrics include explicit unit suffixes where appropriate (e.g., `_kw`, `_kwh`, `_c`, `_m_per_s`, `_deg`, `_pct`).

---

## 2. Relational Metadata Tables

### 2.1 `organisations`
| Column | Type | Null | Default | PK/FK | Index | Description |
| :--- | :--- | :---: | :--- | :---: | :---: | :--- |
| `id` | UUID | No | `gen_random_uuid()` | PK | Yes | Unique organisation ID |
| `tenant_id` | UUID | No | `gen_random_uuid()` | UK | Yes | Multi-tenant isolation partition key |
| `name` | VARCHAR(255) | No | | | | Commercial organization name |
| `code` | VARCHAR(64) | No | | UK | Yes | Human-readable unique code (e.g. `ORG-PREI`) |
| `billing_tier` | VARCHAR(32) | No | `'ENTERPRISE'` | | | Subscription level (`COMMUNITY`, `PRO`, `ENTERPRISE`) |
| `created_at` | TIMESTAMPTZ | No | `NOW()` | | | Entity creation timestamp |
| `updated_at` | TIMESTAMPTZ | No | `NOW()` | | | Last modification timestamp |

### 2.2 `portfolios`
| Column | Type | Null | Default | PK/FK | Index | Description |
| :--- | :--- | :---: | :--- | :---: | :---: | :--- |
| `id` | UUID | No | `gen_random_uuid()` | PK | Yes | Portfolio ID |
| `tenant_id` | UUID | No | | FK | Yes | References `organisations(tenant_id)` |
| `organisation_id` | UUID | No | | FK | Yes | References `organisations(id)` ON DELETE CASCADE |
| `name` | VARCHAR(255) | No | | | | Portfolio display name |
| `code` | VARCHAR(64) | No | | | Yes | Portfolio code (e.g. `PORT-CA-DESERT`) |
| `region` | VARCHAR(128) | No | | | | Geographic operating region |
| `target_capacity_kw` | NUMERIC(12, 2) | No | | | | Planned total portfolio capacity in kW |
| `created_at` | TIMESTAMPTZ | No | `NOW()` | | | Timestamp |
| `updated_at` | TIMESTAMPTZ | No | `NOW()` | | | Timestamp |

### 2.3 `sites`
| Column | Type | Null | Default | PK/FK | Index | Description |
| :--- | :--- | :---: | :--- | :---: | :---: | :--- |
| `id` | UUID | No | `gen_random_uuid()` | PK | Yes | Site ID |
| `tenant_id` | UUID | No | | FK | Yes | References `organisations(tenant_id)` |
| `portfolio_id` | UUID | No | | FK | Yes | References `portfolios(id)` ON DELETE RESTRICT |
| `name` | VARCHAR(255) | No | | | | Site display name |
| `code` | VARCHAR(64) | No | | | Yes | Site code (e.g. `SITE-MOJAVE-01`) |
| `latitude` | NUMERIC(9, 6) | No | | | | Latitude in decimal degrees ($-90.0$ to $+90.0$) |
| `longitude` | NUMERIC(9, 6) | No | | | | Longitude in decimal degrees ($-180.0$ to $+180.0$) |
| `altitude_m` | NUMERIC(6, 1) | Yes | | | | Site elevation in meters above sea level |
| `timezone` | VARCHAR(64) | No | `'UTC'` | | | IANA timezone name (e.g. `America/Los_Angeles`) |
| `grid_voltage_kv` | NUMERIC(6, 2) | Yes | | | | Grid point of interconnection voltage in kV |
| `created_at` | TIMESTAMPTZ | No | `NOW()` | | | Timestamp |
| `updated_at` | TIMESTAMPTZ | No | `NOW()` | | | Timestamp |

### 2.4 `energy_systems`
| Column | Type | Null | Default | PK/FK | Index | Description |
| :--- | :--- | :---: | :--- | :---: | :---: | :--- |
| `id` | UUID | No | `gen_random_uuid()` | PK | Yes | Energy system ID |
| `tenant_id` | UUID | No | | FK | Yes | References `organisations(tenant_id)` |
| `site_id` | UUID | No | | FK | Yes | References `sites(id)` ON DELETE CASCADE |
| `name` | VARCHAR(255) | No | | | | Energy system name (e.g. `Mojave PV Array A`) |
| `code` | VARCHAR(64) | No | | | Yes | Energy system code (e.g. `SYS-PV-01`) |
| `technology_type` | VARCHAR(32) | No | | | Yes | Enum: `SOLAR_PV`, `WIND`, `BESS`, `HYBRID` |
| `nameplate_capacity_kw`| NUMERIC(12, 2)| No | | | | Total rated active capacity in kW |
| `lifecycle_state` | VARCHAR(32) | No | `'PLANNED'` | | Yes | Enum: `PLANNED`, `COMMISSIONED`, `OPERATIONAL`, etc. |
| `technology_metadata`| JSONB | No | `'{}'` | | GIN | Technology-specific adapter attributes |
| `created_at` | TIMESTAMPTZ | No | `NOW()` | | | Timestamp |
| `updated_at` | TIMESTAMPTZ | No | `NOW()` | | | Timestamp |

### 2.5 `assets`
| Column | Type | Null | Default | PK/FK | Index | Description |
| :--- | :--- | :---: | :--- | :---: | :---: | :--- |
| `id` | UUID | No | `gen_random_uuid()` | PK | Yes | Asset ID |
| `tenant_id` | UUID | No | | FK | Yes | References `organisations(tenant_id)` |
| `energy_system_id` | UUID | No | | FK | Yes | References `energy_systems(id)` ON DELETE CASCADE |
| `parent_asset_id` | UUID | Yes | | FK | Yes | References `assets(id)` (nested hierarchy) |
| `name` | VARCHAR(255) | No | | | | Asset name (e.g. `Inverter Station #03`) |
| `code` | VARCHAR(64) | No | | | Yes | Asset code (e.g. `INV-03`) |
| `asset_type` | VARCHAR(64) | No | | | Yes | `PV_INVERTER`, `WIND_TURBINE`, `BESS_CONTAINER`, `TRANSFORMER` |
| `lifecycle_state` | VARCHAR(32) | No | `'PLANNED'` | | Yes | Current lifecycle state |
| `manufacturer` | VARCHAR(128) | Yes | | | | Equipment vendor (e.g. `SMA`, `Vestas`, `Tesla`) |
| `model_number` | VARCHAR(128) | Yes | | | | Manufacturer model designation |
| `serial_number` | VARCHAR(128) | Yes | | | | Hardware serial number |
| `commissioning_date`| DATE | Yes | | | | Date of commercial operation |
| `warranty_expiration`| DATE | Yes | | | | Date warranty terms expire |
| `technology_metadata`| JSONB | No | `'{}'` | | GIN | Dynamic asset parameters |
| `created_at` | TIMESTAMPTZ | No | `NOW()` | | | Timestamp |
| `updated_at` | TIMESTAMPTZ | No | `NOW()` | | | Timestamp |

### 2.6 `components`
| Column | Type | Null | Default | PK/FK | Index | Description |
| :--- | :--- | :---: | :--- | :---: | :---: | :--- |
| `id` | UUID | No | `gen_random_uuid()` | PK | Yes | Component ID |
| `tenant_id` | UUID | No | | FK | Yes | References `organisations(tenant_id)` |
| `asset_id` | UUID | No | | FK | Yes | References `assets(id)` ON DELETE CASCADE |
| `parent_component_id`| UUID | Yes | | FK | Yes | References `components(id)` (sub-assemblies) |
| `name` | VARCHAR(255) | No | | | | Component name (e.g. `IGBT Module Phase A`) |
| `code` | VARCHAR(64) | No | | | Yes | Component code |
| `component_type` | VARCHAR(64) | No | | | Yes | `POWER_ELECTRONICS`, `BEARING`, `BATTERY_CELL`, `PITCH_SYSTEM` |
| `lifecycle_state` | VARCHAR(32) | No | `'OPERATIONAL'`| | | Current component state |
| `part_number` | VARCHAR(128) | Yes | | | | OEM part number |
| `serial_number` | VARCHAR(128) | Yes | | | | Component serial number |
| `created_at` | TIMESTAMPTZ | No | `NOW()` | | | Timestamp |
| `updated_at` | TIMESTAMPTZ | No | `NOW()` | | | Timestamp |

### 2.7 `sensors`
| Column | Type | Null | Default | PK/FK | Index | Description |
| :--- | :--- | :---: | :--- | :---: | :---: | :--- |
| `id` | UUID | No | `gen_random_uuid()` | PK | Yes | Sensor ID |
| `tenant_id` | UUID | No | | FK | Yes | References `organisations(tenant_id)` |
| `asset_id` | UUID | Yes | | FK | Yes | References `assets(id)` |
| `component_id` | UUID | Yes | | FK | Yes | References `components(id)` |
| `name` | VARCHAR(255) | No | | | | Sensor description (e.g. `Heatsink Temp`) |
| `code` | VARCHAR(64) | No | | | Yes | Sensor code (e.g. `SENS-HS-01`) |
| `sensor_type` | VARCHAR(64) | No | | | Yes | Telemetry classification |
| `unit_of_measure` | VARCHAR(32) | No | | | | Engineering unit (`kW`, `degC`, `W/m2`, `m/s`, `V`, `A`) |
| `sampling_interval_sec`| INTEGER | No | `1` | | | Standard sampling period in seconds |
| `modbus_address` | VARCHAR(32) | Yes | | | | Modbus register address (e.g. `30045`) |
| `opc_node_id` | VARCHAR(128) | Yes | | | | OPC UA NodeId string |
| `mqtt_topic` | VARCHAR(255) | Yes | | | | Dedicated MQTT subscription topic |
| `min_physical_range`| NUMERIC(12, 4)| Yes| | | | Lower bound of physical feasible range |
| `max_physical_range`| NUMERIC(12, 4)| Yes| | | | Upper bound of physical feasible range |
| `created_at` | TIMESTAMPTZ | No | `NOW()` | | | Timestamp |
| `updated_at` | TIMESTAMPTZ | No | `NOW()` | | | Timestamp |

---

## 3. Time-Series Hypertable: `telemetry_observations`

| Column | Type | Null | Default | PK/FK | Description |
| :--- | :--- | :---: | :--- | :---: | :--- |
| `timestamp` | TIMESTAMPTZ | No | | PK | Physical sampling instant (UTC) — Hypertable time dimension |
| `tenant_id` | UUID | No | | PK | Multi-tenant isolation key — Hypertable space partition |
| `asset_id` | UUID | No | | PK | Parent Asset UUID |
| `metric` | VARCHAR(64) | No | | PK | Metric key (e.g., `power_active_kw`) |
| `sensor_id` | UUID | No | | | Transducer Sensor UUID |
| `value` | DOUBLE PRECISION | No | | | Physical measured numerical value |
| `unit` | VARCHAR(32) | No | | | Canonical engineering unit string |
| `source` | VARCHAR(32) | No | `'SCADA'`| | Protocol origin (`SCADA`, `INVERTER_MODBUS`, `BMS_CAN`, etc.) |
| `quality` | VARCHAR(16) | No | `'VALID'`| | Status (`VALID`, `INVALID`, `MISSING`, `STALE`, `UNCERTAIN`) |
| `confidence` | REAL | No | `1.0` | | Calculated reliability score between `0.00` and `1.00` |
| `communication_status`| VARCHAR(16)| No | `'ONLINE'`| | Link status (`ONLINE`, `DEGRADED`, `OFFLINE`, `BUFFERED`) |

---

## 4. Standard Metric Catalogue

| Metric Code | Standard Unit | Applicable Technology | Description | Typical Physical Bounds |
| :--- | :--- | :--- | :--- | :--- |
| `power_active_kw` | `kW` | Solar PV, Wind, BESS, Hybrid | 3-phase real active electrical power | $[0.0, 1.25 \times P_{rated}]$ |
| `power_reactive_kvar`| `kVAR` | Solar PV, Wind, BESS | Reactive electrical power | $[-1.0 \times P_{rated}, +1.0 \times P_{rated}]$ |
| `voltage_ac_v` | `V` | All AC Assets | AC line-to-neutral or line-to-line RMS voltage | $[0.8 \times V_{nom}, 1.2 \times V_{nom}]$ |
| `current_ac_a` | `A` | All AC Assets | AC line current RMS | $[0.0, 1.5 \times I_{rated}]$ |
| `frequency_hz` | `Hz` | Grid Interconnection | Interconnection electrical grid frequency | $[45.0, 65.0]$ |
| `voltage_dc_v` | `V` | Solar PV, BESS | DC bus operating voltage | $[0.0, 1500.0]$ |
| `current_dc_a` | `A` | Solar PV, BESS | DC operating current | $[0.0, 3000.0]$ |
| `irradiance_poa_wm2` | `W/m2`| Solar PV | Plane of Array Solar Irradiance | $[0.0, 1500.0]$ |
| `irradiance_ghi_wm2` | `W/m2`| Solar PV | Global Horizontal Solar Irradiance | $[0.0, 1400.0]$ |
| `temp_module_c` | `degC` | Solar PV | Back-of-module surface temperature | $[-40.0, 105.0]$ |
| `temp_ambient_c` | `degC` | All Technologies | Ambient air weather temperature | $[-50.0, 60.0]$ |
| `wind_speed_ms` | `m/s` | Wind Turbines | Nacelle anemometer measured wind speed | $[0.0, 60.0]$ |
| `wind_direction_deg` | `deg` | Wind Turbines | Wind heading relative to true north | $[0.0, 360.0]$ |
| `rotor_speed_rpm` | `rpm` | Wind Turbines | Rotor rotational speed | $[0.0, 30.0]$ |
| `vibration_velocity_rms_mms`| `mm/s`| Wind Turbines, Motors | Gearbox bearing vibration velocity RMS | $[0.0, 50.0]$ |
| `state_of_charge_pct`| `%` | BESS | Battery rack State of Charge ($SoC$) | $[0.0, 100.0]$ |
| `state_of_health_pct`| `%` | BESS | Battery capacity State of Health ($SoH$) | $[0.0, 100.0]$ |
| `temp_cell_max_c` | `degC` | BESS | Maximum measured battery cell temperature | $[-20.0, 85.0]$ |
| `soiling_ratio` | `ratio` | Solar PV | Soiling derating ratio ($PR_{soiled} / PR_{clean}$) | $[0.0, 1.0]$ |
