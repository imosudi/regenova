# REGENOVA — Production & Microservices Deployment Guide

This document defines the canonical, repeatable procedure for deploying the **REGENOVA** platform and its integrated microservices using **Docker Compose**.

---

## 1. System Requirements

- **Operating System**: Linux (Ubuntu 22.04 / 24.04 / 26.04 recommended)
- **Container Engine**: Docker Engine 24+ (`docker.io`)
- **Orchestration**: Docker Compose v2 (`docker compose`)
- **Reverse Proxy**: Apache 2.4+ (with `proxy`, `proxy_http`, `proxy_wstunnel`, `rewrite`, `ssl`)
- **Database**: PostgreSQL 16+ with TimescaleDB 2.x extension

---

## 2. Standardised Container Infrastructure (`docker/`)

All container definitions and runtime assets are organised into dedicated subdirectories under `docker/`:

```text
docker/
├── api/
│   └── Dockerfile              # Core Telemetry & Anomaly Detection API
├── backoffice/
│   └── Dockerfile              # Multi-tenant Administration Console
├── web/
│   └── Dockerfile              # Web Operations Portal
├── flowfield/
│   └── Dockerfile              # Node-RED IoT Telemetry & Event Ingestion
├── twinfield/
│   └── Dockerfile              # FastAPI Digital Twin Sub-API
├── mosquitto/
│   └── mosquitto.conf          # MQTT TCP (1883) & WebSockets (9001) Configuration
└── timescaledb/
    ├── Dockerfile              # TimescaleDB 2.x Container (pg16 base)
    └── init/
        └── 01-init.sql         # Hypertables, indices & postgres_fdw host linkage
```

---

## 3. Microservice Topology & Hybrid Persistence

| Container Name | Service Name | Dockerfile Path | Host Binding | Upstream Port | Primary Persistence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `regenova-flowfield` | `flowfield` | `docker/flowfield/Dockerfile` | `127.0.0.1:1880` | `1880` | `flowfield_data` (Volume) + TimescaleDB |
| `regenova-twinfield` | `twinfield` | `docker/twinfield/Dockerfile` | `127.0.0.1:9000` | `9000` | Redis / Host PostgreSQL |
| `regenova-api` | `regenova-api` | `docker/api/Dockerfile` | `127.0.0.1:8101` | `8001` | Host PostgreSQL + TimescaleDB |
| `regenova-backoffice` | `regenova-backoffice` | `docker/backoffice/Dockerfile` | `127.0.0.1:8102` | `8002` | Host PostgreSQL 18 (`regenova_db`) |
| `regenova-web` | `regenova-web` | `docker/web/Dockerfile` | `127.0.0.1:8100` | `8000` | Host PostgreSQL 18 (`regenova_db`) |
| `regenova-mosquitto` | `mosquitto` | `eclipse-mosquitto:2` | `0.0.0.0:1883`, `127.0.0.1:9001` | `1883`, `9001` | `mosquitto_data` (Volume) |
| `regenova-redis` | `redis` | `redis:7-alpine` | `127.0.0.1:6380` | `6379` | In-Memory / Ephemeral |
| `regenova-timescaledb` | `timescaledb` | `docker/timescaledb/Dockerfile` | `127.0.0.1:5433` | `5432` | `timescaledb_data` (Volume) + `postgres_fdw` to Host |

### Dual Database Architecture:
- **Transactional State & Metadata**: Retained on host PostgreSQL 18 (`host.docker.internal:5432`, database: `regenova_db`). Houses asset hierarchies, tenancy, configurations, health records, and user management.
- **Time-Series Telemetry**: Managed by containerized TimescaleDB (`timescaledb:5432` on `regenova-net`, host: `127.0.0.1:5433`, database: `regenova_timeseries_db`). Stores chunked high-velocity measurements with automatic partitioning.
- **Database Federation (`postgres_fdw`)**: The TimescaleDB container configures a foreign server link (`host_postgres`) and maps schema `host_regenova`, allowing seamless cross-database analytical queries without breaking data boundaries.

---

## 4. Quickstart: Single-Command Deployment

```bash
# 1. Clone the repository
git clone https://github.com/imosudi/regenova.git
cd regenova

# 2. Configure environment (if needed)
cp .env.example .env

# 3. Execute automated deployment script
./scripts/deploy_docker.sh
```

---

## 5. Manual Step-by-Step Deployment

### Step 1: Validate Configuration
```bash
docker compose config
```

### Step 2: Build Images
```bash
docker compose build
```

### Step 3: Launch Containers
```bash
docker compose up -d
```

### Step 4: Verify Container Health
```bash
docker compose ps
```
All services should report `Up (healthy)`.

---

## 6. Reverse Proxy Configuration (Apache 2.4)

Each microservice binds locally to `127.0.0.1` and is exposed via Apache VirtualHosts with Let's Encrypt TLS:
- `flowfield.regenova.cloud` → `ProxyPass / http://127.0.0.1:1880/`
- `twinfield.regenova.cloud` → `ProxyPass / http://127.0.0.1:9000/`
- `api.regenova.cloud` → `ProxyPass / http://127.0.0.1:8101/`
- `backoffice.regenova.cloud` → `ProxyPass / http://127.0.0.1:8102/`
- `regenova.cloud` → `ProxyPass / http://127.0.0.1:8100/`
- `mosquitto.regenova.cloud` → `ProxyPass / http://127.0.0.1:9001/` (WebSockets)
