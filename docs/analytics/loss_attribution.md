# REAMP Performance Loss Attribution and Waterfall Decomposition

## 1. Executive Summary & Objective

When an operational asset generates less power than its nameplate rating, identifying **why** the deficit occurred is paramount for commercial, technical, and contractual decision-making. 

The REAMP Loss Attribution Engine deconstructs total potential energy loss into an exhaustive, mutually exclusive **waterfall decomposition**. This enables operators, asset managers, and off-takers to distinguish:
- Natural environmental variation (irradiance deficits, low wind);
- Design constraints (inverter clipping, DC/AC oversizing);
- Grid-imposed limitations (utility curtailment, interconnection constraints);
- Equipment outages (breaker trips, inverter faults, planned maintenance);
- Controllable technical underperformance (soiling, shading, string disconnects, cell degradation).

---

## 2. Loss Attribution Waterfall Architecture

```
Nameplate Capacity Under STC (P_rated)
  |
  |-- [-] Environmental Resource Loss (G_poa < 1000 W/m² or v < v_rated)
  v
Weather-Unadjusted Potential (P_resource)
  |
  |-- [-] Temperature Derating Loss (T_cell > 25°C thermal efficiency decline)
  v
Theoretical DC Generation (P_dc,expected)
  |
  |-- [-] Inverter Clipping Loss (DC oversizing: P_dc * eta > P_ac,rated)
  v
Expected Unconstrained AC Power (P_ac,expected)
  |
  +---> [Condition: Operational State == CURTAILED]
  |       |-- [-] Grid Curtailment Loss (P_expected - P_curtailment_limit)
  |
  +---> [Condition: Operational State in (FAULT, MAINTENANCE, OFFLINE)]
  |       |-- [-] Asset Outage Loss (P_expected)
  |
  +---> [Condition: Operational State == RUNNING]
          |-- [-] Controllable Technical Underperformance Loss (P_expected - P_actual)
                  |-- Soiling & Optical Transmission Loss
                  |-- Inverter Subsystem Inefficiency
                  |-- String Disconnection & Shading
                  |-- Irreversible Cell Degradation
  v
Actual Power Delivered to Interconnection (P_actual)
```

---

## 3. Loss Taxonomy & Mathematical Definitions

### 3.1 Category 1: Environmental Resource Variation (`RESOURCE_VARIATION`)
- **Definition**: The deficit between STC nameplate capacity and what the prevailing environmental resource can physically produce.
- **Formula (Solar)**:
  $$P_{loss,resource} = P_{dc,rated} \cdot \max\left(0.0, 1.0 - \frac{G_{poa}}{1000\ \text{W/m}^2}\right)$$
- **Formula (Wind)**:
  $$P_{loss,resource} = \max\left(0.0, P_{rated} - P_{curve}(v_{norm})\right)$$
- **Classification**: Uncontrollable natural resource variation. Zero operational penalty.

### 3.2 Category 2: Thermal Derating Loss (`THERMAL_DERATE`)
- **Definition**: The generation deficit resulting from elevated module or component temperatures exceeding standard reference conditions ($25.0^\circ\text{C}$).
- **Formula (Solar)**:
  $$P_{loss,thermal} = P_{dc,rated} \cdot \left(\frac{G_{poa}}{1000}\right) \cdot \max\left(0.0, -\gamma_{Pmp} \cdot (T_{cell} - 25.0^\circ\text{C})\right)$$
- **Classification**: Environmental / physical consequence. Uncontrollable without active cooling.

### 3.3 Category 3: Inverter Clipping Loss (`INVERTER_CLIPPING`)
- **Definition**: Power lost when array DC generation exceeds the inverter's maximum continuous AC output capacity ($P_{ac,rated}$).
- **Formula**:
  $$P_{ac,uncapped} = P_{dc,expected} \cdot \eta_{inv}$$
  $$P_{loss,clipping} = \max\left(0.0, P_{ac,uncapped} - P_{ac,rated}\right)$$
- **Classification**: Engineering design tradeoff (DC oversizing to maximize levelized cost of energy). Normal in high-noon summer conditions.

