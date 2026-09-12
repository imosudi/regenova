#!/usr/bin/env python3
"""
REGENOVA Backoffice - Separated Admin Backend Management Server & WSGI Application.
Hosted at https://backoffice.regenova.cloud/
Application Directory: /home/mosud/backend

Interfaces directly with REGENOVA REST API on https://api.regenova.cloud
and PostgreSQL 18.6 database.
"""

import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Dict, List, Optional, Tuple

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_WEB_DIR = os.path.join(APP_DIR, "backend")

# Upstream API endpoint (can be overridden via REGENOVA_API_URL env var)
DEFAULT_API_URL = os.environ.get("REGENOVA_API_URL", "https://api.regenova.cloud")


class BackofficeRequestHandler(SimpleHTTPRequestHandler):
    """HTTP Request Handler for standalone Backoffice development server."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BACKEND_WEB_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._proxy_api_request("GET")
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._proxy_api_request("POST")
        else:
            self.send_error(405, "Method Not Allowed")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Tenant-ID")
        self.end_headers()

    def _proxy_api_request(self, method: str):
        target_url = f"{DEFAULT_API_URL}{self.path}"
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else None

        req_headers = {}
        for h in ["Content-Type", "Authorization", "X-Tenant-ID", "x-tenant-id", "X-Admin-Token", "x-admin-token"]:
            if h in self.headers:
                req_headers[h] = self.headers[h]

        try:
            req = urllib.request.Request(target_url, data=body, headers=req_headers, method=method)
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_data = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in ("content-type", "access-control-allow-origin"):
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(resp_data)))
                self.end_headers()
                self.wfile.write(resp_data)
        except urllib.error.HTTPError as e:
            err_data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err_data)))
            self.end_headers()
            self.wfile.write(err_data)
        except Exception as e:
            err_obj = json.dumps({"error": f"Gateway error proxying to API: {str(e)}"}).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err_obj)))
            self.end_headers()
            self.wfile.write(err_obj)


def application(environ, start_response):
    """
    WSGI Entry Point for Apache mod_wsgi.
    Directly serves Backoffice static web files and proxies API requests if needed.
    """
    method = environ.get("REQUEST_METHOD", "GET").upper()
    raw_path = environ.get("PATH_INFO", "/")

    # 1. CORS Preflight
    if method == "OPTIONS":
        start_response("200 OK", [
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Tenant-ID"),
        ])
        return [b""]

    # 2. Reverse proxy fallback for /api/ requests
    if raw_path.startswith("/api/"):
        query_string = environ.get("QUERY_STRING", "")
        target_url = f"{DEFAULT_API_URL}{raw_path}"
        if query_string:
            target_url += f"?{query_string}"

        body = None
        content_len = int(environ.get("CONTENT_LENGTH", 0) or 0)
        if content_len > 0:
            body = environ["wsgi.input"].read(content_len)

        req_headers = {}
        for k, v in environ.items():
            if k == "CONTENT_TYPE":
                req_headers["Content-Type"] = v
            elif k.startswith("HTTP_"):
                header_name = k[5:].replace("_", "-").title()
                if header_name in ("Authorization", "X-Tenant-Id", "Content-Type", "X-Admin-Token"):
                    req_headers[header_name] = v

        try:
            req = urllib.request.Request(target_url, data=body, headers=req_headers, method=method)
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_bytes = resp.read()
                resp_status = f"{resp.status} OK" if resp.status == 200 else f"{resp.status} Status"
                headers = [
                    ("Content-Type", resp.headers.get("Content-Type", "application/json")),
                    ("Content-Length", str(len(resp_bytes))),
                    ("Access-Control-Allow-Origin", "*"),
                ]
                start_response(resp_status, headers)
                return [resp_bytes]
        except urllib.error.HTTPError as e:
            err_data = e.read()
            start_response(f"{e.code} Error", [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(err_data))),
                ("Access-Control-Allow-Origin", "*"),
            ])
            return [err_data]
        except Exception as e:
            err_msg = json.dumps({"error": f"API Gateway error: {str(e)}"}).encode("utf-8")
            start_response("502 Bad Gateway", [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(err_msg))),
                ("Access-Control-Allow-Origin", "*"),
            ])
            return [err_msg]

    # 3. Static Web Files
    subpath = raw_path.lstrip("/")
    if not subpath or subpath == "":
        subpath = "index.html"

    file_path = os.path.abspath(os.path.join(BACKEND_WEB_DIR, subpath))
    # Path traversal protection
    if not file_path.startswith(BACKEND_WEB_DIR) or not os.path.isfile(file_path):
        resp = b"404 Not Found"
        start_response("404 Not Found", [
            ("Content-Type", "text/plain"),
            ("Content-Length", str(len(resp))),
        ])
        return [resp]

    mime, _ = mimetypes.guess_type(file_path)
    if not mime:
        if file_path.endswith(".css"):
            mime = "text/css"
        elif file_path.endswith(".js"):
            mime = "application/javascript"
        else:
            mime = "application/octet-stream"

    with open(file_path, "rb") as f:
        file_content = f.read()

    headers = [
        ("Content-Type", mime),
        ("Content-Length", str(len(file_content))),
    ]
    start_response("200 OK", headers)
    return [file_content]


def run_backoffice_server(port=8080):
    server_address = ("", port)
    httpd = HTTPServer(server_address, BackofficeRequestHandler)
    print("================================================================")
    print(" REGENOVA Backoffice Management Server Running")
    print(f" Local URL: http://localhost:{port}")
    print(f" Upstream API: {DEFAULT_API_URL}")
    print("================================================================")
    httpd.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_backoffice_server(port)
