"""
REAMP Load Testing - Edge/Fog Gateway Scaling Benchmarks.
Simulates distributed edge gateway architectures across scaling tiers:
- 10 gateways
- 50 gateways
- 200 gateways
- 500 gateways

Measures:
- Distributed local edge buffering throughput
- Central backfill ingestion throughput
- Zero data loss under multi-gateway load
- Backlog drainage latency
"""

import time
import datetime
from typing import Dict, Any, List
from reamp.edge.buffer import SQLiteEdgeBuffer
from reamp.edge.models import TelemetryObservation, QualityFlag, CommunicationStatus
from reamp.mvp import REAMPApplicationMVP, AssetRecord, AssetStatus


def run_edge_fog_scaling_benchmark(gateway_counts: List[int] = None) -> Dict[str, Any]:
    """Execute edge/fog multi-gateway scaling benchmark."""
    if gateway_counts is None:
        gateway_counts = [10, 50, 100, 250]

    benchmark_results = {}
    samples_per_gateway = 25  # 25 chronological observations per gateway

    for num_gateways in gateway_counts:
        app = REAMPApplicationMVP(storage_db=":memory:")
        app.initialize_default_topology()

        # 1. Instantiate distributed edge buffers (simulating independent hardware gateways)
        gateways = [SQLiteEdgeBuffer(db_path=":memory:") for _ in range(num_gateways)]

        now_dt = datetime.datetime.now(datetime.timezone.utc)
        total_observations = num_gateways * samples_per_gateway

        # Register assets for each gateway
        for g_idx in range(num_gateways):
            app.register_asset(
                AssetRecord(
                    asset_id=f"ASSET-GW-{g_idx:04d}",
                    site_id="SITE-MOJAVE-01",
                    name=f"Gateway Inverter #{g_idx}",
                    asset_type="INVERTER",
                    model="Sungrow SG2500HV",
                    rated_power_kw=2500.0,
                    commissioned_date=now_dt,
                    status=AssetStatus.ACTIVE
                )
            )

        # 2. Phase 1: Local Edge Buffering Across All Gateways
        t_buffer_start = time.perf_counter()
        for g_idx, gw in enumerate(gateways):
            asset_id = f"ASSET-GW-{g_idx:04d}"
            for s in range(samples_per_gateway):
                obs = TelemetryObservation(
                    tenant_id=app.tenant_id,
                    asset_id=asset_id,
                    sensor_id=f"SENS-GW{g_idx}-PDC",
                    metric="dc_power_kw",
                    value=2000.0 + (s * 0.5),
                    unit="kW",
                    timestamp=(now_dt + datetime.timedelta(seconds=s)).isoformat(),
                    source="EDGE_GATEWAY_LOCAL",
                    quality=QualityFlag.VALID,
                    communication_status=CommunicationStatus.BUFFERED,
                )
                gw.insert(obs)

        t_buffer_end = time.perf_counter()
        buffer_duration_s = t_buffer_end - t_buffer_start
        buffer_throughput_obs_sec = round(total_observations / buffer_duration_s, 2) if buffer_duration_s > 0 else 0.0

        # 3. Phase 2: Concurrent Backfill Synchronization to Central Cloud
        t_sync_start = time.perf_counter()
        synced_count = 0

        for g_idx, gw in enumerate(gateways):
            asset_id = f"ASSET-GW-{g_idx:04d}"
            unacked = gw.get_unacknowledged_batch(limit=samples_per_gateway * 2)
            if unacked:
                highest_seq = max(item["sequence_id"] for item in unacked)
                for item in unacked:
                    app.process_telemetry_packet(
                        asset_id=asset_id,
                        telemetry={
                            "dc_power_kw": item["value"],
                            "poa_irradiance": 800.0,
                            "ambient_temp": 25.0,
                            "ac_power_kw": item["value"] * 0.98,
                            "heatsink_temp": 45.0,
                        }
                    )
                    synced_count += 1
                gw.acknowledge_batch(highest_seq)

        t_sync_end = time.perf_counter()
        sync_duration_s = t_sync_end - t_sync_start
        sync_throughput_obs_sec = round(synced_count / sync_duration_s, 2) if sync_duration_s > 0 else 0.0

        # Verify all gateways drained backlog to 0
        remaining_backlog = sum(gw.get_backlog_count() for gw in gateways)
        data_loss_rate = round((total_observations - synced_count) / max(1, total_observations), 6)

        benchmark_results[f"tier_{num_gateways}_gateways"] = {
            "gateway_count": num_gateways,
            "observations_per_gateway": samples_per_gateway,
            "total_observations": total_observations,
            "buffering_duration_s": round(buffer_duration_s, 4),
            "buffering_throughput_obs_sec": buffer_throughput_obs_sec,
            "sync_duration_s": round(sync_duration_s, 4),
            "sync_throughput_obs_sec": sync_throughput_obs_sec,
            "synced_count": synced_count,
            "remaining_backlog": remaining_backlog,
            "data_loss_rate_pct": data_loss_rate * 100.0,
            "backlog_drained": remaining_backlog == 0,
        }

    return benchmark_results


if __name__ == "__main__":
    results = run_edge_fog_scaling_benchmark()
    print("================================================================================")
    print(" REAMP EDGE/FOG GATEWAY SCALING BENCHMARK RESULTS")
    print("================================================================================")
    for tier, data in results.items():
        print(f"\n[{tier.upper()}] (Gateways: {data['gateway_count']} | Obs: {data['total_observations']})")
        print(f"  Buffering:   {data['buffering_throughput_obs_sec']} obs/sec in {data['buffering_duration_s']} s")
        print(f"  CentralSync: {data['sync_throughput_obs_sec']} obs/sec in {data['sync_duration_s']} s")
        print(f"  Loss Rate:   {data['data_loss_rate_pct']:.4f}% | Backlog Drained: {data['backlog_drained']}")
