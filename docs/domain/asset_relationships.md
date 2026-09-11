# REAMP - Asset Relationships and Topology Specification

**Document Identifier**: `REAMP-DOM-03`  
**Phase**: Phase 2 - Asset Ontology and Domain Model  
**Status**: Approved / Quality Gate Passed  
**Last Updated**: 2026-09-11  

---

## 1. Relationship Classification Framework

In REAMP, assets do not exist in isolation. They form complex structural, electrical, mechanical, logical, telemetry, and operational graph topologies.

REAMP categorizes asset relationships into 6 distinct edge types:

```text
 1. Structural / Hierarchy Edges     (PARENT_OF, CHILD_OF, CONTAINS)
 2. Electrical Topology Edges        (FEEDS_POWER_TO, CONNECTED_TO_BUS)
 3. Mechanical Topology Edges        (MECHANICALLY_COUPLED_TO, MOUNTED_ON)
 4. Telemetry & Sensing Edges        (MONITORED_BY_SENSOR, PROVIDES_METRIC_TO)
 5. Control & Protection Edges       (CONTROLLED_BY_PLC, PROTECTED_BY_BREAKER)
 6. Maintenance & CMMS Edges         (ASSOCIATED_WITH_WORK_ORDER, SPARE_PART_FOR)
```

---

## 2. Universal Relationship Edge Specification

Every relationship between two entities is modeled as a directed edge with metadata attributes:

```text
┌─────────────────────────────────────────────────────────────────┐
│                    DomainRelationshipEdge                       │
├─────────────────────────────────────────────────────────────────┤
│ + relationship_id: UUID                                         │
│ + source_entity_id: UUID (e.g. Inverter ID)                     │
│ + target_entity_id: UUID (e.g. Substation Bus ID)               │
│ + relationship_type: RelationshipType Enum                      │
│ + directional: Boolean (Default: True)                          │
│ + weight_or_impedance: Optional[Float] (For electrical cables) │
│ + created_at: ISO8601Timestamp                                  │
│ + metadata: Dict[String, Any]                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Technology-Specific Relationship Topologies

### 3.1 Solar Photovoltaic (PV) Topology Graph

```text
Site
 └── EnergySystem (PV Plant)
      └── Asset (Substation Transformer)
           └── Asset (Central Inverter #01) ◄─── FEEDS_POWER_TO
                ├── Asset (String Combiner Box A) ◄─── FEEDS_POWER_TO
                │    ├── Component (PV String 01) ◄─── FEEDS_POWER_TO
                │    │    └── Sensor (DC String Current Sensor) ◄─── MONITORED_BY
                │    └── Component (PV String 02)
                └── Component (IGBT Power Module #1)
                     └── Sensor (Heat Sink Temp Sensor) ◄─── MONITORED_BY
```

- **DC Electrical Topology**: `PV String` $\rightarrow$ `FEEDS_POWER_TO` $\rightarrow$ `Combiner Box` $\rightarrow$ `FEEDS_POWER_TO` $\rightarrow$ `Inverter DC Bus`.
- **AC Electrical Topology**: `Inverter AC Output` $\rightarrow$ `FEEDS_POWER_TO` $\rightarrow$ `Pad-mount Transformer` $\rightarrow$ `FEEDS_POWER_TO` $\rightarrow$ `Substation 34.5kV Bus`.
- **Sensing Topology**: `Pyranometer Sensor` $\rightarrow$ `PROVIDES_METRIC_TO` $\rightarrow$ `EnergySystem (PV Plant)` (Global Irradiance reference).

---

## 3.2 Wind Energy Systems Topology Graph

```text
Site
 └── EnergySystem (Wind Farm)
      └── Asset (Wind Turbine #01)
           ├── Component (Rotor Hub & Blades)
           │    └── Component (Pitch Actuator Motors)
           │         └── Sensor (Blade Pitch Angle Encoder)
           ├── Component (Gearbox 3-Stage) ◄─── MECHANICALLY_COUPLED_TO (Rotor)
           │    ├── Sensor (High Speed Shaft Vibration Sensor)
           │    └── Sensor (Gearbox Sump Oil Temp Sensor)
           ├── Component (DFIG Generator) ◄─── MECHANICALLY_COUPLED_TO (Gearbox)
           │    └── Component (Power Converter) ◄─── FEEDS_POWER_TO
           └── Sensor (Nacelle Anemometer) ◄─── MONITORED_BY
```

- **Mechanical Topology**: `Blades` $\rightarrow$ `ROTATES_LOW_SPEED_SHAFT` $\rightarrow$ `Gearbox` $\rightarrow$ `ROTATES_HIGH_SPEED_SHAFT` $\rightarrow$ `Generator`.
- **Control Topology**: `Nacelle Anemometer` $\rightarrow$ `PROVIDES_INPUT_TO` $\rightarrow$ `Pitch Controller PLC` $\rightarrow$ `CONTROLS` $\rightarrow$ `Pitch Actuator Motor`.

---

## 3.3 Battery Energy Storage System (BESS) Topology Graph

```text
Site
 └── EnergySystem (BESS Plant)
      └── Asset (Container BESS #01)
           ├── Asset (PCS Inverter) ◄─── FEEDS_POWER_TO
           └── Asset (Battery Rack #01)
                ├── Component (Battery Pack / Module 01)
                │    ├── Component (Cell Array #01-16)
                │    │    └── Sensor (Cell Voltage & Temp Transducer)
                │    └── Component (BMS Slave Unit)
                └── Component (BMS Master Controller) ◄─── CONTROLS
```

- **DC Power Topology**: `Battery Cell Array` $\rightarrow$ `FEEDS_POWER_TO` $\rightarrow$ `Rack DC Bus` $\rightarrow$ `FEEDS_POWER_TO` $\rightarrow$ `PCS Inverter DC Input`.
- **BMS Control Topology**: `BMS Master Controller` $\rightarrow$ `MONITORS_HEALTH` $\rightarrow$ `Rack Contactors` $\rightarrow$ `PROTECTS_BY_TRIPPING`.

---

## 4. Graph Query & Traversal Requirements

1. **Upstream Financial Loss Attribution Traversal**: When a Level 7 `Component` (e.g. IGBT Power Module) fails, the domain model MUST support upward graph traversal to calculate total impacted capacity ($kW$) at the Level 5 `EnergySystem` and Level 3 `Project` levels.
2. **Downstream Anomaly Impact Propagation**: When a Level 6 `Asset` (e.g. Transformer) trips, downstream graph queries MUST identify all child and dependent assets placed into `OFFLINE` or `DERATED` states.
3. **Graph Storage Integrity**: Relationship edges must enforce referential integrity; deleting an entity automatically soft-deletes or archives its connected relationship edges.
