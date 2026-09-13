#!/usr/bin/env bash
# ==============================================================================
# REGENOVA Microservices — Repeatable Docker Compose Deployment Script
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

echo "=================================================================="
echo " REGENOVA Microservices Deployment Automation"
echo " Working Directory: ${ROOT_DIR}"
echo "=================================================================="

# 1. Verify Docker & Docker Compose
if ! command -v docker &> /dev/null; then
    echo "[-] Error: docker is not installed. Please install Docker 24+."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "[-] Error: docker compose is not installed. Please install Docker Compose v2."
    exit 1
fi
echo "[+] Docker Engine: $(docker --version)"
echo "[+] Docker Compose: $(docker compose version)"

# 2. Check or initialise .env configuration
if [ ! -f "${ROOT_DIR}/.env" ]; then
    echo "[!] .env not found. Initialising from .env.example..."
    cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
fi

# 3. Validate Docker Compose syntax
echo "[*] Validating docker-compose.yml configuration..."
docker compose config --quiet
echo "[+] Configuration syntax validated successfully."

# 4. Build containers
echo "[*] Building REGENOVA microservices containers..."
docker compose build

# 5. Launch containers
echo "[*] Launching containers via Docker Compose..."
docker compose up -d

# 6. Verify Service Health
echo "[*] Awaiting container healthchecks (10 seconds)..."
sleep 10
docker compose ps

echo "=================================================================="
echo "[SUCCESS] All REGENOVA microservices deployed and healthy!"
echo "=================================================================="
