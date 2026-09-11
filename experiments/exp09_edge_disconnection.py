"""
REAMP Experiment 09 - Edge/Cloud Disconnection & Store-and-Forward Resilience.

Test Condition:
- Simulates an edge gateway experiencing a complete WAN connection failure:
  1. Link dropped for 500 edge telemetry sampling cycles (500 observations)
  2. Edge buffer accumulates all observations in local ACID SQLite queue
  3. Link restored
  4. Complete FIFO backfill synchronization to central application
  5. Cryptographic audit chain verification across disconnect boundary

Evaluated Metrics:
- Data Loss Rate (target: 0.00%)
- Buffer Availability during outage (100.0%)
- Backfill Ingestion Rate (observations per second)
- FIFO Chronological Order Preservation
- Cryptographic Audit Integrity across disconnect/reconnect (100% valid)
"""

import time
from typing import Dict, Any

from experiments.common import (
    generate_diurnal_solar_telemetry,
    save_experiment_result,
)
from reamp.edge.buffer import SQLiteEdgeBuffer
from reamp.edge.models import TelemetryObservation, QualityFlag, CommunicationStatus
from reamp.mvp import REAMPApplicationMVP


def run_experiment(seed: int = 42) -> Dict[str, Any]:
    # 1. Central Application Runtime
    app = REAMPApplicationMVP(storage_db=":memory:")
    app.initialize_default_topology()

    # 2. Local Edge Buffer (simulating physical gateway disk storage)
    edge_buffer = SQLiteEdgeBuffer(db_path=":memory:")

    # Generate 500 telemetry observations during the outage window
    raw_stream = generate_diurnal_solar_telemetry(n_samples=500, seed=seed)

    # -------------------------------------------------------------------------
    # Phase 1: Disconnected Edge Buffering
    # -------------------------------------------------------------------------
    buffered_count = 0
    t_start_buffer = time.perf_counter()

    for row in raw_stream:
        obs = TelemetryObservation(
            tenant_id=app.tenant_id,
            asset_id="ASSET-INV-01",
            sensor_id="SENS-INV01-PDC",
            metric="dc_power_kw",
            value=row["dc_power_kw"],
            unit="kW",
            timestamp=row["timestamp"],
            source="EDGE_GATEWAY_OFFLINE",
            quality=QualityFlag.VALID,
            communication_status=CommunicationStatus.BUFFERED,
        )
        edge_buffer.insert(obs)
        buffered_count += 1

    t_buffer_duration = time.perf_counter() - t_start_buffer

    # Verify all records exist unacknowledged in the local queue
    unacked = edge_buffer.get_unacknowledged_batch(limit=1000)
    unacked_count_pre_sync = len(unacked)

    # -------------------------------------------------------------------------
    # Phase 2: WAN Link Restored -> Backfill FIFO Synchronization
    # -------------------------------------------------------------------------
    t_start_sync = time.perf_counter()
    synced_records = 0
    fifo_order_preserved = True
    last_seq = -1

    for item in unacked:
        seq_id = item["sequence_id"]
        if seq_id <= last_seq:
            fifo_order_preserved = False
        last_seq = seq_id

        # Ingest buffered packet into central REAMP application
        tel_data = {
            "dc_power_kw": item["value"],
            "poa_irradiance": 800.0,
            "ambient_temp": 25.0,
            "ac_power_kw": item["value"] * 0.98,
            "heatsink_temp": 45.0,
        }
        app.process_telemetry_packet(
            asset_id="ASSET-INV-01",
            telemetry=tel_data,
        )

        # Gateway marks record acknowledged
        edge_buffer.acknowledge_batch(seq_id)
        synced_records += 1

    t_sync_duration = time.perf_counter() - t_start_sync
    backfill_throughput = round(synced_records / t_sync_duration, 2) if t_sync_duration > 0 else 0.0

    # Verify buffer backlog is completely cleared
    remaining_unacked = edge_buffer.get_unacknowledged_batch(limit=1000)
    data_loss_count = buffered_count - synced_records
    data_loss_rate = round(data_loss_count / buffered_count, 6)

    # Verify central audit chain integrity
    audit_valid, broken_idx = app.audit_logger.verify_chain_integrity()

    results = {
        "experiment_id": "EXP09_EDGE_DISCONNECTION",
        "description": "Store-and-Forward Edge Disconnection & Backfill Synchronization",
        "outage_records_buffered": buffered_count,
        "synced_records_count": synced_records,
        "remaining_unacked_count": len(remaining_unacked),
        "data_loss_rate_pct": data_loss_rate * 100.0,
        "fifo_order_preserved": fifo_order_preserved,
        "performance_metrics": {
            "buffering_time_s": round(t_buffer_duration, 4),
            "sync_time_s": round(t_sync_duration, 4),
            "backfill_throughput_obs_sec": backfill_throughput,
        },
        "audit_integrity": {
            "is_valid": audit_valid,
            "total_chain_entries": len(app.audit_logger.get_entries()),
            "broken_index": broken_idx,
        },
    }

    save_experiment_result("EXP09_EDGE_DISCONNECTION", results)
    return results


if __name__ == "__main__":
    res = run_experiment()
    print(f"[{res['experiment_id']}] Disconnection Benchmark Results:")
    print(f"  Buffered:       {res['outage_records_buffered']} records")
    print(f"  Synchronized:   {res['synced_records_count']} records")
    print(f"  Data Loss Rate: {res['data_loss_rate_pct']:.4f}%")
    print(f"  FIFO Order:     {'PRESERVED' if res['fifo_order_preserved'] else 'VIOLATED'}")
    print(f"  Backfill Rate:  {res['performance_metrics']['backfill_throughput_obs_sec']} obs/sec")
    print(f"  Audit Integrity:{'VALID' if res['audit_integrity']['is_valid'] else 'COMPROMISED'}")
