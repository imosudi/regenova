# REAMP - Asset Ontology Specification

**Document Identifier**: `REAMP-DOC-02`  
**Phase**: Phase 2 - Asset Ontology and Domain Model  
**Status**: Approved / Quality Gate Passed  
**Last Updated**: 2026-09-11  

---

## 1. Executive Summary & Semantic Principles

The **Renewable Energy Asset Intelligence and Management Framework (REAMP)** Asset Ontology provides a formal, technology-agnostic semantic model for representing heterogeneous renewable energy infrastructure and its operational context.

Traditional asset management systems embed assumptions specific to a single technology (such as Solar PV string layouts or Wind turbine gearboxes) into their core database schemas. REAMP avoids this anti-pattern by establishing a strict separation between:

1. **Canonical Asset Hierarchy**: Universal structural organization (`Organisation → Portfolio → Project → Site → Energy System → Asset → Component → Sensor`).
2. **Core Domain Entities**: Universal domain concepts (e.g., identity, location, nameplate capacity, operational lifecycle, ownership, maintenance history).
3. **Technology Adapter Schemas**: Technology-specific physics attributes, parameter sets, and operational metrics attached via strongly-typed, validated metadata interfaces.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                     REAMP Core Asset Ontology                           │
│  (Organisation → Portfolio → Project → Site → EnergySystem → Asset...)   │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▲
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│ Solar PV      │           │ Wind Energy   │           │ BESS          │
│ Tech Adapter  │           │ Tech Adapter  │           │ Tech Adapter  │
├───────────────┤           ├───────────────┤           ├───────────────┤
│ • Strings     │           │ • Nacelle     │           │ • Racks/Cells │
│ • Inverters   │           │ • Gearbox     │           │ • BMS/PCS     │
│ • Irradiance  │           │ • Power Curve │           │ • SoC / SoH   │
└───────────────┘           └───────────────┘           └───────────────┘
```

---

## 2. Canonical 8-Level Hierarchy Taxonomy

REAMP mandates an 8-level structural hierarchy across all domain models, APIs, and storage layers:

| Hierarchy Level | Entity Class | Scope & Semantic Definition | Technology-Agnostic Example |
| :--- | :--- | :--- | :--- |
| **Level 1** | `Organisation` | Top-level enterprise or corporate entity owning or managing renewable portfolios. | *Acme Clean Energy Corp* |
| **Level 2** | `Portfolio` | Regional or strategic grouping of renewable energy projects. | *EMEA Utility Scale Portfolio* |
| **Level 3** | `Project` | Legal, financial, or grid-interconnection project entity. | *SolWest 100MW Expansion* |
| **Level 4** | `Site` | Physical geographic land area or offshore precinct containing generation/storage infrastructure. | *Mojave Solar & Storage Park* |
| **Level 5** | `EnergySystem` | Self-contained, technology-specific generation or storage plant within a site. | *Site-Alpha 50MW PV Plant #1* |
| **Level 6** | `Asset` | Major functional electro-mechanical or power conversion unit. | *Central Inverter #04* / *Turbine #12* |
| **Level 7** | `Component` | Sub-assembly, module, or physical component within a major asset. | *Inverter Power Block B* / *Gearbox* |
| **Level 8** | `Sensor` | Individual telemetry transducer, meter, or physical sensor node. | *Heat Sink Temp Sensor #2* |

---

## 3. Technology Adapter Architecture

Core domain entities maintain **zero hardcoded dependencies** on specific generation technologies. Technology-specific parameters are attached via strongly-typed technology metadata schemas validated at runtime.

### 3.1 Solar Photovoltaic (PV) Adapter Schema
Attached to `EnergySystem` (`PV_PLANT`) and `Asset` (`PV_INVERTER`, `PV_COMBINER`, `PV_TRACKER`).
- **PV Plant Metadata**: Total Installed DC Power ($kWp$), Total AC Capacity ($kW$), DC/AC Ratio, Tracker Type (`FIXED`, `SINGLE_AXIS_HSAT`, `DUAL_AXIS`).
- **PV Inverter Metadata**: Rated AC Power ($kW$), Max DC Voltage ($V$), Number of MPPT Inputs, Efficiency Rating ($\%_{CEC}$).
- **PV String/Module Metadata**: Module Technology (`MONO_PERC`, `TOPCON`, `HJT`, `CDTE`), $P_{mp}$, $V_{mp}$, $I_{mp}$, $V_{oc}$, $I_{sc}$, Temperature Coefficient of Power ($\gamma \%/^\circ C$).

### 3.2 Wind Energy Adapter Schema
Attached to `EnergySystem` (`WIND_FARM`) and `Asset` (`WIND_TURBINE`, `SUBSTATION_TRANSFORMER`).
- **Wind Turbine Metadata**: Hub Height ($m$), Rotor Diameter ($m$), Swept Area ($m^2$), Cut-in Wind Speed ($m/s$), Rated Wind Speed ($m/s$), Cut-out Wind Speed ($m/s$), OEM Power Curve Matrix $(v_w, P_{gen})$.
- **Drive-train Metadata**: Transmission Type (`DIRECT_DRIVE`, `GEARED_3_STAGE`), Gearbox Ratio, Generator Type (`DFIG`, `PMSG`).

### 3.3 Battery Energy Storage System (BESS) Adapter Schema
Attached to `EnergySystem` (`BESS_PLANT`) and `Asset` (`BESS_CONTAINER`, `PCS_INVERTER`, `BATTERY_RACK`).
- **BESS Plant Metadata**: Nameplate Energy Capacity ($kWh$), Continuous Power Rating ($kW$), Chemistry (`LFP`, `NMC`, `LTO`, `FLOW`), Nominal Voltage ($V$).
- **BESS Rack/Cell Metadata**: Cell Count, Max Charge $C$-rate, Max Discharge $C$-rate, Min/Max Cell Voltage Limits ($V$), Thermal Management Type (`LIQUID_COOLED`, `HVAC_AIR`).

### 3.4 Hybrid Plant Adapter Schema
Attached to `EnergySystem` (`HYBRID_PLANT`).
- **Hybrid Plant Metadata**: Combined Grid Export Capacity Limit ($kW$), Microgrid Controller ID, Operating Mode (`PARALLEL_EXPORT`, `PEAK_SHAVING`, `ISLANDED`).

---

## 4. Universal Entity Attributes & Data Types

Every entity across all 8 levels inherits common core attributes:

```text
┌─────────────────────────────────────────────────────────────────┐
│                     BaseDomainEntity                            │
├─────────────────────────────────────────────────────────────────┤
│ + id: UUID / URN (e.g. "urn:reamp:asset:inv-004")               │
│ + name: String                                                  │
│ + code: String (Human-readable unique identifier)               │
│ + entity_level: HierarchyLevel Enum                             │
│ + parent_id: Optional[UUID]                                     │
│ + lifecycle_state: LifecycleState Enum                          │
│ + location: Optional[LocationValueObject]                       │
│ + manufacturer_info: Optional[ManufacturerValueObject]          │
│ + capacity: Optional[CapacityValueObject]                       │
│ + warranty_terms: Optional[WarrantyValueObject]                 │
│ + commissioning_date: Optional[ISO8601Timestamp]                │
│ + decommissioning_date: Optional[ISO8601Timestamp]              │
│ + technology_adapter_type: TechnologyType Enum                  │
│ + technology_metadata: Dict[String, Any] (JSON Schema validated)│
│ + created_at: ISO8601Timestamp                                  │
│ + updated_at: ISO8601Timestamp                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Domain Invariants & Quality Rules

To guarantee domain integrity, the ontology enforces four strict invariants:

1. **Strict Hierarchy Tree Invariant**: No entity (except Level 1 `Organisation`) may exist without a valid `parent_id` belonging to the immediate parent hierarchy level.
2. **Sensor Attachment Boundary Invariant**: Level 8 `Sensor` entities MUST be child nodes of either Level 6 `Asset` or Level 7 `Component`.
3. **Technology Adapter Consistency Invariant**: All child entities within an `EnergySystem` must possess technology metadata compatible with the parent `EnergySystem`'s `technology_adapter_type`.
4. **Lifecycle State Transition Invariant**: An entity cannot transition directly from `PLANNED` to `DECOMMISSIONED` without passing through `COMMISSIONED` or `UNDER_CONSTRUCTION`.
