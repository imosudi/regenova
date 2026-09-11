#!/usr/bin/env python3
"""
REAMP Phase 5 — Automated Edge, Fog and IoT Integration Resilience Test Suite
Tests all 7 required failure modes and behaviors:
1. Valid Telemetry
2. Malformed Telemetry
3. Duplicate Telemetry
4. Delayed Telemetry
5. Disconnected Operation
6. Reconnection
7. Synchronisation & Backfill
8. Protocol Adapters (Modbus, OPC UA, MQTT, REST)
9. Local Alerting & Burst Mode
"""

import os
import sys
import uuid
import datetime
from typing import List, Dict, Any

# Ensure reamp package is importable
sys.path.insert(0, os.path.abspath("."))

from reamp.edge.models import TelemetryObservation, SensorConfig, EdgeAlert, QualityFlag, CommunicationStatus
from reamp.edge.config import EdgeConfig
from reamp.edge.buffer import SQLiteEdgeBuffer
from reamp.edge.pipeline import ValidationEngine, AggregationEngine
from reamp.edge.gateway import EdgeGateway
from reamp.edge.adapters.modbus import ModbusProtocolAdapter, ModbusRegisterMapping
from reamp.edge.adapters.opcua import OpcUaProtocolAdapter, OpcUaNodeMapping
from reamp.edge.adapters.mqtt import MqttProtocolAdapter
from reamp.edge.adapters.rest import RestProtocolAdapter

ERRORS = 0

def log_pass(msg: str):
    print(f"[\033[92mPASS\033[0m] {msg}")

def log_fail(msg: str):
    global ERRORS
    ERRORS += 1
    print(f"[\033[91mFAIL\033[0m] {msg}")


def test_valid_telemetry():
    print("\n--- 1. Testing Valid Telemetry Ingestion ---")
    gw = EdgeGateway(EdgeConfig(db_path=":memory:"))
    tenant_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    sensor_id = str(uuid.uuid4())

    gw.register_sensor(SensorConfig(
        sensor_id=sensor_id,
        asset_id=asset_id,
        metric="power_active_kw",
        unit="kW",
        min_range=0.0,
        max_range=3000.0,
        critical_high_threshold=2800.0
    ))

    obs = TelemetryObservation(
        tenant_id=tenant_id,
        asset_id=asset_id,
        sensor_id=sensor_id,
        metric="power_active_kw",
        value=2450.0,
        unit="kW",
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source="INVERTER_MODBUS"
    )

    res = gw.ingest(obs)
    if res["status"] == "INGESTED" and res["quality"] == "VALID" and res["confidence"] == 1.0:
        log_pass("Valid telemetry successfully validated and ingested with confidence 1.0")
    else:
        log_fail(f"Valid telemetry ingestion failed: {res}")
    gw.shutdown()


def test_malformed_telemetry():
    print("\n--- 2. Testing Malformed Telemetry Handling ---")
    gw = EdgeGateway(EdgeConfig(db_path=":memory:"))
    tenant_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    sensor_id = str(uuid.uuid4())

    gw.register_sensor(SensorConfig(
        sensor_id=sensor_id,
        asset_id=asset_id,
        metric="temp_cell_c",
        unit="degC",
        min_range=-20.0,
        max_range=85.0
    ))

    # Case A: Physically impossible value (> 85 C)
    obs_bad_val = TelemetryObservation(
        tenant_id=tenant_id,
        asset_id=asset_id,
        sensor_id=sensor_id,
        metric="temp_cell_c",
        value=150.0,  # Exceeds max_range 85.0
        unit="degC",
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    res_a = gw.ingest(obs_bad_val)
    if res_a["quality"] == "INVALID" and res_a["confidence"] == 0.0:
        log_pass("Impossible physical value flagged INVALID with confidence 0.0 (no silent drop)")
    else:
        log_fail(f"Malformed value not flagged INVALID: {res_a}")

    # Case B: Future-dated timestamp skew (+60 seconds in the future)
    future_ts = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60)).isoformat()
    obs_future = TelemetryObservation(
        tenant_id=tenant_id,
        asset_id=asset_id,
        sensor_id=sensor_id,
        metric="temp_cell_c",
        value=45.0,
        unit="degC",
        timestamp=future_ts
    )
    res_b = gw.ingest(obs_future)
    if res_b["quality"] == "INVALID" and res_b["confidence"] == 0.0:
        log_pass("Future timestamp skew flagged INVALID with confidence 0.0")
    else:
        log_fail(f"Future timestamp not flagged INVALID: {res_b}")
    gw.shutdown()


