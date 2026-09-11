"""
REAMP Modbus TCP/RTU Protocol Adapter.
Decodes 16-bit holding and input registers into physical telemetry measurements.
"""

import struct
import datetime
from typing import List, Dict, Any, Optional
from reamp.edge.adapters.base import BaseProtocolAdapter
from reamp.edge.models import TelemetryObservation, QualityFlag, CommunicationStatus


class ModbusRegisterMapping:
    def __init__(
        self,
        address: int,
        data_type: str,  # "UINT16", "INT16", "FLOAT32"
        scale_factor: float,
        asset_id: str,
        sensor_id: str,
        metric: str,
        unit: str,
        word_order: str = "BIG_ENDIAN"  # "BIG_ENDIAN" or "LITTLE_ENDIAN"
    ):
        self.address = address
        self.data_type = data_type
        self.scale_factor = scale_factor
        self.asset_id = asset_id
        self.sensor_id = sensor_id
        self.metric = metric
        self.unit = unit
        self.word_order = word_order


class ModbusProtocolAdapter(BaseProtocolAdapter):
    """Parses Modbus TCP/RTU registers and decodes them into canonical telemetry."""

    def __init__(
        self,
        name: str,
        tenant_id: str,
        site_id: str,
        host: str,
        port: int = 502,
        slave_id: int = 1,
        mappings: Optional[List[ModbusRegisterMapping]] = None
    ):
        super().__init__(name, tenant_id, site_id)
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.mappings = mappings or []

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def decode_registers(self, mapping: ModbusRegisterMapping, registers: List[int]) -> float:
        """Decode raw 16-bit register integers into scaled physical float."""
        if mapping.data_type == "UINT16":
            raw_val = registers[0] & 0xFFFF
            return float(raw_val) * mapping.scale_factor

        elif mapping.data_type == "INT16":
            raw_val = registers[0] & 0xFFFF
            if raw_val >= 0x8000:
                raw_val -= 0x10000
            return float(raw_val) * mapping.scale_factor

        elif mapping.data_type == "FLOAT32":
            if len(registers) < 2:
                raise ValueError("FLOAT32 decoding requires at least two 16-bit registers")
            reg0, reg1 = registers[0], registers[1]
            if mapping.word_order == "LITTLE_ENDIAN":
                reg0, reg1 = reg1, reg0
            raw_bytes = struct.pack(">HH", reg0, reg1)
            unpacked_float = struct.unpack(">f", raw_bytes)[0]
            return round(unpacked_float * mapping.scale_factor, 4)

        else:
            raise ValueError(f"Unsupported Modbus data type: {mapping.data_type}")

    def poll(self) -> List[TelemetryObservation]:
        """Poll simulated registers for testing / offline execution."""
        if not self._connected:
            return []

        # Simulated raw registers:
        # Address 40001: 2480 (UINT16, scale 0.1 -> 248.0 kW)
        # Address 40002: (FLOAT32 for voltage -> 480.0 V)
        # 480.0 in IEEE 754 float is 0x43F00000 -> reg0 = 0x43F0 (17392), reg1 = 0x0000 (0)
        sim_data = {
            40001: [2480],
            40002: [17392, 0]
        }
        return self.normalize(sim_data)

    def normalize(self, raw_register_table: Dict[int, List[int]]) -> List[TelemetryObservation]:
        observations = []
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for m in self.mappings:
            if m.address in raw_register_table:
                regs = raw_register_table[m.address]
                phys_val = self.decode_registers(m, regs)
                obs = TelemetryObservation(
                    tenant_id=self.tenant_id,
                    asset_id=m.asset_id,
                    sensor_id=m.sensor_id,
                    metric=m.metric,
                    value=phys_val,
                    unit=m.unit,
                    timestamp=now_str,
                    source="MODBUS_ADAPTER",
                    quality=QualityFlag.VALID,
                    confidence=1.0,
                    communication_status=CommunicationStatus.ONLINE
                )
                observations.append(obs)

        return observations
