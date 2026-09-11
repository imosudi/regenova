# REAMP Expected-Performance Models and Physics Formulations

## 1. Overview & Principles

The REAMP expected-performance model formulates the theoretical electrical output of a renewable generation or storage unit as a function of its physical design parameters, prevailing environmental conditions, and current operational state:

$$P_{expected} = f(\mathbf{\Theta}_{asset}, \mathbf{E}_{env}, S_{op})$$

Where:
- $\mathbf{\Theta}_{asset}$: Static and semi-static asset characteristics (nameplate capacity, temperature coefficients, tilt/azimuth, efficiency curves, degradation factors).
- $\mathbf{E}_{env}$: High-frequency environmental telemetry (plane-of-array irradiance, ambient temperature, wind speed, wind direction, barometric pressure, relative humidity).
- $S_{op}$: Operational state discrete identifier (`RUNNING`, `CURTAILED`, `FAULT_TRIPPED`, `MAINTENANCE`, `OFFLINE`, `STANDBY`).

---

## 2. Solar Photovoltaic (PV) Performance Model

### 2.1 Environmental Inputs & Preprocessing

The primary environmental driver for Solar PV is Plane-of-Array ($POA$) irradiance $G_{poa}$ ($\text{W/m}^2$), measured via calibrated thermopile pyranometers or reference solar cells conforming to ISO 9060 Class A:

- **Minimum Operational Irradiance**: Irradiance values below $G_{threshold} = 20\ \text{W/m}^2$ represent twilight/night conditions where inverter standby self-consumption dominates; $P_{expected}$ is constrained to $0.0\ \text{kW}$.
- **Irradiance Ratio**:
  $$R_G = \frac{G_{poa}}{G_{STC}}$$
  where $G_{STC} = 1000\ \text{W/m}^2$ is the Standard Test Condition reference irradiance.

### 2.2 Module Cell Temperature Modeling

In operational power plants, direct back-of-module temperature sensors may be sparse, noisy, or failing. REAMP provides a dual-mode cell temperature calculation:

1. **Direct Measurement Mode**:
   When back-of-module thermocouple $T_{bom}$ is available and flagged `VALID`:
   $$T_{cell} = T_{bom} + \Delta T_{module}$$
   where $\Delta T_{module} \approx \frac{G_{poa}}{1000} \cdot 3.0^\circ\text{C}$ accounts for the thermal gradient between the rear sheet and the silicon junction.

2. **NMOT / Evans-PVsyst Empirical Estimation Mode**:
   When only ambient temperature $T_{amb}$ is available:
   $$T_{cell} = T_{amb} + \left(\frac{NMOT - 20^\circ\text{C}}{800\ \text{W/m}^2}\right) \cdot G_{poa} \cdot \left(1 - \frac{\eta_{STC}}{0.9}\right)$$
   For crystalline silicon under typical conditions, this simplifies to the standard Sandia/King formulation:
   $$T_{cell} = T_{amb} + G_{poa} \cdot \left(\frac{NMOT - 20^\circ\text{C}}{800}\right)$$
   Where $NMOT$ is typically $45.0^\circ\text{C} \pm 2^\circ\text{C}$.

### 2.3 Thermal Derating Function

Silicon photovoltaic cell efficiency declines with increasing temperature due to narrowing bandgap and increased intrinsic carrier concentration:
$$f_{temp}(T_{cell}) = 1.0 + \gamma_{Pmp} \cdot (T_{cell} - 25.0^\circ\text{C})$$
Where:
- $\gamma_{Pmp}$: Temperature coefficient of maximum power (typical values: $-0.0035\ /^\circ\text{C}$ for monocrystalline PERC; $-0.0026\ /^\circ\text{C}$ for heterojunction / HJT).
- At $T_{cell} = 65^\circ\text{C}$ and $\gamma_{Pmp} = -0.0035$, $f_{temp} = 1 - 0.14 = 0.86$ (a $14\%$ thermal loss).

### 2.4 DC Array Power Formulation

$$P_{dc,expected} = P_{dc,rated} \cdot \left(\frac{G_{poa}}{1000}\right) \cdot f_{temp}(T_{cell}) \cdot \eta_{soiling} \cdot \eta_{mismatch} \cdot \eta_{dc\_wiring}$$

Where:
- $P_{dc,rated}$: Total installed DC peak capacity (kWp).
- $\eta_{soiling}$: Baseline clean module transmission (typically $0.98$ for clean arrays).
- $\eta_{mismatch}$: String mismatch and manufacturing tolerance factor (typically $0.985$).
- $\eta_{dc\_wiring}$: DC ohmic cabling efficiency (typically $0.985 - 0.99$).

### 2.5 Inverter Conversion and Power Limiting

In modern utility-scale PV designs, the Inverter Loading Ratio ($ILR = P_{dc,rated} / P_{ac,rated}$) frequently ranges from $1.20$ to $1.40$ to maximize energy yield during morning and evening hours.

1. **Inverter Conversion Efficiency**:
   Empirically represented as a weighted curve (California Energy Commission / Sandia inverter model) or nominal full-load efficiency:
   $$\eta_{inv}(P_{dc}) = \eta_{nom} \cdot \left(1 - e^{-k \cdot P_{dc} / P_{ac,rated}}\right)$$
   For high-power central and string inverters operating above $20\%$ load, $\eta_{inv} \approx \eta_{nom} \approx 0.985$.

2. **Uncapped AC Power**:
   $$P_{ac,uncapped} = P_{dc,expected} \cdot \eta_{inv}$$

3. **Inverter AC Power Saturation (Clipping)**:
   The inverter's IGBT bridge and magnetic components are thermal and current limited to $P_{ac,rated}$:
   $$P_{ac,expected} = \min\left(P_{ac,rated}, P_{ac,uncapped}\right)$$