def test_duplicate_telemetry():
    print("\n--- 3. Testing Duplicate Telemetry Deduplication ---")
    gw = EdgeGateway(EdgeConfig(db_path=":memory:"))
    tenant_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    sensor_id = str(uuid.uuid4())
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    obs1 = TelemetryObservation(
        tenant_id=tenant_id, asset_id=asset_id, sensor_id=sensor_id,
        metric="wind_speed_ms", value=12.5, unit="m/s", timestamp=ts
    )
    obs2 = TelemetryObservation(
        tenant_id=tenant_id, asset_id=asset_id, sensor_id=sensor_id,
        metric="wind_speed_ms", value=12.5, unit="m/s", timestamp=ts
    )

    gw.ingest(obs1)
    gw.ingest(obs2)  # Duplicate key

    total = gw.buffer.get_total_count()
    if total == 1:
        log_pass("Duplicate observation handled idempotently (total buffer count remains 1)")
    else:
        log_fail(f"Expected 1 buffer record after duplicate, found {total}")
    gw.shutdown()


def test_delayed_telemetry():
    print("\n--- 4. Testing Delayed / Out-of-Order Telemetry ---")
    gw = EdgeGateway(EdgeConfig(db_path=":memory:"))
    tenant_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    sensor_id = str(uuid.uuid4())

    t0 = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)
    t1 = t0 + datetime.timedelta(seconds=1)
    t2 = t0 + datetime.timedelta(seconds=2)

    # Ingest in out-of-order sequence (t2, then t0, then t1)
    obs2 = TelemetryObservation(tenant_id=tenant_id, asset_id=asset_id, sensor_id=sensor_id, metric="m", value=2.0, unit="v", timestamp=t2.isoformat())
    obs0 = TelemetryObservation(tenant_id=tenant_id, asset_id=asset_id, sensor_id=sensor_id, metric="m", value=0.0, unit="v", timestamp=t0.isoformat())
    obs1 = TelemetryObservation(tenant_id=tenant_id, asset_id=asset_id, sensor_id=sensor_id, metric="m", value=1.0, unit="v", timestamp=t1.isoformat())

    gw.ingest(obs2)
    gw.ingest(obs0)
    gw.ingest(obs1)

    batch = gw.buffer.get_unacknowledged_batch(limit=10)
    if len(batch) == 3:
        log_pass("Out-of-order delayed telemetry preserved and extracted safely")
    else:
        log_fail(f"Expected 3 records in batch, got {len(batch)}")
    gw.shutdown()


