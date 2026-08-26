"""
Channel Model — 可插拔物理世界抽象层 (Sprint 6.3.4 · Task 2.2)

基类与契约定义。真实实现位于同包:
- log_distance.py  (LogDistanceChannel, v0.1 基线)
- shadowing.py     (ShadowingChannel, Task 3)
- adapter.py       (ChannelModelLinkAdapter, 向后兼容桥接)

接口契约冻结于:
- docs/design/channel-model-api.md
- docs/adr/ADR-001-channel-model-architecture.md

设计约束 (来自 ADR-001 / channel-model-api.md):
- evaluate() 必须是纯函数式: 不修改 Node / Gateway / MAC, 无副作用;
  仅读取 TransmissionContext 中的字段, 不回写任何对象。
- 所有未来模型 (Shadowing / Rayleigh / Urban / ML / DigitalTwin) 均为
  ChannelModel 的子类, 调用点 (仿真引擎) 保持不变。

物理约定 (与 simulator/channel.py 对齐):
- SF7..SF12 接收灵敏度表
- noise_floor 默认 -120 dBm
- 参考距离 d0 = 1 m, Friis 参考损耗

注 (Task 2.4 包结构重构): 本包目录名为 channel_model/ (而非 channel/),
因为 simulator/ 下已存在 legacy 模块 channel.py (LoRaChannel), 同名包会与其
冲突并遮蔽。channel_model/ 包承接原 channel_model.py 的对外导入路径, 因此
所有 `from simulator.channel_model import ...` 调用点零改动。
"""

from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


# 物理常量
SPEED_OF_LIGHT = 3.0e8  # m/s

# LoRa 典型接收灵敏度 (dBm), SF7..SF12 — 与 simulator/channel.py 一致
SF_SENSITIVITY = {
    7: -123,
    8: -126,
    9: -129,
    10: -132,
    11: -134,
    12: -137,
}

# 环境 -> 默认路径损耗指数 (n)。
# 仅作 LogDistanceChannel 基线参考; 不改变接口契约, 可用构造参数覆盖。
ENV_PATH_LOSS_EXPONENT = {
    "urban": 3.5,
    "suburban": 3.0,
    "rural": 2.7,
    "indoor": 3.2,
}


@dataclass
class TransmissionContext:
    """单次传输的输入契约。

    由仿真引擎在 Node 发出 packet 后、Gateway 接收前构建,
    ChannelModel 绝不读取节点/网关坐标, 只消费已算好的 distance 等字段。
    """

    tx_node: "Node"            # 发送节点 (只读引用, 不修改)
    rx_gateway: "Gateway"      # 目标网关 (只读引用, 不修改)
    distance: float            # 米, 由引擎根据坐标计算
    tx_power: float            # dBm, 节点发射功率
    frequency: float           # Hz (e.g. 868e6 for EU868)
    spreading_factor: int      # SF7..SF12
    bandwidth: float           # Hz (e.g. 125e3)
    environment: str           # "urban" | "suburban" | "indoor" | "rural"
    timestamp: float           # 仿真时钟, 秒


@dataclass
class ChannelResult:
    """单次传输的输出契约。

    字段稳定性 (Sprint 6.4 ChannelResult v1.1):
    - 既有 5 字段为稳定契约, 模型 / 适配器 / 消费者均依赖;
    - v1.1 新增 distance / path_loss (默认值 0.0): 使 Result 自描述一次链路
      计算 (无需反查 TransmissionContext), 支撑 Monte Carlo 与链路预算模块化;
    - 刻意不加入 success: success 是仿真高层 (packet collision) 结果, 由
      simulation.py 计算, 不属于信道模型物理输出
      (见 docs/design/channel-result-v1.md §3)。
    """

    rssi: float                # dBm, 接收信号强度
    snr: float                 # dB, 信噪比
    pdr: float                 # 0..1, 包投递概率
    packet_received: bool      # 本次传输采样得到的布尔结果
    propagation_delay: float   # 秒, 单向路径时延

    # --- v1.1 新增 (自描述链路, 默认 0.0 以兼容未显式赋值的构造) ---
    distance: float = 0.0      # 米, 物理传播距离 (来自 TransmissionContext.distance)
    path_loss: float = 0.0     # dB, 模型计算得到的路径损耗 PL(d)


class ChannelModel(ABC):
    """所有信道模型的抽象基类 — 唯一的扩展点。

    新增一种传播模型 = 新增一个 ChannelModel 子类, 其余代码无需改动。
    """

    @abstractmethod
    def evaluate(self, context: TransmissionContext) -> ChannelResult:
        """计算单次传输的链路质量。

        实现必须是纯函数式: 不修改 Node / Gateway / MAC, 无副作用;
        仅返回一个 ChannelResult。
        """
        ...
