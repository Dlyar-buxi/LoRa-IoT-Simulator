"""LoRa IoT Simulator —— 全局仿真配置。

所有可调参数集中在此，方便后续 Sprint 做实验与调优。
单位约定：距离=米(m)，功率=dBm，频率=Hz。
"""

import math

# ---------- 仿真农场区域 ----------
AREA_SIZE = 2000          # 农场面积 2km × 2km（米）
NODE_COUNT = 200          # 默认虚拟节点数（设计目标支持 1000+）
GATEWAY_COUNT = 2         # 网关数量

# ---------- LoRa 物理层 ----------
FREQUENCY = 868e6         # 868 MHz（欧洲 ISM 频段）
BANDWIDTH = 125e3         # 125 kHz（典型 LoRa 带宽）
TX_POWER = 14             # 默认发射功率 dBm（范围通常 2~20）
SF_RANGE = [7, 8, 9, 10, 11, 12]   # 扩频因子可选集
DEFAULT_SF = 7            # 默认 SF（近距离、高速）

# ---------- 通信参数 ----------
PACKET_INTERVAL = 300     # 发送周期（秒）= 5 分钟一次上报
NOISE_FLOOR = -120.0      # 噪声底（dBm）
COLLISION_SNR_THRESHOLD = 6.0   # 可成功解调所需最低 SNR（dB）

# ---------- 能量 / 电池模型 ----------
BATTERY_CAPACITY_MAH = 2000.0   # 电池容量 mAh
TX_CURRENT_MA = 120.0           # 发射电流 mA
RX_CURRENT_MA = 12.0            # 接收电流 mA
SLEEP_CURRENT_UA = 1.5          # 休眠电流 µA
VOLTAGE = 3.7                   # 标称电压 V

# ---------- 路径损耗模型（对数距离模型） ----------
PATH_LOSS_REF_DIST = 1.0        # 参考距离（米）
PATH_LOSS_REF = 40.0            # 参考距离处路径损耗（dB）
PATH_LOSS_EXPONENT = 2.8        # 路径损耗指数（自由空间=2.0，植被/建筑更高）
SHADOW_SIGMA = 4.0              # 阴影衰落标准差（dB，对数正态）

# ---------- 可复现性 ----------
SEED = 42                       # 随机种子，保证仿真可复现


def sf_to_time_on_air(sf, payload_bytes=12, bw=BANDWIDTH, preamble=8):
    """粗略估算 LoRa 空中时间（秒），用于能耗与容量分析。

    采用 Semtech 经典公式（忽略 CRC/头/校验细节的近似）。
    """
    bw_khz = bw / 1000.0
    de = 0  # 低速率优化关闭
    n_pre = preamble
    n_pl = payload_bytes
    crc = 1
    ih = 0  # 隐式头关闭
    # 符号数（Semtech 公式核心）
    numerator = 8 * n_pl - 4 * sf + 28 + 16 * crc - 20 * ih
    denominator = 4 * (sf - 2 * de)
    payload_sym = numerator / denominator if (denominator != 0 and numerator > 0) else 0.0
    total_sym = n_pre + (math.ceil(payload_sym) if payload_sym > 0 else 0)
    ts_sym = (2 ** sf) / bw_khz  # 每符号时间 ms
    return (total_sym * ts_sym) / 1000.0
