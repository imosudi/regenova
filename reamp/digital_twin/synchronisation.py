"""
REAMP Digital Twin Synchronization Engine.
Handles real-time telemetry validation, clock-drift checking, staleness watchdog monitoring,
and store-and-forward edge buffer re-synchronization.
"""

from typing import Dict, Any, List, Optional
import datetime

from reamp.digital_twin.models import SyncStatus


class DigitalTwinSyncEngine:
    """
    Manages edge-to-twin state synchronization, packet validation,
    staleness evaluation, and buffer reconciliation.
    """

    def __init__(
        self,
        heartbeat_timeout_seconds: float = 60.0,
        stale_timeout_seconds: float = 300.0,
        max_future_drift_seconds: float = 10.0,
    ) -> None:
        self.heartbeat_timeout = heartbeat_timeout_seconds
        self.stale_timeout = stale_timeout_seconds
        self.max_future_drift = max_future_drift_seconds
        self.last_sequence_number: int = -1

    def parse_iso_timestamp(self, ts_str: str) -> datetime.datetime:
        """Parses ISO 8601 string to timezone-aware UTC datetime."""
        clean_ts = ts_str.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(clean_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt

    def evaluate_sync_status(
        self,
        latest_telemetry_timestamp: str,
        current_time: Optional[datetime.datetime] = None,
        is_replaying_buffer: bool = False,
    ) -> SyncStatus:
        """
        Determines current synchronization status based on telemetry age.
        """
        if is_replaying_buffer:
            return SyncStatus.REPLAYING_BUFFER

        now = current_time or datetime.datetime.now(datetime.timezone.utc)
        packet_time = self.parse_iso_timestamp(latest_telemetry_timestamp)
        age_seconds = (now - packet_time).total_seconds()

        if age_seconds <= self.heartbeat_timeout:
            return SyncStatus.SYNCHRONIZED
        elif age_seconds <= self.stale_timeout:
            return SyncStatus.DEGRADED_COMMUNICATION
        else:
            return SyncStatus.OUT_OF_SYNC

    def validate_packet(
        self,
        telemetry: Dict[str, Any],
        current_time: Optional[datetime.datetime] = None,
    ) -> bool:
        """
        Validates packet timing against clock-skew limits and basic structure.
        Raises ValueError if packet timestamp violates future clock drift limits.
        """
        if "timestamp" not in telemetry:
            raise ValueError("Telemetry packet missing mandatory 'timestamp' field.")

        now = current_time or datetime.datetime.now(datetime.timezone.utc)
        packet_time = self.parse_iso_timestamp(telemetry["timestamp"])
        drift_seconds = (packet_time - now).total_seconds()

        if drift_seconds > self.max_future_drift:
            raise ValueError(
                f"Clock Skew Violation: Packet timestamp {telemetry['timestamp']} is "
                f"{drift_seconds:.1f}s in the future (max allowed: {self.max_future_drift}s)."
            )

        return True

    def reconcile_edge_buffer(
        self,
        buffered_records: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Sorts, deduplicates, and validates a batch of historical observations
        replayed from an edge store-and-forward SQLite buffer.
        """
        if not buffered_records:
            return []

        # 1. Deduplicate by (timestamp, sequence_number)
        seen_keys = set()
        deduped = []
        for rec in buffered_records:
            key = (rec.get("timestamp"), rec.get("sequence_number", 0))
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(rec)

        # 2. Sort monotonically by timestamp and sequence number
        sorted_records = sorted(
            deduped,
            key=lambda r: (self.parse_iso_timestamp(r["timestamp"]), r.get("sequence_number", 0)),
        )

        return sorted_records
