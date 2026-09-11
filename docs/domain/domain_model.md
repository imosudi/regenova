# REAMP — Core Domain Model Specification

**Document Identifier**: `REAMP-DOM-01`  
**Phase**: Phase 2 — Asset Ontology and Domain Model  
**Status**: Approved / Quality Gate Passed  
**Last Updated**: 2026-09-11  

---

## 1. Architectural Overview

The REAMP Domain Model enforces Clean Architecture principles. Domain entities encapsulate identity, invariants, state transitions, and business rules, remaining completely independent of database storage drivers, REST frameworks, or UI presentation code.

---

## 2. Core Enumerations

### `HierarchyLevel`
```text
ORGANISATION = 1
PORTFOLIO    = 2
PROJECT      = 3
SITE         = 4
ENERGY_SYSTEM= 5
ASSET        = 6
COMPONENT    = 7
SENSOR       = 8
```

### `TechnologyType`
```text
SOLAR_PV     = "SOLAR_PV"
WIND         = "WIND"
BESS         = "BESS"
HYBRID       = "HYBRID"
SUBSTATION   = "SUBSTATION"
GENERIC      = "GENERIC"
```

### `LifecycleState`
```text
PLANNED            = "PLANNED"
UNDER_CONSTRUCTION = "UNDER_CONSTRUCTION"
COMMISSIONED       = "COMMISSIONED"
OPERATIONAL        = "OPERATIONAL"
DERATED            = "DERATED"
DEGRADED           = "DEGRADED"
MAINTENANCE        = "MAINTENANCE"
STANDBY            = "STANDBY"
DECOMMISSIONED     = "DECOMMISSIONED"
```

### `SensorType`
```text
ELECTRICAL_VOLTAGE    = "ELECTRICAL_VOLTAGE"
ELECTRICAL_CURRENT    = "ELECTRICAL_CURRENT"
ELECTRICAL_POWER_ACTIVE = "ELECTRICAL_POWER_ACTIVE"
ELECTRICAL_FREQUENCY = "ELECTRICAL_FREQUENCY"
IRRADIANCE_POA        = "IRRADIANCE_POA"
IRRADIANCE_GHI        = "IRRADIANCE_GHI"
TEMPERATURE_AMBIENT   = "TEMPERATURE_AMBIENT"
TEMPERATURE_SURFACE   = "TEMPERATURE_SURFACE"
WIND_SPEED            = "WIND_SPEED"
WIND_DIRECTION        = "WIND_DIRECTION"
VIBRATION_VELOCITY    = "VIBRATION_VELOCITY"
PRESSURE_HYDRAULIC    = "PRESSURE_HYDRAULIC"
STATE_OF_CHARGE       = "STATE_OF_CHARGE"
STATE_OF_HEALTH       = "STATE_OF_HEALTH"
SOILING_RATIO         = "SOILING_RATIO"
```

---

## 3. Value Objects

Value Objects are immutable data structures defined strictly by their attributes rather than a persistent identity.

### `LocationValueObject`
```text
+ latitude: Float (-90.0 to +90.0)
+ longitude: Float (-180.0 to +180.0)
+ altitude_m: Optional[Float]
+ address: Optional[String]
+ timezone: String (e.g. "America/Los_Angeles", "UTC")
+ tilt_deg: Optional[Float] (For Solar PV arrays, 0 to 90)
+ azimuth_deg: Optional[Float] (For Solar PV arrays, 0 to 360)
+ hub_height_m: Optional[Float] (For Wind turbines)
```

### `CapacityValueObject`
```text
+ rating_value: Float (> 0.0)
+ rating_unit: String ("kW", "MW", "kWp", "MWp", "kWh", "MWh", "kVA")
+ power_factor: Optional[Float] (0.0 to 1.0)
+ continuous_rating: Optional[Float]
+ peak_rating: Optional[Float]
```

### `ManufacturerValueObject`
```text
+ make: String (e.g. "SMA", "Vestas", "Tesla", "Sungrow")
+ model_name: String
+ serial_number: Optional[String]
+ hardware_version: Optional[String]
+ firmware_version: Optional[String]
+ country_of_origin: Optional[String]
```

### `WarrantyValueObject`
```text
+ provider_name: String
+ start_date: Date
+ expiration_date: Date
+ coverage_type: String ("FULL_PARTS_LABOR", "PERFORMANCE_GUARANTEE", "LIMITED_PARTS")
+ guaranteed_performance_pct: Optional[Float] (e.g. 80.0% at Year 25)
+ max_operating_cycles: Optional[Integer] (For BESS)
```

