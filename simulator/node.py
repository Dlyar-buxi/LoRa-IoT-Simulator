"""传感器节点模拟器（虚拟设备）。

对应设计文档 V1.0 §5.1 SensorNode。
职责：生成传感数据、构造数据包、按工作模式消耗电量、移动位置。
"""

import time
import random

from simulator import config
from simulator.sensor import (
    TemperatureSensor,
    HumiditySensor,
    SoilSensor,
    LightSensor,
    CO2Sensor,
)
from simulator.packet import Packet


class SensorNode:
    """模拟一个 LoRa 传感节点（当前为纯软件虚拟设备）。"""

    def __init__(self, node_id, x, y, battery=100.0, sf=None,
                 tx_power=None, seed=None):
        self.node_id = node_id
        self.x = float(x)
        self.y = float(y)
        self.battery = float(battery)                       # 电量百分比 0~100
        self.sf = sf if sf is not None else config.DEFAULT_SF
        self.tx_power = tx_power if tx_power is not None else config.TX_POWER
        self.send_interval = config.PACKET_INTERVAL        # 发送周期（秒）
        self.last_seen = None                              # 最近成功通信时间
        self.online = True                                # 是否在线

        # 为每个传感器绑定独立随机源（基于节点 seed，保证可复现）
        rng = random.Random(seed)
        self.sensors = {
            "temperature": TemperatureSensor(rng, base=26.0, noise=1.5),
            "humidity": HumiditySensor(rng, base=62.0, noise=5.0),
            "soil": SoilSensor(rng, base=42.0, noise=4.0),
            "light": LightSensor(rng, base=42000.0, noise=4000.0),
            "co2": CO2Sensor(rng, base=420.0, noise=25.0),
        }

    # ---------- 数据生成 ----------
    def generate_data(self) -> dict:
        """生成一次传感数据（温度/湿度/土壤/光照/CO2）。"""
        return {name: s.read() for name, s in self.sensors.items()}

    def create_packet(self, timestamp=None) -> Packet:
        """根据当前传感数据构造一个待发送数据包。"""
        data = self.generate_data()
        return Packet(
            device_id=self.node_id,
            timestamp=timestamp if timestamp is not None else time.time(),
            payload=data,
            sf=self.sf,
            tx_power=self.tx_power,
            x=self.x,
            y=self.y,
        )

    # ---------- 能量模型 ----------
    def consume_energy(self, mode="tx", duration_s=1.0) -> float:
        """按工作模式消耗电量，返回本次消耗 mAh，并递减百分比。

        mode: "tx"(发射) / "rx"(接收) / 其它(休眠)
        """
        if mode == "tx":
            current_ma = config.TX_CURRENT_MA
        elif mode == "rx":
            current_ma = config.RX_CURRENT_MA
        else:
            current_ma = config.SLEEP_CURRENT_UA / 1000.0

        used_mah = current_ma * (duration_s / 3600.0)
        self.battery = max(0.0, self.battery -
                           (used_mah / config.BATTERY_CAPACITY_MAH) * 100.0)
        if self.battery <= 0:
            self.online = False
        return used_mah

    # ---------- 位置 ----------
    def update_position(self, dx, dy):
        """在平面内移动节点（带边界约束）。"""
        self.x = max(0.0, min(config.AREA_SIZE, self.x + dx))
        self.y = max(0.0, min(config.AREA_SIZE, self.y + dy))

    def __repr__(self):
        return (f"SensorNode(id={self.node_id}, "
                f"pos=({self.x:.0f},{self.y:.0f}), "
                f"batt={self.battery:.1f}%, sf={self.sf}, "
                f"online={self.online})")
