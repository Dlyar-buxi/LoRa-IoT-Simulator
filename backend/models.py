"""API 数据模型（Sprint 4.4.1，Pydantic）。

注意：ORM 模型放在 database.py（留待后续 Sprint 做 SQLite 存储），
此处仅定义 REST 响应模型。
"""

from pydantic import BaseModel


class StatusOut(BaseModel):
    time: float
    running: bool
    state: str                       # idle / ready / running / paused / finished
    pending: int                     # 事件队列中剩余未执行事件数
    generated: int
    received: int
    lost: int


class NodeOut(BaseModel):
    id: str
    sf: int
    rssi: float | None = None
    snr: float | None = None
    gateway: str | None = None
    x: float
    y: float
    battery: float
    online: bool


class GatewayOut(BaseModel):
    id: str
    received: int
    avg_rssi: float | None = None
    x: float
    y: float


class StatisticsOut(BaseModel):
    throughput: float
    pdr: float
    retransmissions: int


class PacketRecordOut(BaseModel):
    time: float
    event: str                       # TRANSMIT / RETRANSMIT
    node: str
    sf: int
    rssi: float | None = None
    snr: float | None = None
    gateway: str | None = None
    success: bool | None = None      # 本次尝试成败（网关计数差分得到）


class TimelineOut(BaseModel):
    time: float                       # 时间桶起点
    received: int                     # 桶内成功尝试数
    lost: int                        # 桶内失败尝试数
    pdr: float                       # 桶内瞬时 PDR = received/(received+lost)
