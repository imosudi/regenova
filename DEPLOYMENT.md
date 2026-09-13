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

## 2. Standardized Container Infrastructure (`docker/`)

All container definitions and runtime assets are organized into dedicated subdirectories under `docker/`:

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
└── mosquitto/
    └── mosquitto.conf          # MQTT TCP (1883) & WebSockets (9001) Configuration
```

---

## 3. Microservice Topology

| Container Name | Service Name | Dockerfile Path | Host Binding | Upstream Port |
| :--- | :--- | :--- | :--- | :--- |
| `regenova-flowfield` | `flowfield` | `docker/flowfield/Dockerfile` | `127.0.0.1:1880` | `1880` |
| `regenova-twinfield` | `twinfield` | `docker/twinfield/Dockerfile` | `127.0.0.1:9000` | `9000` |
| `regenova-api` | `regenova-api` | `docker/api/Dockerfile` | `127.0.0.1:8101` | `8001` |
| `regenova-backoffice` | `regenova-backoffice` | `docker/backoffice/Dockerfile` | `127.0.0.1:8102` | `8002` |
| `regenova-web` | `regenova-web` | `docker/web/Dockerfile` | `127.0.0.1:8100` | `8000` |
| `regenova-mosquitto` | `mosquitto` | `eclipse-mosquitto:2` | `0.0.0.0:1883`, `127.0.0.1:9001` | `1883`, `9001` |
| `regenova-redis` | `redis` | `redis:7-alpine` | `127.0.0.1:6380` | `6379` |
| `regenova-timescaledb` | `timescaledb` | `timescale/timescaledb:latest-pg16` | `127.0.0.1:5433` | `5432` |

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
