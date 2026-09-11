"""
REAMP Edge SQLite Store-and-Forward Buffer Engine.
Provides high-performance, crash-resilient transactional buffering for offline telemetry logging.
"""

import sqlite3
import datetime
from typing import List, Dict, Any, Optional
from reamp.edge.models import TelemetryObservation, QualityFlag, CommunicationStatus


class SQLiteEdgeBuffer:
    """Manages the local embedded SQLite queue with FIFO backfill semantics."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        cur = self._conn.cursor()
        cur.execute("PRAGMA journal_mode = WAL;")
        cur.execute("PRAGMA synchronous = NORMAL;")
        cur.execute("PRAGMA foreign_keys = ON;")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS edge_telemetry_buffer (
                sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                sensor_id TEXT NOT NULL,
                metric TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                quality TEXT NOT NULL DEFAULT 'VALID',
                confidence REAL NOT NULL DEFAULT 1.0,
                communication_status TEXT NOT NULL DEFAULT 'BUFFERED',
                buffered_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                is_acknowledged INTEGER NOT NULL DEFAULT 0 CHECK (is_acknowledged IN (0, 1)),
                ack_received_at TEXT
            );
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_edge_buffer_fifo 
                ON edge_telemetry_buffer(is_acknowledged, sequence_id ASC);
        """)

        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_edge_buffer_unique_obs 
                ON edge_telemetry_buffer(tenant_id, asset_id, metric, timestamp);
        """)

        self._conn.commit()

    def insert(self, obs: TelemetryObservation) -> int:
        """Insert a single observation into the buffer idempotently."""
        cur = self._conn.cursor()
        quality_str = obs.quality.value if isinstance(obs.quality, QualityFlag) else str(obs.quality)
        comm_str = (
            obs.communication_status.value
            if isinstance(obs.communication_status, CommunicationStatus)
            else str(obs.communication_status)
        )

        cur.execute("""
            INSERT INTO edge_telemetry_buffer (
                tenant_id, asset_id, sensor_id, metric, value, unit, timestamp, source, quality, confidence, communication_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (tenant_id, asset_id, metric, timestamp) DO UPDATE SET
                value = EXCLUDED.value,
                quality = EXCLUDED.quality,
                confidence = EXCLUDED.confidence;
        """, (
            obs.tenant_id, obs.asset_id, obs.sensor_id, obs.metric, obs.value, obs.unit,
            obs.timestamp, obs.source, quality_str, obs.confidence, comm_str
        ))
        self._conn.commit()
        return cur.lastrowid

    def insert_batch(self, observations: List[TelemetryObservation]) -> int:
        """Insert a batch of observations inside a single atomic transaction."""
        if not observations:
            return 0
        cur = self._conn.cursor()
        records = []
        for obs in observations:
            quality_str = obs.quality.value if isinstance(obs.quality, QualityFlag) else str(obs.quality)
            comm_str = (
                obs.communication_status.value
                if isinstance(obs.communication_status, CommunicationStatus)
                else str(obs.communication_status)
            )
            records.append((
                obs.tenant_id, obs.asset_id, obs.sensor_id, obs.metric, obs.value, obs.unit,
                obs.timestamp, obs.source, quality_str, obs.confidence, comm_str
            ))

        cur.executemany("""
            INSERT INTO edge_telemetry_buffer (
                tenant_id, asset_id, sensor_id, metric, value, unit, timestamp, source, quality, confidence, communication_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (tenant_id, asset_id, metric, timestamp) DO UPDATE SET
                value = EXCLUDED.value,
                quality = EXCLUDED.quality,
                confidence = EXCLUDED.confidence;
        """, records)
        self._conn.commit()
        return len(records)

    def get_unacknowledged_batch(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Fetch unacknowledged records in strict chronological FIFO order."""
        cur = self._conn.cursor()
        cur.execute("""
            SELECT sequence_id, tenant_id, asset_id, sensor_id, metric, value, unit,
                   timestamp, source, quality, confidence, communication_status
            FROM edge_telemetry_buffer
            WHERE is_acknowledged = 0
            ORDER BY sequence_id ASC
            LIMIT ?;
        """, (limit,))
        rows = cur.fetchall()

        results = []
        for r in rows:
            results.append({
                "sequence_id": r[0],
                "tenant_id": r[1],
                "asset_id": r[2],
                "sensor_id": r[3],
                "metric": r[4],
                "value": r[5],
                "unit": r[6],
                "timestamp": r[7],
                "source": r[8],
                "quality": r[9],
                "confidence": r[10],
                "communication_status": r[11]
            })
        return results

    def acknowledge_batch(self, highest_sequence_id: int) -> int:
        """Mark all buffered records up to highest_sequence_id as successfully delivered."""
        cur = self._conn.cursor()
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cur.execute("""
            UPDATE edge_telemetry_buffer
            SET is_acknowledged = 1,
                ack_received_at = ?
            WHERE sequence_id <= ? AND is_acknowledged = 0;
        """, (now_str, highest_sequence_id))
        self._conn.commit()
        return cur.rowcount

    def purge_acknowledged(self) -> int:
        """Purge acknowledged records from the SQLite storage to reclaim disk space."""
        cur = self._conn.cursor()
        cur.execute("DELETE FROM edge_telemetry_buffer WHERE is_acknowledged = 1;")
        self._conn.commit()
        return cur.rowcount

    def get_backlog_count(self) -> int:
        """Return the count of pending unacknowledged records."""
        cur = self._conn.cursor()
        cur.execute("SELECT COUNT(*) FROM edge_telemetry_buffer WHERE is_acknowledged = 0;")
        return cur.fetchone()[0]

    def get_total_count(self) -> int:
        """Return total record count in buffer."""
        cur = self._conn.cursor()
        cur.execute("SELECT COUNT(*) FROM edge_telemetry_buffer;")
        return cur.fetchone()[0]

    def close(self):
        """Close SQLite database connection."""
        self._conn.close()