### 3.4 Category 4: Grid Curtailment Loss (`CURTAILMENT`)
- **Definition**: Lost generation resulting from external transmission system operator (TSO/DSO) dispatch instructions capping active power injection at $P_{limit} < P_{expected}$.
- **Formula**:
  When $S_{op} = \text{CURTAILED}$:
  $$P_{loss,curtailment} = \max\left(0.0, P_{expected} - P_{limit}\right)$$
- **Classification**: Contractual / commercial loss. Eligible for deemed-generation reimbursement under qualifying Power Purchase Agreements.

### 3.5 Category 5: Equipment Outage & Trip Loss (`ASSET_OUTAGE`)
- **Definition**: Lost generation when an asset is unavailable due to an internal fault, protection trip, scheduled overhaul, or emergency shutdown.
- **Formula**:
  When $S_{op} \in \{\text{FAULT\_TRIPPED}, \text{MAINTENANCE}, \text{OFFLINE}\}$:
  $$P_{loss,outage} = P_{expected}$$
- **Classification**: Operational availability loss. Does not indicate physical derating of healthy components; logged directly to availability accounting (CMMS / O&M downtime metrics).

### 3.6 Category 6: Controllable Technical Underperformance (`CONTROLLABLE_UNDERPERFORMANCE`)
- **Definition**: The residual gap between expected power and actual power while the asset is commanded to be in the `RUNNING` operational state.
- **Formula**:
  When $S_{op} = \text{RUNNING}$:
  $$P_{loss,underperf} = \max\left(0.0, P_{expected} - P_{actual}\right)$$
- **Sub-Attribution Breakdown**:
  1. **Soiling Loss**: Tracked via soiling sensor stations or clean-versus-dirty reference PV modules:
     $$P_{loss,soiling} = P_{expected} \cdot (1 - \text{Soiling Ratio})$$
  2. **String Disconnection / Blown Fuse**: Discrete step drops in DC current telemetry.
  3. **Module Degradation**: Age-dependent irreversible capacity fading:
     $$P_{loss,degradation} = P_{expected} \cdot (\text{Age in Years} \times 0.005 / \text{year})$$
  4. **Unexplained Gap**: Remaining delta requiring field dispatch or drone thermal inspection.

---

## 4. Operational State Gating and Priority Rules

To ensure strict determinism, the engine evaluates operational states according to the following priority hierarchy:

```
                  [Telemetry Ingestion]
                            |
           Is irradiance / wind telemetry valid?
                /                       \
             [NO]                       [YES]
              |                           |
      Flag MISSING_DATA             Evaluate State
     Confidence <= 0.40                   |
     Suppress False Alarms                +---> Operational State == FAULT_TRIPPED
                                          |     --> Classify ASSET_OUTAGE (P_loss = P_exp)
                                          |
                                          +---> Operational State == MAINTENANCE
                                          |     --> Classify PLANNED_OUTAGE (P_loss = P_exp)
                                          |
                                          +---> Operational State == CURTAILED
                                          |     --> Classify CURTAILMENT (P_loss = P_exp - P_limit)
                                          |
                                          +---> Operational State == RUNNING
                                                --> Calculate Expected Power P_exp
                                                --> Calculate Delta P = P_exp - P_act
                                                --> If Delta P > 0: Classify UNDERPERFORMANCE
                                                --> Else: Classify NOMINAL_RUNNING
```

---

## 5. Economic Valuation of Losses

### 5.1 Interval Energy Calculation
For an evaluation time slice of duration $\Delta t$ hours (e.g. $10\ \text{minutes} = 1/6\ \text{hour}$ or $1\ \text{hour}$):
$$E_{loss,i} = P_{loss,i} \cdot \Delta t\ (\text{kWh})$$

### 5.2 Revenue Impact Modeling
Using the plant's contract PPA tariff $T_{ppa}$ (\$/kWh) and optional marginal grid penalty $T_{pen}$ (\$/kWh):
$$\text{Revenue Loss}_i = E_{loss,i} \cdot T_{ppa}$$

### 5.3 Responsibility Ledger
The financial engine tallies economic losses into three distinct ledgers:
1. **Asset Owner Balance Sheet**: Absorbs losses from preventable technical underperformance, soiling, and component trips.
2. **Off-Taker / Utility Invoicing**: Generates deemed generation claims for grid curtailment hours.
3. **Insurance / Warranty Claims**: Tracks catastrophic failures exceeding manufacturer availability guarantees.