def test_disconnected_operation_reconnection_and_sync():
    print("\n--- 5, 6, 7. Testing Disconnected Operation -> Reconnection -> Synchronisation ---")
    gw = EdgeGateway(EdgeConfig(db_path=":memory:"))
    tenant_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    sensor_id = str(uuid.uuid4())

    gw.register_sensor(SensorConfig(
        sensor_id=sensor_id, asset_id=asset_id, metric="power_active_kw", unit="kW",
        min_range=0.0, max_range=5000.0
    ))

    # Phase A: Disconnected Operation
    gw.simulate_wan_disconnect()
    if not gw.is_wan_online:
        log_pass("Simulated WAN link failure (WAN state = OFFLINE)")

    NUM_OBSERVATIONS = 100
    base_time = datetime.datetime.now(datetime.timezone.utc)
    for i in range(NUM_OBSERVATIONS):
        ts = (base_time + datetime.timedelta(seconds=i)).isoformat()
        obs = TelemetryObservation(
            tenant_id=tenant_id, asset_id=asset_id, sensor_id=sensor_id,
            metric="power_active_kw", value=2000.0 + i, unit="kW", timestamp=ts
        )
        gw.ingest(obs)

    backlog = gw.buffer.get_backlog_count()
    if backlog == NUM_OBSERVATIONS:
        log_pass(f"100% of observations safely buffered locally during WAN outage ({backlog} records)")
    else:
        log_fail(f"Expected {NUM_OBSERVATIONS} buffered records, got {backlog}")

    # Attempt synchronization while still disconnected
    synced_while_down = gw.synchronize_with_cloud()
    if synced_while_down == 0 and gw.buffer.get_backlog_count() == NUM_OBSERVATIONS:
        log_pass("Synchronization halted safely while WAN link is down (zero data corruption)")
    else:
        log_fail(f"Unexpected sync while offline: {synced_while_down}")

    # Phase B: Reconnection
    gw.simulate_wan_reconnect()
    if gw.is_wan_online:
        log_pass("Simulated WAN restoration (WAN state = ONLINE)")

    # Phase C: Synchronisation & Cloud Ingestion Verification
    cloud_received_records: List[Dict[str, Any]] = []

    def mock_cloud_receiver(batch: List[Dict[str, Any]]) -> bool:
        cloud_received_records.extend(batch)
        return True  # HTTP 200 ACK

    gw.cloud_transmit_callback = mock_cloud_receiver

    # Synchronize backlog
    synced_count = gw.synchronize_with_cloud(batch_size=50)  # first batch of 50
    synced_count_2 = gw.synchronize_with_cloud(batch_size=50) # second batch of 50

    total_synced = synced_count + synced_count_2
    if total_synced == NUM_OBSERVATIONS and len(cloud_received_records) == NUM_OBSERVATIONS:
        log_pass(f"Cloud received 100% of backfill stream ({total_synced}/{NUM_OBSERVATIONS} records synchronized)")
    else:
        log_fail(f"Backfill mismatch: synced {total_synced}, cloud received {len(cloud_received_records)}")

    # Verify backlog count is now 0
    remaining_backlog = gw.buffer.get_backlog_count()
    if remaining_backlog == 0:
        log_pass("Buffer backlog successfully cleared to 0 unacknowledged records")
    else:
        log_fail(f"Remaining backlog expected 0, got {remaining_backlog}")

    # Verify purging of acknowledged records
    purged = gw.buffer.purge_acknowledged()
    if purged == NUM_OBSERVATIONS and gw.buffer.get_total_count() == 0:
        log_pass(f"Acknowledged records purged ({purged} cleaned, SQLite buffer clean)")
    else:
        log_fail(f"Purge error: purged {purged}, remaining total {gw.buffer.get_total_count()}")

    gw.shutdown()


