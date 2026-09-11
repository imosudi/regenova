# REAMP — Architecture Decision Records (ADRs)

**Document Identifier**: `REAMP-ARC-04`  
**Phase**: Phase 3 — Reference Architecture  
**Status**: Approved / Quality Gate Passed  
**Last Updated**: 2026-09-11  

---

## ADR-001: Core Backend Framework & Ingestion Protocol Choice

- **Status**: Approved
- **Context**: REAMP requires a high-performance, strongly-typed backend framework capable of processing asynchronous telemetry streams, running scientific Python libraries (NumPy, SciPy, PyTorch, SHAP), and serving OpenAPI endpoints.
- **Alternatives Evaluated**:
  1. *Node.js / Express*: High IO throughput, but lacks native scientific Python/ML ecosystem integration.
  2. *Go (Golang)*: High concurrency, but requires separate IPC wrappers for Python analytical ML libraries.
  3. *Python 3.11 + FastAPI (Selected)*: Native integration with scientific Python/ML libraries, native async/await IO, automatic OpenAPI documentation, high developer productivity.
- **Decision**: Adopt **Python 3.11 + FastAPI** for core cloud services and API Gateway.

---

## ADR-002: Relational Domain Database Engine

- **Status**: Approved
- **Context**: REAMP requires a rock-solid, ACID-compliant relational database for managing multi-tenant organisations, asset hierarchies, metadata, user roles, CMMS work orders, and audit logs.
- **Alternatives Evaluated**:
  1. *MySQL 8.0*: Widely supported, but weaker JSON schema validation and GIS spatial indexing compared to PostgreSQL.
  2. *PostgreSQL 16 (Selected)*: Superior JSONB metadata indexing, PostGIS support for asset geofencing, Row Level Security (RLS) for multi-tenancy, and native TimescaleDB extension compatibility.
- **Decision**: Adopt **PostgreSQL 16** as the canonical relational domain database.

---

## ADR-003: Time-Series Database Engine

- **Status**: Approved
- **Context**: REAMP must ingest, store, and query millions of high-frequency sensor time-series events per second with automatic temporal hypertable partitioning and lossy compression.
- **Alternatives Evaluated**:
  1. *InfluxDB 2.x*: Purpose-built for time-series, but requires learning Flux query language and introduces a separate database engine to operationalize alongside PostgreSQL.
  2. *Cassandra*: Highly scalable, but high operational overhead for medium-scale deployments.
  3. *TimescaleDB 2.12 (Selected)*: PostgreSQL extension delivering time-series hypertable auto-partitioning, $90\%$ columnar compression, full SQL support, and seamless JOIN capabilities with PostgreSQL domain tables.
- **Decision**: Adopt **TimescaleDB 2.12** as the unified time-series database.

---

## ADR-004: In-Memory Caching & Real-Time Event Broker

- **Status**: Approved
- **Context**: REAMP requires low-latency real-time caching of asset states and pub/sub message broadcasting for UI WebSockets.
- **Alternatives Evaluated**:
  1. *Memcached*: Simple key-value store, but lacks pub/sub primitives and data structure support.
  2. *Apache Kafka*: Enterprise-grade streaming, but introduces significant operational complexity (Zookeeper/KRaft cluster) premature for initial phases.
  3. *Redis 7.2 / Valkey (Selected)*: Sub-millisecond key-value caching, native pub/sub channels, Redis Streams, and minimal resource footprint.
- **Decision**: Adopt **Redis 7.2** for in-memory state caching and internal event pub/sub.

---

## ADR-005: Mandatory Frontend UI Framework

- **Status**: Approved
- **Context**: `AGENTS.md` Rule 9 explicitly mandates **Bootstrap 5.3.x** in the default **LIGHT** theme to ensure a clean, accessible, non-dark SCADA presentation.
- **Alternatives Evaluated**:
  1. *Tailwind CSS*: Explicitly prohibited by project operating rules unless requested.
  2. *Material UI (React)*: Complex component library with heavy JS bundle overhead.
  3. *Bootstrap 5.3.x + Vanilla JS (Selected)*: Standard responsive grid, lightweight utilities, clean light theme, accessible components, zero framework lock-in.
- **Decision**: Adopt **Bootstrap 5.3.x** as the exclusive frontend UI framework.

---

## ADR-006: Edge Local Store-and-Forward Engine

- **Status**: Approved
- **Context**: Edge gateways must locally buffer telemetry during cellular or WAN outages for up to 72 hours on memory-constrained hardware ($\le 256\text{ MB RAM}$).
- **Alternatives Evaluated**:
  1. *Embedded RocksDB*: Fast, but complex binary dependencies across ARM64/x86 architectures.
  2. *SQLite 3 (Selected)*: Zero-configuration, battle-tested, embedded ACID database with native transactional logging and lightweight cross-platform binaries.
- **Decision**: Adopt **SQLite 3** as the edge store-and-forward buffer engine.

---

## ADR-007: Authentication, Identity Provider & Edge Device PKI

