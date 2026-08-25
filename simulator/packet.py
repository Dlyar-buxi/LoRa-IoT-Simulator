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

    def to_dict(self):
        return {
            "node_id": self.node_id,
            "payload": self.payload,
            "sf": self.sf,
            "tx_power": self.tx_power,
            "distance": self.distance,
            "rssi": self.rssi,
            "snr": self.snr,
            "collision": self.collision,
            "success": self.success
        }
