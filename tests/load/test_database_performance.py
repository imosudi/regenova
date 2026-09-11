"""
REAMP Load Testing - Database & Storage Engine Performance.
Evaluates time-series database scalability:
1. Transaction commit batching performance (Single vs 50 vs 250 vs 1000 rows/batch)
2. Time-series temporal window query latency (B-Tree index efficiency on 20,000+ observations)
3. Disk / in-memory storage footprint (bytes per observation)
"""

import time
import sqlite3
import datetime
from typing import Dict, Any


def run_database_performance_benchmark() -> Dict[str, Any]:
    """Execute database insertion batching and query indexing benchmarks."""
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()

    # DDL matching REAMP time-series edge buffer schema
    cur.execute("""
        CREATE TABLE time_series_observations (
            sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL NOT NULL,
            timestamp TEXT NOT NULL,
            quality TEXT NOT NULL DEFAULT 'VALID',
            is_acknowledged INTEGER NOT NULL DEFAULT 0
        );
    """)
    cur.execute("""
        CREATE INDEX idx_ts_asset_time ON time_series_observations(asset_id, timestamp);
    """)
    conn.commit()

    # 1. Batching Performance Evaluation
    batch_sizes = [1, 50, 250, 1000]
    total_test_rows = 2000
    batching_results = []

    now_base = datetime.datetime(2026, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)

    for b_size in batch_sizes:
        cur.execute("DELETE FROM time_series_observations;")
        conn.commit()

        t_start = time.perf_counter()
        rows_inserted = 0

        while rows_inserted < total_test_rows:
            batch_count = min(b_size, total_test_rows - rows_inserted)
            batch_data = [
                (
                    "TENANT-SOLAR-CORP",
                    f"ASSET-INV-{i % 100:03d}",
                    "active_power_kw",
                    1800.0 + (i % 50),
                    (now_base + datetime.timedelta(seconds=rows_inserted + i)).isoformat(),
                    "VALID",
                    1
                )
                for i in range(batch_count)
            ]
            cur.executemany("""
                INSERT INTO time_series_observations (tenant_id, asset_id, metric, value, timestamp, quality, is_acknowledged)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, batch_data)
            conn.commit()
            rows_inserted += batch_count

        dur_s = time.perf_counter() - t_start
        throughput_rows_sec = round(total_test_rows / dur_s, 2) if dur_s > 0 else 0.0
        latency_per_row_us = round((dur_s / total_test_rows) * 1_000_000, 2)

        batching_results.append({
            "batch_size": b_size,
            "total_rows": total_test_rows,
            "duration_s": round(dur_s, 4),
            "throughput_rows_sec": throughput_rows_sec,
            "latency_per_row_us": latency_per_row_us,
        })

    # 2. Populate 25,000 observations for Range Query Indexing Benchmarks
    cur.execute("DELETE FROM time_series_observations;")
    conn.commit()

    total_dataset_rows = 25000
    num_assets = 50
    rows_per_asset = total_dataset_rows // num_assets

    bulk_data = []
    for a in range(num_assets):
        asset_id = f"ASSET-INV-{a:03d}"
        for r in range(rows_per_asset):
            ts = (now_base + datetime.timedelta(seconds=r * 60)).isoformat()
            bulk_data.append((
                "TENANT-SOLAR-CORP",
                asset_id,
                "ac_power_kw",
                1500.0 + (r % 100),
                ts,
                "VALID",
                1
            ))

    cur.executemany("""
        INSERT INTO time_series_observations (tenant_id, asset_id, metric, value, timestamp, quality, is_acknowledged)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """, bulk_data)
    conn.commit()

    # 3. Query Benchmark: Retrieve 1-hour and 24-hour windows
    query_benchmarks = []
    target_asset = "ASSET-INV-005"

    # Window 1: 1-hour window (60 points)
    t0_iso = (now_base + datetime.timedelta(hours=2)).isoformat()
    t1_iso = (now_base + datetime.timedelta(hours=3)).isoformat()

    t_q1_start = time.perf_counter()
    for _ in range(50):
        cur.execute("""
            SELECT * FROM time_series_observations
            WHERE asset_id = ? AND timestamp BETWEEN ? AND ?;
        """, (target_asset, t0_iso, t1_iso))
        rows = cur.fetchall()
    dur_q1 = (time.perf_counter() - t_q1_start) / 50.0

    query_benchmarks.append({
        "query_type": "1_hour_window",
        "rows_returned": len(rows),
        "mean_latency_ms": round(dur_q1 * 1000.0, 3),
        "queries_per_sec": round(1.0 / dur_q1, 2) if dur_q1 > 0 else 0.0,
    })

    # Window 2: Full history window (500 points)
    t2_iso = (now_base + datetime.timedelta(hours=24)).isoformat()
    t_q2_start = time.perf_counter()
    for _ in range(50):
        cur.execute("""
            SELECT * FROM time_series_observations
            WHERE asset_id = ? AND timestamp BETWEEN ? AND ?;
        """, (target_asset, now_base.isoformat(), t2_iso))
        rows2 = cur.fetchall()
    dur_q2 = (time.perf_counter() - t_q2_start) / 50.0

    query_benchmarks.append({
        "query_type": "24_hour_window",
        "rows_returned": len(rows2),
        "mean_latency_ms": round(dur_q2 * 1000.0, 3),
        "queries_per_sec": round(1.0 / dur_q2, 2) if dur_q2 > 0 else 0.0,
    })

    # Page size and memory footprint estimation
    page_count = cur.execute("PRAGMA page_count;").fetchone()[0]
    page_size = cur.execute("PRAGMA page_size;").fetchone()[0]
    db_size_bytes = page_count * page_size
    bytes_per_row = round(db_size_bytes / max(1, total_dataset_rows), 2)

    conn.close()

    results = {
        "dataset_rows": total_dataset_rows,
        "database_size_bytes": db_size_bytes,
        "bytes_per_observation": bytes_per_row,
        "batching_evaluations": batching_results,
        "query_evaluations": query_benchmarks,
    }
    return results


if __name__ == "__main__":
    res = run_database_performance_benchmark()
    print("================================================================================")
    print(" REAMP DATABASE & STORAGE PERFORMANCE BENCHMARK")
    print("================================================================================")
    print(f"Total Rows: {res['dataset_rows']} | DB Size: {res['database_size_bytes']} bytes ({res['bytes_per_observation']} bytes/row)")
    print("\nBatching Ingestion:")
    for b in res["batching_evaluations"]:
        print(f"  Batch={b['batch_size']:4d} -> {b['throughput_rows_sec']:8.1f} rows/s ({b['latency_per_row_us']:6.1f} us/row)")
    print("\nQuery Indexing Latencies:")
    for q in res["query_evaluations"]:
        print(f"  Query: {q['query_type']:15s} -> {q['mean_latency_ms']} ms ({q['rows_returned']} rows returned | {q['queries_per_sec']} QPS)")
