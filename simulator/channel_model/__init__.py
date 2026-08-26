"""
simulator.channel_model — 可插拔物理世界抽象层 (包结构重构 Task 2.4)

真实实现对 TransmissionContext / ChannelResult / ChannelModel 契约的承载点。
外部代码入口 (向后兼容, 零改动既有 import):

    from simulator.channel_model import ChannelModel, LogDistanceChannel, ...

注: 本包目录名为 channel_model/ 而非 channel/, 因为 simulator/ 下已存在
legacy 模块 channel.py (LoRaChannel), 同名包会与其冲突并遮蔽。保留
channel_model 这一对外路径名, 因此所有既有 `from simulator.channel_model
import ...` 调用点无需修改。
"""

from simulator.channel_model.adapter import ChannelModelLinkAdapter
from simulator.channel_model.base import (
    ChannelModel,
    ChannelResult,
    ENV_PATH_LOSS_EXPONENT,
    SF_SENSITIVITY,
    SPEED_OF_LIGHT,
    TransmissionContext,
)
from simulator.channel_model.log_distance import LogDistanceChannel
from simulator.channel_model.shadowing import ShadowingChannel
from simulator.channel_model.rayleigh import RayleighChannel

__all__ = [
    "ChannelModel",
    "ChannelResult",
    "TransmissionContext",
    "LogDistanceChannel",
    "ShadowingChannel",
    "RayleighChannel",
    "ChannelModelLinkAdapter",
    "SPEED_OF_LIGHT",
    "SF_SENSITIVITY",
    "ENV_PATH_LOSS_EXPONENT",
]
