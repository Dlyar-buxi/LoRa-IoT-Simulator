from dataclasses import dataclass, field
import time


@dataclass
class Packet:
    node_id: str
    payload: dict
    sf: int
    tx_power: float

    timestamp: float = field(
        default_factory=time.time
    )

    # physical layer
    frequency: int = 868000000
    bandwidth: int = 125000
    coding_rate: str = "4/5"

    airtime: float = 0.0

    # transmission timing (Sprint 3.2)
    tx_start_time: float = 0.0
    tx_end_time: float = 0.0

    # position
    x: float = 0
    y: float = 0

    # channel result
    distance: float = 0
    gateway_id: str | None = None

    rssi: float | None = None
    snr: float | None = None

    collision: bool = False
    success: bool = False
    retry_count: int = 0

    def to_dict(self):
        return {
            "node_id": self.node_id,
            "payload": self.payload,
            "sf": self.sf,
            "tx_power": self.tx_power,
            "distance": self.distance,
            "tx_start_time": self.tx_start_time,
            "tx_end_time": self.tx_end_time,
            "rssi": self.rssi,
            "snr": self.snr,
            "collision": self.collision,
            "success": self.success,
            "retry_count": self.retry_count,
        }
