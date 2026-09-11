# REAMP - Framework Limitations and Assumptions

In compliance with **Rule 3 (Evidence over assumptions)** and **Rule 9 (No fake completion)**, this document records the known limitations, operational assumptions, and engineering trade-offs inherent in the current release of the REAMP framework.

---

## 1. Experimental and Dataset Limitations

### 1.1 Synthetic Generation vs. Live Utility Interconnection
- **Current State**: The framework has been validated against extensive unit, integration, stress, and chaos suites utilizing physically grounded synthetic data generators. These generators model IEC 61724-1 irradiance-temperature physics, IEC 61400-12-1 wind power curves, and empirical Arrhenius thermal degradation.
- **Limitation**: While validated against Sandia National Laboratories and NREL reference models, the system has not yet undergone a multi-year commercial field deployment on live utility-scale transmission substations with real-world sensor drift, foul weather icing, and electromagnetic interference (EMI).

### 1.2 Fixed Single-Point Ambient Measurements
- **Assumption**: Reference pipelines assume that ambient temperature and irradiance measured at the plant weather station are representative across the entire array.
- **Limitation**: On multi-gigawatt facilities spanning hundreds of hectares, micro-climates, localized cloud shadows, and complex terrain induce spatial variations not fully captured by single-point meteorological instrumentation.

---

## 2. Algorithmic and Modeling Limitations

### 2.1 Degradation Trajectory Assumptions
- **Assumption**: The predictive maintenance engine models component wear using linear ($y = at + b$) and exponential ($y = a e^{bt}$) degradation curves.
- **Limitation**: Certain mechanical and chemical failure modes-such as abrupt fatigue spalling in wind turbine gearbox bearings or sudden lithium dendrite short-circuits in BESS-exhibit non-monotonic, sudden-onset dynamics that defy simple curve-fitting and require particle filter state estimation or acoustic emission sensors.

### 2.2 Unsupervised Isolation Forest Tuning
- **Assumption**: Unsupervised Isolation Forest operates with default contamination factor $\nu = 0.05$ and sub-sampling size $\psi = 64$.
- **Limitation**: While highly effective at flagging anomalies without labeled training datasets, shifts in asset operational regimens (e.g., changing from Baseload to Frequency Regulation mode in BESS) can temporarily elevate outlier scores until baseline recalibration occurs.

---

## 3. Computational and Deployment Trade-offs

### 3.1 Single-Node Testing vs. Distributed Orchestration
- **Current State**: The full framework test suite executes cleanly on single developer workstations and standard CI/CD runners using in-memory databases (`:memory:`) and local multi-processing.
- **Limitation**: Deployments scaling beyond 10,000 active assets streaming at $1\,\text{Hz}$ will require transitioning the orchestration layer to distributed worker clusters (e.g., Ray, Celery, Kubernetes) and dedicated TimescaleDB clusters to maintain sub-second latency.

### 3.2 Protocol Adapter Testing without Physical Hardware
- **Current State**: Protocol adapters (`Modbus`, `OPC UA`, `MQTT`, `REST`) are verified using binary register decoders and simulated socket streams.
- **Limitation**: Physical serial bus characteristics-such as RS-485 baud rate mismatch, token ring collisions, ground loops, and noisy analog-to-digital converters-were not physically replicated in software testing.