---

## 3. Wind Turbine Performance Model (IEC 61400-12-1)

### 3.1 Air Density Normalization

Wind turbine aerodynamic thrust and power generation are directly proportional to ambient air density $\rho$. Telemetry wind speed $v_{meas}$ is normalized to standard air density $\rho_0 = 1.225\ \text{kg/m}^3$:
$$\rho = \frac{P_{baro} \cdot 100}{R_{spec} \cdot (T_{amb} + 273.15)}$$
where $R_{spec} = 287.058\ \text{J/(kg}\cdot\text{K)}$.
$$v_{norm} = v_{meas} \cdot \left(\frac{\rho}{\rho_0}\right)^{1/3}$$

### 3.2 Four-Region Aerodynamic Power Curve

Expected electrical output is evaluated across four continuous operating regimes:

```
Power (kW)
  ^
  |                           Region III (Rated Output)
  |                       +-------------------------------+
  |                      /                                |
  |                     /                                 |
  |                    /                                  |
  |                   / Region II                         |
  |                  / (Aerodynamic Cubic Tracking)       |
  |                 /                                     |
  |                /                                      |
  |               /                                       |
  |              /                                        |
  |  Region I   /                                         | Region IV
  |  (Cut-in)  /                                          | (Cut-out Trip)
--+-----------+-------------------------------------------+-----------------> Wind Speed (m/s)
  0         v_in                                        v_rated   v_out
```

1. **Region I ($0 \le v_{norm} < v_{cut\_in}$)**:
   Below cut-in speed (typically $3.0\ \text{m/s}$), aerodynamic torque is insufficient to overcome bearing and generator drag:
   $$P_{expected} = 0.0\ \text{kW}$$

2. **Region II ($v_{cut\_in} \le v_{norm} < v_{rated}$)**:
   Turbine operates at optimal tip-speed ratio ($\lambda_{opt}$) tracking maximum aerodynamic power coefficient ($C_{p,max} \le 16/27$):
   $$P_{aero}(v_{norm}) = 0.5 \cdot \rho_0 \cdot \pi R^2 \cdot C_{p,max} \cdot v_{norm}^3 \cdot \eta_{drivetrain}$$
   In standard engineering implementations, this is parameterized via the manufacturer's certified IEC 61400-12-1 tabular power curve or smooth cubic interpolation:
   $$P_{expected}(v_{norm}) = P_{rated} \cdot \left(\frac{v_{norm}^3 - v_{cut\_in}^3}{v_{rated}^3 - v_{cut\_in}^3}\right)$$

3. **Region III ($v_{rated} \le v_{norm} \le v_{cut\_out}$)**:
   Active blade pitch regulation maintains mechanical load at nameplate limit:
   $$P_{expected} = P_{rated}$$

4. **Region IV ($v_{norm} > v_{cut\_out}$)**:
   Storm safety aerodynamic feathering and mechanical braking (typically $v_{cut\_out} \ge 25.0\ \text{m/s}$):
   $$P_{expected} = 0.0\ \text{kW}$$

---

## 4. Battery Energy Storage System (BESS) Performance Model

### 4.1 Dispatch Setpoint Tracking

Unlike passive generation assets (Solar/Wind), BESS is an actively dispatched asset responding to energy market signals, frequency regulation, or peak shaving setpoints $P_{setpoint}$ (kW):
- $P_{setpoint} > 0$: Discharging to grid.
- $P_{setpoint} < 0$: Charging from grid.
- $P_{setpoint} = 0$: Idle / Standby.

### 4.2 State of Charge (SoC) and Inverter Limits

Expected discharge power is constrained by available stored energy and battery management system (BMS) limits:
$$P_{expected,discharge} = \min\left(P_{setpoint}, P_{rated,discharge}\right) \cdot \mathbb{I}(SoC > SoC_{min})$$
$$P_{expected,charge} = \max\left(P_{setpoint}, -P_{rated,charge}\right) \cdot \mathbb{I}(SoC < SoC_{max})$$

### 4.3 Round-Trip Efficiency (RTE) Verification

Cycle efficiency over complete charge-discharge cycles:
$$RTE_{measured} = \frac{\sum E_{discharge}}{\sum |E_{charge}|}$$
Benchmark expectation:
$$RTE_{expected} = RTE_{rated} \cdot [1 - \alpha_{fade} \cdot (\text{Cycles} / \text{RatedCycles})] \cdot f_{temp}(T_{cell})$$

---

## 5. Performance Gap & Weather Adjustment Formulation

### 5.1 Deterministic Performance Gap

The core metric quantifying deviation from physical expectation:
$$\Delta P = P_{expected} - P_{actual}$$

- When $\Delta P \le 0$: Asset is meeting or exceeding physical expectation (surplus generation).
- When $\Delta P > 0$: Asset is underperforming relative to prevailing environmental conditions.

### 5.2 IEC 61724-1 Standard Performance Ratios

1. **Raw Performance Ratio ($PR_{raw}$)**:
   $$PR_{raw} = \frac{P_{actual}}{P_{dc,rated} \cdot (G_{poa} / 1000)}$$
2. **Weather-Adjusted Temperature-Compensated Performance Ratio ($PR_{STC}$)**:
   $$PR_{STC} = \frac{P_{actual}}{P_{dc,rated} \cdot (G_{poa} / 1000) \cdot [1 + \gamma_{Pmp} \cdot (T_{cell} - 25.0)]}$$

By comparing $PR_{raw}$ against $PR_{STC}$, the asset intelligence engine isolates pure thermal losses from irreversible equipment degradation.