def test_local_alerting_and_burst_mode():
    print("\n--- 8. Testing Local Alerting & Burst-on-Anomaly Override ---")
    gw = EdgeGateway(EdgeConfig(db_path=":memory:"))
    tenant_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    sensor_id = str(uuid.uuid4())

    gw.register_sensor(SensorConfig(
        sensor_id=sensor_id,
        asset_id=asset_id,
        metric="temp_cell_max_c",
        unit="degC",
        min_range=-20.0,
        max_range=85.0,
        critical_high_threshold=65.0  # Alert threshold
    ))

    # Trigger critical limit (70.0 >= 65.0)
    obs = TelemetryObservation(
        tenant_id=tenant_id, asset_id=asset_id, sensor_id=sensor_id,
        metric="temp_cell_max_c", value=70.0, unit="degC",
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    res = gw.ingest(obs)
    if res["alert_triggered"] and len(gw.active_alerts) == 1:
        alert = gw.active_alerts[0]
        if alert.severity == "CRITICAL" and alert.metric == "temp_cell_max_c":
            log_pass(f"Immediate local safety alarm generated: {alert.alert_code} ({alert.message})")
        else:
            log_fail(f"Unexpected alert properties: {alert}")
    else:
        log_fail("Failed to trigger local alert on critical threshold breach")

    if gw.aggregator.burst_mode_active:
        log_pass("Burst Mode automatically activated on safety anomaly (streaming raw 1Hz telemetry)")
    else:
        log_fail("Burst mode was not activated after critical alarm")
    gw.shutdown()


def test_protocol_adapters():
    print("\n--- 9. Testing Protocol Adapters (Modbus, OPC UA, MQTT, REST) ---")
    tenant_id = "tenant-01"
    site_id = "site-01"

    # 1. Modbus Adapter
    modbus = ModbusProtocolAdapter(
        name="SMA_Inverter_01", tenant_id=tenant_id, site_id=site_id, host="192.168.1.100",
        mappings=[
            ModbusRegisterMapping(40001, "UINT16", 0.1, "inv-01", "sens-pwr", "power_active_kw", "kW"),
            ModbusRegisterMapping(40002, "FLOAT32", 1.0, "inv-01", "sens-volt", "voltage_ac_v", "V")
        ]
    )
    modbus.connect()
    modbus_obs = modbus.poll()
    if len(modbus_obs) == 2 and modbus_obs[0].value == 248.0 and modbus_obs[1].value == 480.0:
        log_pass(f"Modbus Adapter decoded registers correctly ({modbus_obs[0].metric}={modbus_obs[0].value} kW, {modbus_obs[1].metric}={modbus_obs[1].value} V)")
    else:
        log_fail(f"Modbus decoding error: {modbus_obs}")

    # 2. OPC UA Adapter
    opcua = OpcUaProtocolAdapter(
        name="Vestas_WTG_01", tenant_id=tenant_id, site_id=site_id, endpoint_url="opc.tcp://10.0.0.10:4840",
        mappings=[
            OpcUaNodeMapping("ns=2;s=Turbine.Nacelle.WindSpeed", "wtg-01", "sens-wind", "wind_speed_ms", "m/s"),
            OpcUaNodeMapping("ns=2;s=Turbine.Gearbox.BearingVibrationRMS", "wtg-01", "sens-vib", "vibration_rms", "mm/s")
        ]
    )
    opcua.connect()
    opcua_obs = opcua.poll()
    if len(opcua_obs) == 2 and opcua_obs[0].value == 12.8:
        log_pass(f"OPC UA Adapter mapped node values correctly ({opcua_obs[0].metric}={opcua_obs[0].value} m/s)")
    else:
        log_fail(f"OPC UA mapping error: {opcua_obs}")

    # 3. MQTT Adapter
    mqtt = MqttProtocolAdapter(name="Tracker_MQTT", tenant_id=tenant_id, site_id=site_id, broker_host="192.168.1.5")
    mqtt.connect()
    mqtt_obs = mqtt.poll()
    if len(mqtt_obs) == 1 and mqtt_obs[0].metric == "tracker_tilt_angle_deg" and mqtt_obs[0].value == 45.2:
        log_pass(f"MQTT Adapter parsed topic payload correctly ({mqtt_obs[0].metric}={mqtt_obs[0].value} deg)")
    else:
        log_fail(f"MQTT parsing error: {mqtt_obs}")

    # 4. REST Adapter
    rest = RestProtocolAdapter(
        name="Vaisala_Weather", tenant_id=tenant_id, site_id=site_id, endpoint_url="http://192.168.1.50/weather",
        metric_mappings={
            "poa_irradiance": {"asset_id": "met-01", "sensor_id": "sens-poa", "metric": "irradiance_poa_wm2", "unit": "W/m2"},
            "ambient_temp": {"asset_id": "met-01", "sensor_id": "sens-temp", "metric": "temp_ambient_c", "unit": "degC"}
        }
    )
    rest.connect()
    rest_obs = rest.poll()
    if len(rest_obs) == 2 and rest_obs[0].value in (28.4, 920.5):
        log_pass("REST Adapter polled and normalized weather observations correctly")
    else:
        log_fail(f"REST polling error: {rest_obs}")


def main():
    print("================================================================")
    print("REAMP Phase 5 Verification: Edge, Fog & IoT Integration")
    print("================================================================")

    test_valid_telemetry()
    test_malformed_telemetry()
    test_duplicate_telemetry()
    test_delayed_telemetry()
    test_disconnected_operation_reconnection_and_sync()
    test_local_alerting_and_burst_mode()
    test_protocol_adapters()

    print("\n================================================================")
    if ERRORS == 0:
        print("[\033[92mALL TESTS PASSED\033[0m] Phase 5 resilience and integration criteria satisfied!")
        sys.exit(0)
    else:
        print(f"[\033[91mFAILED\033[0m] {ERRORS} test(s) failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
