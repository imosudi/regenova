"""
REAMP Load Testing — Asset Scaling Benchmarks.
Evaluates progressive asset scale tiers:
Tier 1: 10 assets
Tier 2: 100 assets
Tier 3: 1,000 assets
Tier 4: 10,000 assets

Measures:
- Ingestion throughput (observations/second)
- Latency distributions (P50, P95, P99, Mean)
- Memory footprint (MB via tracemalloc)
- CPU time and resource utilization
- Architectural limit identification
"""

import time
import datetime
import tracemalloc
from typing import Dict, Any, List
from reamp.mvp import REAMPApplicationMVP, AssetRecord, AssetStatus


def run_asset_scaling_benchmark(tiers: List[int] = None) -> Dict[str, Any]:
    """Execute progressive asset scaling benchmark across specified tiers."""
    if tiers is None:
        tiers = [10, 100, 1000, 10000]

    benchmark_results = {}
    now = datetime.datetime.now(datetime.timezone.utc)

    for n in tiers:
        tracemalloc.start()
        t_cpu_start = time.process_time()
        t_wall_start = time.perf_counter()

        # Initialize fresh application instance with in-memory storage
        app = REAMPApplicationMVP(storage_db=":memory:")
        app.initialize_default_topology()

        # 1. Register N assets
        for i in range(n):
            a = AssetRecord(
                asset_id=f"ASSET-INV-{i:05d}",
                site_id="SITE-MOJAVE-01",
                name=f"Inverter #{i}",
                asset_type="INVERTER",
                model="Sungrow SG2500HV",
                rated_power_kw=2500.0,
                commissioned_date=now,
                status=AssetStatus.ACTIVE
            )
            app.register_asset(a)

        t_reg_end = time.perf_counter()
        registration_duration_s = t_reg_end - t_wall_start

        # 2. Ingest telemetry burst across all N assets
        # Each packet contains 5 standard SCADA metrics
        telemetry_template = {
            "poa_irradiance": 850.0,
            "ambient_temp": 26.5,
            "ac_power_kw": 1950.0,
            "dc_power_kw": 2000.0,
            "heatsink_temp": 48.0,
        }

        latencies_ms = []
        t_ingest_start = time.perf_counter()

        # For 10,000 assets, process 2,500 active telemetry streams in benchmark run to balance CI runtime
        active_eval_count = min(n, 2500) if n >= 10000 else n
        for i in range(active_eval_count):
            asset_id = f"ASSET-INV-{i:05d}"
            t_single_start = time.perf_counter()
            app.process_telemetry_packet(asset_id, telemetry_template)
            latencies_ms.append((time.perf_counter() - t_single_start) * 1000.0)

        t_ingest_end = time.perf_counter()
        ingest_duration_s = t_ingest_end - t_ingest_start

        # Metrics computation
        total_obs = active_eval_count * 5  # 5 metrics per packet
        throughput_obs_sec = round(total_obs / ingest_duration_s, 2) if ingest_duration_s > 0 else 0.0
        throughput_packets_sec = round(active_eval_count / ingest_duration_s, 2) if ingest_duration_s > 0 else 0.0

        latencies_sorted = sorted(latencies_ms)
        p50 = round(latencies_sorted[int(len(latencies_sorted) * 0.50)], 3)
        p95 = round(latencies_sorted[int(len(latencies_sorted) * 0.95)], 3)
        p99 = round(latencies_sorted[int(len(latencies_sorted) * 0.99)], 3)
        mean_lat = round(sum(latencies_ms) / len(latencies_ms), 3)

        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        cpu_time_s = round(time.process_time() - t_cpu_start, 3)

        benchmark_results[f"tier_{n}_assets"] = {
            "registered_assets": n,
            "evaluated_assets": active_eval_count,
            "total_observations_ingested": total_obs,
            "registration_duration_s": round(registration_duration_s, 4),
            "ingestion_duration_s": round(ingest_duration_s, 4),
            "throughput_obs_per_sec": throughput_obs_sec,
            "throughput_packets_per_sec": throughput_packets_sec,
            "latency_p50_ms": p50,
            "latency_p95_ms": p95,
            "latency_p99_ms": p99,
            "mean_latency_ms": mean_lat,
            "peak_memory_mb": round(peak_mem / (1024 * 1024), 2),
            "cpu_time_s": cpu_time_s,
            "memory_per_asset_kb": round((peak_mem / 1024) / max(1, n), 2),
        }

    return benchmark_results


if __name__ == "__main__":
    results = run_asset_scaling_benchmark()
    print("================================================================================")
    print(" REAMP ASSET SCALING BENCHMARK RESULTS")
    print("================================================================================")
    for tier, data in results.items():
        print(f"\n[{tier.upper()}] (Assets: {data['registered_assets']})")
        print(f"  Throughput:  {data['throughput_obs_per_sec']} obs/sec ({data['throughput_packets_per_sec']} packets/s)")
        print(f"  Latency:     Mean: {data['mean_latency_ms']} ms | P50: {data['latency_p50_ms']} ms | P95: {data['latency_p95_ms']} ms | P99: {data['latency_p99_ms']} ms")
        print(f"  Memory:      Peak: {data['peak_memory_mb']} MB ({data['memory_per_asset_kb']} KB/asset)")
        print(f"  CPU Time:    {data['cpu_time_s']} s | Ingest Time: {data['ingestion_duration_s']} s")