- **Status**: Approved
- **Context**: REAMP requires a secure, unified authentication strategy covering both human users across multi-tenant enterprise accounts and distributed edge IoT/IPC devices over untrusted WAN networks.
- **Alternatives Evaluated**:
  1. *Basic Auth / Static API Keys*: Simple, but vulnerable to replay attacks, lacks tenant context, and fails compliance auditing.
  2. *Custom Symmetric JWT Service*: Low operational footprint, but symmetric keys shared between services risk wide compromise; key rotation requires synchronized restarts.
  3. *OAuth2 / OIDC with Asymmetric JWT (RS256) + Dedicated Edge PKI (Selected)*: Industry standard for user and service authentication. Cloud API Gateway terminates OAuth2 Bearer tokens signed via RS256 with JWKS endpoint verification. Edge gateways authenticate via mutual TLS 1.3 (mTLS) using X.509 client certificates issued by an internal REAMP Device Certificate Authority (CA) with offline-tolerant CRL caching for intermittent field connectivity.
- **Decision**: Adopt **OAuth2 / OIDC with RS256 JWT** for user/service APIs and **X.509 mTLS PKI** for edge device identity.

---

## ADR-008: Observability, Distributed Tracing & Metrics Stack

- **Status**: Approved
- **Context**: In compliance with `AGENTS.md` Rule 5 ("observable") and `NFR-OBS-001`/`NFR-OBS-002`, the framework must capture end-to-end distributed traces across edge agents and cloud microservices, collect real-time system metrics, and aggregate structured JSON logs.
- **Alternatives Evaluated**:
  1. *Proprietary SaaS (Datadog / New Relic)*: High feature richness, but violates technology neutrality, creates vendor lock-in, and introduces high variable cloud costs.
  2. *Custom Ad-Hoc Logging & StatsD*: Minimal dependencies, but lacks standardized trace context propagation and modern query interfaces.
  3. *OpenTelemetry + Prometheus + Grafana + Loki (Selected)*: Open-source, vendor-neutral standard (CNCF graduated). OpenTelemetry SDK automatically propagates W3C `traceparent` headers (`trace_id`, `span_id`, `tenant_id`, `asset_id`) from Edge Agents through to Cloud Ingestion and Analytics. Prometheus scrapes `/metrics` endpoints, Loki ingests structured JSON logs, and Grafana provides the unified operational monitoring dashboards.
- **Decision**: Adopt **OpenTelemetry (OTel) + Prometheus + Grafana** as the canonical observability architecture.

---

## ADR-009: Stream & Event Processing Engine

- **Status**: Approved
- **Context**: The framework requires an asynchronous event pipeline to decouple high-frequency telemetry ingestion from downstream analytical processing (Data Quality verification, Asset Health calculations, Anomaly detection, and Alert dispatch).
- **Alternatives Evaluated**:
  1. *Apache Kafka / Apache Flink*: Extreme throughput, but introduces heavy operational dependencies (Zookeeper / KRaft clusters, JVM memory footprint) that represent premature complexity for modular deployments.
  2. *RabbitMQ*: Robust AMQP broker, but message retention after consumption is limited and lacks native time-series sliding window stream semantics.
  3. *Redis 7.2 Streams & Consumer Groups (Selected)*: Native append-only log data structure built into Redis. Supports persistent consumer groups (`XADD`, `XREADGROUP`, `XACK`), millisecond latency, replayability for backfill processing, and zero additional infrastructure overhead beyond the existing Redis instance.
- **Decision**: Adopt **Redis 7.2 Streams** as the core asynchronous stream and event processing engine.

---

## ADR-010: Container Orchestration & Deployment Stack

- **Status**: Approved
- **Context**: In compliance with `NFR-PRT-001` and `NFR-PRT-002`, REAMP must operate seamlessly across resource-constrained Edge industrial PCs ($\le 256\text{ MB RAM}$) and highly scalable Cloud clusters.
- **Alternatives Evaluated**:
  1. *HashiCorp Nomad*: Elegant and lightweight, but lacks the vast ecosystem, Helm packaging standards, and managed cloud offerings of Kubernetes.
  2. *Full Kubernetes (k8s) Everywhere*: Heavy control plane requiring $> 2\text{ GB RAM}$, unsuitable for low-power edge IPCs and substations.
  3. *Tiered Deployment: K3s for Edge, Managed K8s (EKS/GKE/AKS) for Cloud, Docker Compose for Local Dev (Selected)*: K3s provides a fully CNCF-certified Kubernetes distribution packaged as a single $< 100\text{ MB}$ binary with memory footprint $< 256\text{ MB RAM}$, ideal for field IPCs. Cloud production utilizes managed Kubernetes clusters with Horizontal Pod Autoscalers (HPA). Docker Compose provides instant developer reproducibility.
- **Decision**: Adopt **K3s for Edge deployments, Managed Kubernetes for Cloud platforms, and Docker Compose for local development**.

