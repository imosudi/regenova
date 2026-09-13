# REGENOVA FlowField — Deployment Audit (F0)

## 1. Host Infrastructure

- **Server Alias**: `regenova-server`
- **IPv4 Address**: `130.61.63.86`
- **Operating System**: Ubuntu 26.04.1 LTS (Resolute Raccoon)
- **Kernel**: Linux 6.8.0-1017-oracle (Oracle Cloud Infrastructure VM)
- **Primary User**: `mosud` (UID 1001, GID 1001)

---

## 2. Runtime Discovery

### Node.js
- **Local Machine**: `v18.19.1` (npm `9.2.0`)
- **Remote Server**: Currently not installed in system PATH. Candidate package in Ubuntu repository: Node.js `v22.22.1 LTS` (`22.22.1+dfsg+~cs22.19.15-1ubuntu1`).

### Node-RED
- **Local Machine**: Not installed globally.
- **Remote Server**: Not installed.
- **Target Runtime**: Node-RED LTS (v4.0.8+) to be installed in `/home/mosud/flowfield/node_modules/` or globally as appropriate during F1.

---

## 3. Network, DNS & Ingress

### DNS Resolution (VERIFIED)
- `flowfield.regenova.cloud` → `130.61.63.86` (A Record)
- `mosquitto.regenova.cloud` → `130.61.63.86` (A Record)
- `twinfield.regenova.cloud` → `130.61.63.86` (A Record)
- `api.regenova.cloud` → `130.61.63.86` (A Record)
- `backoffice.regenova.cloud` → `130.61.63.86` (A Record)
- `db.regenova.cloud` → `130.61.63.86` (A Record)
- `regenova.cloud` → `130.61.63.86` (A Record)

### Reverse Proxy (Apache 2.4.66)
- **VHost Configuration**: `/etc/apache2/sites-available/flowfield.regenova.cloud-le-ssl.conf`
- **Current VirtualHost Status**: Active on port 443 with valid SSL certificate (`twinfield.regenova.cloud/fullchain.pem` cert pool).
- **Missing Proxy Directives**: Currently lacks `ProxyPass / http://127.0.0.1:1880/`, `ProxyPassReverse`, and WebSocket rewrite rules.
- **HTTP (Port 80)**: `/etc/apache2/sites-available/flowfield.regenova.cloud.conf` permanently redirects (301) to HTTPS.

### Firewall & Ports (iptables)
- **Inbound Allowed Ports**:
  - `80` (HTTP)
  - `443` (HTTPS)
  - `22` (SSH)
  - `5432` (PostgreSQL)
  - `10000` (Webmin)
- **All other ports**: Rejected with `icmp-host-prohibited`.
- **Architectural Consequence**: FlowField Node-RED must bind to `127.0.0.1:1880` and be accessed exclusively via Apache reverse proxy on `https://flowfield.regenova.cloud/`.

---

## 4. Service Supervision

- **Supervisor**: systemd
- **Target Unit**: `/etc/systemd/system/flowfield.service`
  - User: `mosud`
  - Group: `mosud`
  - WorkingDirectory: `/home/mosud/flowfield`
  - ExecStart: `node-red -u /home/mosud/flowfield`
  - Restart: `always`
  - Environment: Production configurations loaded from `/home/mosud/flowfield/.env`

---

## 5. Deployment Verdict
- **Baseline Readiness**: All infrastructure primitives (DNS, TLS, Reverse Proxy host, systemd) are available.
- **Status**: `READY` for Phase F1 (Runtime Baseline).
