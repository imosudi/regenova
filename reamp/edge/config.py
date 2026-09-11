"""
REAMP Edge Configuration Module.
Loads runtime environment variables and device operational limits.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class EdgeConfig:
    """Runtime configuration for REAMP Edge Gateway."""
    tenant_id: str = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    site_id: str = "site-mojave-alpha"
    gateway_id: str = "gw-edge-01"
    db_path: str = "edge_buffer.db"
    cloud_endpoint: str = "https://gateway.reamp.io:8443/api/v1/telemetry/batch"
    batch_size: int = 1000
    flush_interval_sec: float = 0.5
    max_buffer_retention_hours: int = 72
    aggregation_window_sec: int = 60
    burst_cooldown_sec: int = 900
    mtls_client_cert: Optional[str] = None
    mtls_client_key: Optional[str] = None
    ca_cert: Optional[str] = None

    @classmethod
    def from_env(cls) -> "EdgeConfig":
        return cls(
            tenant_id=os.getenv("REAMP_TENANT_ID", "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"),
            site_id=os.getenv("REAMP_SITE_ID", "site-mojave-alpha"),
            gateway_id=os.getenv("REAMP_GATEWAY_ID", "gw-edge-01"),
            db_path=os.getenv("REAMP_EDGE_DB_PATH", "edge_buffer.db"),
            cloud_endpoint=os.getenv("REAMP_CLOUD_ENDPOINT", "https://gateway.reamp.io:8443/api/v1/telemetry/batch"),
            batch_size=int(os.getenv("REAMP_BATCH_SIZE", "1000")),
            flush_interval_sec=float(os.getenv("REAMP_FLUSH_INTERVAL_SEC", "0.5")),
            max_buffer_retention_hours=int(os.getenv("REAMP_MAX_BUFFER_HOURS", "72")),
            aggregation_window_sec=int(os.getenv("REAMP_AGGR_WINDOW_SEC", "60")),
            burst_cooldown_sec=int(os.getenv("REAMP_BURST_COOLDOWN_SEC", "900")),
            mtls_client_cert=os.getenv("REAMP_MTLS_CERT"),
            mtls_client_key=os.getenv("REAMP_MTLS_KEY"),
            ca_cert=os.getenv("REAMP_CA_CERT")
        )
