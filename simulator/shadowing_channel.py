"""
simulator.shadowing_channel — 向后兼容 shim (Task 2.4 包结构重构)

真实实现对已迁入 simulator/channel_model/shadowing.py。
本文件仅作转发, 保证既有 import 路径零改动:

    from simulator.shadowing_channel import ShadowingChannel

新代码建议直接使用 simulator.channel_model。
"""

from simulator.channel_model import ShadowingChannel

__all__ = ["ShadowingChannel"]