---

## 4. Hierarchy Entities

### `Organisation` (Level 1)
- `id`: UUID (Primary Key)
- `name`: String (e.g., "Pacific Renewable Energy Inc")
- `code`: String (Unique, e.g., "ORG-PREI")
- `tenant_id`: UUID (Multi-tenant isolation key)
- `created_at`, `updated_at`: Timestamp

### `Portfolio` (Level 2)
- `id`: UUID
- `organisation_id`: UUID (Foreign Key to `Organisation`)
- `name`: String (e.g., "California Desert Solar Portfolio")
- `code`: String
- `region`: String
- `target_capacity`: `CapacityValueObject`

### `Project` (Level 3)
- `id`: UUID
- `portfolio_id`: UUID (Foreign Key to `Portfolio`)
- `name`: String (e.g., "Antelope Valley Solar Phase 1")
- `code`: String
- `offtaker_name`: String (e.g., "Southern California Edison")
- `ppa_rate_usd_per_mwh`: Float

### `Site` (Level 4)
- `id`: UUID
- `project_id`: UUID (Foreign Key to `Project`)
- `name`: String (e.g., "Site Mojave Alpha")
- `code`: String
- `location`: `LocationValueObject`
- `grid_interconnection_voltage_kv`: Float

### `EnergySystem` (Level 5)
- `id`: UUID
- `site_id`: UUID (Foreign Key to `Site`)
- `name`: String (e.g., "Mojave PV Generation Unit #1")
- `code`: String
- `technology_type`: `TechnologyType` (`SOLAR_PV`, `WIND`, `BESS`, `HYBRID`)
- `capacity`: `CapacityValueObject`
- `lifecycle_state`: `LifecycleState`
- `technology_metadata`: Dictionary (Validated against adapter schema)

### `Asset` (Level 6)
- `id`: UUID
- `energy_system_id`: UUID (Foreign Key to `EnergySystem`)
- `parent_asset_id`: Optional[UUID] (For nested asset topologies, e.g. Inverter -> String Combiner)
- `name`: String (e.g., "Inverter Station #03")
- `code`: String (e.g., "INV-03")
- `asset_type`: String (`PV_INVERTER`, `WIND_TURBINE`, `BESS_CONTAINER`, `TRANSFORMER`)
- `lifecycle_state`: `LifecycleState`
- `manufacturer_info`: `ManufacturerValueObject`
- `capacity`: `CapacityValueObject`
- `warranty`: `WarrantyValueObject`
- `commissioning_date`: Date
- `technology_metadata`: Dictionary

### `Component` (Level 7)
- `id`: UUID
- `asset_id`: UUID (Foreign Key to `Asset`)
- `parent_component_id`: Optional[UUID] (For nested sub-assemblies)
- `name`: String (e.g., "IGBT Power Module A")
- `code`: String (e.g., "COMP-IGBT-A")
- `component_type`: String (`POWER_ELECTRONICS`, `GEARBOX_BEARING`, `BATTERY_CELL_RACK`, `PITCH_ACTUATOR`)
- `lifecycle_state`: `LifecycleState`
- `manufacturer_info`: `ManufacturerValueObject`

### `Sensor` (Level 8)
- `id`: UUID
- `asset_id`: Optional[UUID] (Foreign Key to `Asset`)
- `component_id`: Optional[UUID] (Foreign Key to `Component`)
- `name`: String (e.g., "Inverter Heat Sink Temp Sensor")
- `code`: String (e.g., "SENS-HS-TEMP-01")
- `sensor_type`: `SensorType`
- `unit_of_measure`: String ("degC", "V", "A", "kW", "W/m2", "rpm")
- `sampling_interval_sec`: Integer (Default: 1 to 900 seconds)
- `modbus_address`: Optional[String]
- `opc_node_id`: Optional[String]
- `mqtt_topic`: Optional[String]

---

## 5. Domain Invariants & Validation Constraints

1. **Sensor Parent Mutual Exclusivity Constraint**: A `Sensor` entity MUST have exactly one parent reference set: either `asset_id` OR `component_id` (never both null, never both populated).
2. **Code Uniqueness Invariant**: `code` attributes must be unique within their respective parent scope (e.g. sensor codes unique within an asset; asset codes unique within an energy system).
3. **Valid Capacity Units Constraint**: Solar PV capacities MUST be specified in `kWp` or `MWp` for DC ratings and `kW` or `MW` for AC ratings; BESS capacities MUST be specified in `kWh` or `MWh`.
