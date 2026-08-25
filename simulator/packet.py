"""LoRa 通信数据包。

节点构造时只填充发送侧字段；
rssi / snr / success 由信道模型与网关在传输过程中填充。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Packet:
    device_id: str
    timestamp: float
    payload: Dict[str, Any]
    sf: int
    tx_power: float
    x: float = 0.0
    y: float = 0.0
    rssi: Optional[float] = None
    snr: Optional[float] = None
    success: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        """转为可序列化字典（方便后续走 MQTT / JSON）。"""
        return {
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "sf": self.sf,
            "tx_power": self.tx_power,
            "x": self.x,
            "y": self.y,
            "rssi": self.rssi,
            "snr": self.snr,
            "success": self.success,
        }
