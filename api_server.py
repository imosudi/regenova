#!/usr/bin/env python3
"""
REGENOVA Dedicated API Server & WSGI Application.
Hosts https://api.regenova.cloud/ from /home/mosud/regenova_api.
Provides RESTful JSON endpoints, health checks, OpenAPI-style discovery,
and comprehensive cross-origin resource sharing (CORS) support.
"""

import sys
import os
import json
import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from web_server import GLOBAL_STATE, dispatch_api_request

API_VERSION = "1.0.0"
SERVICE_NAME = "REGENOVA Renewable Energy Asset Intelligence & Management API"

KNOWN_ENDPOINTS = [
    "/api/tenants",
    "/api/overview",
    "/api/sites",
    "/api/assets",
    "/api/asset/{id}",
    "/api/alerts",
    "/api/alerts/acknowledge",
    "/api/alerts/resolve",
    "/api/work-orders",
    "/api/work-orders/approve",
    "/api/adaptations",
    "/api/adaptations/propose",
    "/api/adaptations/approve",
    "/api/audit-chain",
    "/api/users",
    "/api/users/update-role",
    "/api/users/toggle-status",
    "/api/users/regenerate-token",
    "/api/onboarding/tenant",
    "/api/onboarding/user",
    "/api/onboarding/facility",
    "/api/onboarding/device",
    "/api/telemetry/inject",
    "/api/database/status",
    "/api/admin/login",
    "/api/admin/verify",
]


def build_discovery_payload() -> dict:
    """Returns the API discovery and service health payload."""
    return {
        "service": SERVICE_NAME,
        "status": "healthy",
        "version": API_VERSION,
        "framework": "REAMP-MVP-Phase1-15",
        "web_client_url": "https://regenova.cloud/",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "endpoints": KNOWN_ENDPOINTS,
    }


def application(environ, start_response):
    """
    WSGI application handler for Apache mod_wsgi on https://api.regenova.cloud/.
    Handles CORS preflight, RESTful JSON routing, and health checks.
    """
    method = environ.get("REQUEST_METHOD", "GET").upper()
    raw_path = environ.get("PATH_INFO", "/")

    # 1. CORS Preflight Request
    if method == "OPTIONS":
        headers = [
            ("Content-Type", "text/plain"),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, HEAD"),
            ("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, X-Tenant-ID"),
            ("Access-Control-Max-Age", "86400"),
        ]
        start_response("204 No Content", headers)
        return [b""]

    # 2. Health & Service Discovery Check
    clean_path = raw_path.rstrip("/")
    if clean_path in ("", "/api", "/health", "/api/health"):
        discovery_data = build_discovery_payload()
        resp_bytes = json.dumps(discovery_data, indent=2, default=str).encode("utf-8")
        headers = [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(resp_bytes))),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, HEAD"),
            ("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, X-Tenant-ID"),
        ]
        start_response("200 OK", headers)
        if method == "HEAD":
            return [b""]
        return [resp_bytes]

    # 3. Path Normalization: Support both /api/overview and /overview
    api_path = raw_path
    if not api_path.startswith("/api/"):
        api_path = "/api" + (api_path if api_path.startswith("/") else "/" + api_path)

    payload = {}
    if method == "POST":
        try:
            content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
            if content_length > 0:
                body = environ["wsgi.input"].read(content_length).decode("utf-8")
                payload = json.loads(body) if body else {}
        except Exception as e:
            err_bytes = json.dumps({"status": "ERROR", "error": f"Invalid JSON payload: {e}"}).encode("utf-8")
            start_response("400 Bad Request", [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(err_bytes))),
                ("Access-Control-Allow-Origin", "*"),
            ])
            return [err_bytes]

    headers_dict = {
        "X-Tenant-ID": environ.get("HTTP_X_TENANT_ID"),
        "Authorization": environ.get("HTTP_AUTHORIZATION"),
        "Content-Type": environ.get("CONTENT_TYPE"),
    }
    from urllib.parse import parse_qs
    query_params = {k: v[0] for k, v in parse_qs(environ.get("QUERY_STRING", "")).items()}

    # 4. Dispatch to Central API Router
    status_code, data = dispatch_api_request(method, api_path, payload, headers=headers_dict, query_params=query_params)
    resp_bytes = json.dumps(data, indent=2, default=str).encode("utf-8")

    status_text = "200 OK" if status_code == 200 else (
        "404 Not Found" if status_code == 404 else f"{status_code} Error"
    )

    headers = [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(resp_bytes))),
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, HEAD"),
        ("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, X-Tenant-ID"),
    ]

    start_response(status_text, headers)
    if method == "HEAD":
        return [b""]
    return [resp_bytes]


class REAMPAPIRequestHandler(SimpleHTTPRequestHandler):
    """HTTP handler for local standalone testing of the API component."""

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_HEAD(self):
        self._handle_request("HEAD")

    def do_GET(self):
        self._handle_request("GET")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body) if body else {}
        except Exception as e:
            self._send_json({"status": "ERROR", "error": f"Invalid JSON body: {e}"}, status=400)
            return
        self._handle_request("POST", payload)

    def _handle_request(self, method: str, payload: dict = None):
        parsed = urlparse(self.path)
        path = parsed.path

        clean_path = path.rstrip("/")
        if clean_path in ("", "/api", "/health", "/api/health"):
            self._send_json(build_discovery_payload(), status=200, is_head=(method == "HEAD"))
            return

        api_path = path if path.startswith("/api/") else "/api" + (path if path.startswith("/") else "/" + path)
        status_code, data = dispatch_api_request(method, api_path, payload)
        self._send_json(data, status=status_code, is_head=(method == "HEAD"))

    def _send_json(self, data, status=200, is_head=False):
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        if not is_head:
            self.wfile.write(body)


def run_api_server(port=8001):
    server_address = ("", port)
    httpd = HTTPServer(server_address, REAMPAPIRequestHandler)
    print(f"================================================================")
    print(f" {SERVICE_NAME}")
    print(f" Local API Server running on port {port}")
    print(f" Base URL: http://localhost:{port}/")
    print(f"================================================================")
    httpd.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    run_api_server(port)
