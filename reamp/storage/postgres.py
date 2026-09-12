"""
REAMP PostgreSQL Storage Backend.
Connects to PostgreSQL 16+ / TimescaleDB (e.g. host: db.regenova.cloud, dbname: regenova_db).
Manages multi-tenant relational persistence, entity synchronization, telemetry ingestion,
and cryptographic audit ledger persistence with graceful fallback resilience.
"""

import os
import sys
import uuid
import json
import logging
import datetime
from typing import Dict, Any, List, Optional, Tuple
from contextlib import contextmanager

logger = logging.getLogger("reamp.storage.postgres")

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    psycopg2 = None
    PSYCOPG2_AVAILABLE = False


def to_uuid_str(val: Any) -> str:
    """Converts any string or UUID into a standard UUID string deterministically."""
    if not val:
        return str(uuid.uuid4())
    val_str = str(val).strip()
    try:
        return str(uuid.UUID(val_str))
    except (ValueError, AttributeError):
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, val_str))


class PostgresDatabaseManager:
    """
    Enterprise relational database manager for REGENOVA.
    Persists asset hierarchies, user records, telemetry observations,
    and the SHA-256 audit ledger to PostgreSQL.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        dbname: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        connect_timeout: int = 5,
    ) -> None:
        self.host = host or os.environ.get("REAMP_DB_HOST") or os.environ.get("DB_HOST") or "db.regenova.cloud"
        self.port = int(port or os.environ.get("REAMP_DB_PORT") or os.environ.get("DB_PORT") or 5432)
        self.dbname = dbname or os.environ.get("REAMP_DB_NAME") or os.environ.get("DB_NAME") or "regenova_db"
        self.user = user or os.environ.get("REAMP_DB_USER") or os.environ.get("DB_USER") or "regenova_db"
        self.password = password or os.environ.get("REAMP_DB_PASSWORD") or os.environ.get("DB_PASSWORD") or "OmolileOtilile"
        self.connect_timeout = connect_timeout

        self._connected = False
        self._engine_version: Optional[str] = None
        self._last_error: Optional[str] = None

        # Verify initial connectivity
        self.test_connection()

    @contextmanager
    def get_connection(self):
        """Context manager providing a transactional PostgreSQL connection."""
        if not PSYCOPG2_AVAILABLE:
            raise RuntimeError("psycopg2 is not installed in the current environment")

        conn = psycopg2.connect(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            connect_timeout=self.connect_timeout,
        )
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def test_connection(self) -> bool:
        """Tests live database connectivity and captures version information."""
        if not PSYCOPG2_AVAILABLE:
            self._connected = False
            self._last_error = "psycopg2-binary is not installed"
            return False

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    row = cur.fetchone()
                    if row:
                        self._engine_version = row[0]
                        self._connected = True
                        self._last_error = None
                        return True
        except Exception as e:
            self._connected = False
            self._last_error = str(e)
            logger.warning(f"PostgreSQL connection to {self.host}:{self.port}/{self.dbname} failed: {e}")
            return False

        return False

    def get_status(self) -> Dict[str, Any]:
        """Returns diagnostic status of the PostgreSQL connection."""
        is_conn = self.test_connection()
        tables_count = 0
        if is_conn:
            try:
                with self.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
                        row = cur.fetchone()
                        if row:
                            tables_count = row[0]
            except Exception:
                pass

        return {
            "database": "PostgreSQL",
            "status": "CONNECTED" if is_conn else "DISCONNECTED",
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "engine_version": self._engine_version,
            "tables_count": tables_count,
            "driver": "psycopg2" if PSYCOPG2_AVAILABLE else "none",
            "last_error": self._last_error,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    # =========================================================================
    # Domain Entity Synchronization
    # =========================================================================

    def sync_organisation(self, tenant_id: str, name: str, code: str, billing_tier: str = "ENTERPRISE") -> bool:
        """Upserts an organization entity into PostgreSQL."""
        if not self._connected and not self.test_connection():
            return False

        tenant_uuid = to_uuid_str(tenant_id)
        sql = """
        INSERT INTO organisations (tenant_id, name, code, billing_tier)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (tenant_id) DO UPDATE
        SET name = EXCLUDED.name, code = EXCLUDED.code, billing_tier = EXCLUDED.billing_tier, updated_at = NOW();
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (tenant_uuid, name, code, billing_tier))
            return True
        except Exception as e:
            logger.error(f"Failed to sync organisation {tenant_id}: {e}")
            return False

    def sync_portfolio(self, portfolio_id: str, tenant_id: str, name: str, code: str, region: str = "Global", capacity_kw: float = 100000.0) -> bool:
        """Upserts a portfolio entity into PostgreSQL."""
        if not self._connected and not self.test_connection():
            return False

        tenant_uuid = to_uuid_str(tenant_id)
        # Ensure org exists
        self.sync_organisation(tenant_id, name=f"Org for {tenant_id}", code=tenant_id)

        sql = """
        INSERT INTO portfolios (id, tenant_id, organisation_id, name, code, region, target_capacity_kw)
        SELECT %s, %s, id, %s, %s, %s, %s
        FROM organisations WHERE tenant_id = %s
        ON CONFLICT (id) DO UPDATE
        SET name = EXCLUDED.name, region = EXCLUDED.region, target_capacity_kw = EXCLUDED.target_capacity_kw, updated_at = NOW();
        """
        port_uuid = to_uuid_str(portfolio_id)
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (port_uuid, tenant_uuid, name, code, region, capacity_kw, tenant_uuid))
            return True
        except Exception as e:
            logger.error(f"Failed to sync portfolio {portfolio_id}: {e}")
            return False

    def sync_site(self, site_id: str, tenant_id: str, portfolio_id: str, name: str, code: str, latitude: float, longitude: float, rated_capacity_mw: float, technology: str = "SOLAR_PV") -> bool:
        """Upserts a site and associated energy system into PostgreSQL."""
        if not self._connected and not self.test_connection():
            return False

        tenant_uuid = to_uuid_str(tenant_id)
        port_uuid = to_uuid_str(portfolio_id)
        site_uuid = to_uuid_str(site_id)

        # Ensure portfolio exists
        self.sync_portfolio(portfolio_id, tenant_id, name="Default Utility Portfolio", code=portfolio_id)

        sql_site = """
        INSERT INTO sites (id, tenant_id, portfolio_id, name, code, latitude, longitude)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE
        SET name = EXCLUDED.name, code = EXCLUDED.code, latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude, updated_at = NOW();
        """
        sql_sys = """
        INSERT INTO energy_systems (id, tenant_id, site_id, name, code, technology_type, nameplate_capacity_kw)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE
        SET technology_type = EXCLUDED.technology_type, nameplate_capacity_kw = EXCLUDED.nameplate_capacity_kw, updated_at = NOW();
        """
        sys_uuid = to_uuid_str(f"SYS-{site_id}")
        capacity_kw = rated_capacity_mw * 1000.0

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql_site, (site_uuid, tenant_uuid, port_uuid, name, code, latitude, longitude))
                    cur.execute(sql_sys, (sys_uuid, tenant_uuid, site_uuid, f"{name} Energy System", f"SYS-{code}", technology, capacity_kw))
            return True
        except Exception as e:
            logger.error(f"Failed to sync site {site_id}: {e}")
            return False

    def sync_asset(self, asset_id: str, tenant_id: str, site_id: str, name: str, code: str, asset_type: str, model: str, rated_power_kw: float) -> bool:
        """Upserts an asset into PostgreSQL."""
        if not self._connected and not self.test_connection():
            return False

        tenant_uuid = to_uuid_str(tenant_id)
        sys_uuid = to_uuid_str(f"SYS-{site_id}")
        asset_uuid = to_uuid_str(asset_id)

        sql = """
        INSERT INTO assets (id, tenant_id, energy_system_id, name, code, asset_type, model_number)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE
        SET name = EXCLUDED.name, model_number = EXCLUDED.model_number, updated_at = NOW();
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (asset_uuid, tenant_uuid, sys_uuid, name, code, asset_type, model))
            return True
        except Exception as e:
            logger.error(f"Failed to sync asset {asset_id}: {e}")
            return False

    def sync_user(self, user_id: str, tenant_id: str, email: str, full_name: str, role: str, is_active: bool = True, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Upserts an onboarded user with RBAC role into PostgreSQL."""
        if not self._connected and not self.test_connection():
            return False

        tenant_uuid = to_uuid_str(tenant_id)
        user_uuid = to_uuid_str(user_id)
        self.sync_organisation(tenant_id, name=f"Org for {tenant_id}", code=tenant_id)

        meta_json = json.dumps(metadata or {})
        sql = """
        INSERT INTO users (id, tenant_id, email, full_name, role, is_active, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (email) DO UPDATE
        SET full_name = EXCLUDED.full_name, role = EXCLUDED.role, is_active = EXCLUDED.is_active, metadata = EXCLUDED.metadata, updated_at = NOW();
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (user_uuid, tenant_uuid, email, full_name, role, is_active, meta_json))
            return True
        except Exception as e:
            logger.error(f"Failed to sync user {email}: {e}")
            return False

    def record_audit_block(self, entry_id: str, timestamp_str: str, actor_id: str, tenant_id: str, action: str, resource_id: str, outcome: str, entry_hash: str, prev_hash: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """Records a cryptographic audit block into audit_chain_blocks."""
        if not self._connected and not self.test_connection():
            return False

        sql = """
        INSERT INTO audit_chain_blocks (entry_id, timestamp, actor_id, tenant_id, action, resource_id, outcome, entry_hash, prev_hash, details)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (entry_id) DO NOTHING;
        """
        details_json = json.dumps(details or {})
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (entry_id, timestamp_str, actor_id, tenant_id, action, resource_id, outcome, entry_hash, prev_hash, details_json))
            return True
        except Exception as e:
            logger.error(f"Failed to record audit block {entry_id}: {e}")
            return False

    def record_telemetry_observation(self, timestamp_str: str, tenant_id: str, asset_id: str, metric: str, sensor_id: str, value: float, unit: str, source: str = "SCADA", quality: str = "VALID", confidence: float = 1.0) -> bool:
        """Records a telemetry observation row into telemetry_observations."""
        if not self._connected and not self.test_connection():
            return False

        tenant_uuid = to_uuid_str(tenant_id)
        asset_uuid = to_uuid_str(asset_id)
        sensor_uuid = to_uuid_str(sensor_id)

        sql = """
        INSERT INTO telemetry_observations (timestamp, tenant_id, asset_id, metric, sensor_id, value, unit, source, quality, confidence)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (timestamp, tenant_id, asset_id, metric) DO UPDATE
        SET value = EXCLUDED.value, quality = EXCLUDED.quality, confidence = EXCLUDED.confidence;
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (timestamp_str, tenant_uuid, asset_uuid, metric, sensor_uuid, float(value), unit, source, quality, float(confidence)))
            return True
        except Exception as e:
            logger.error(f"Failed to record telemetry for {asset_id} {metric}: {e}")
            return False
