"""API 数据模型（Sprint 4.4.1，Pydantic）。

注意：ORM 模型放在 database.py（留待后续 Sprint 做 SQLite 存储），
此处仅定义 REST 响应模型。
"""

from pydantic import BaseModel


class StatusOut(BaseModel):
    time: float
    running: bool
    state: str  # idle / ready / running / paused / finished
    pending: int  # 事件队列中剩余未执行事件数
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
    event: str  # TRANSMIT / RETRANSMIT
    node: str
    sf: int
    rssi: float | None = None
    snr: float | None = None
    gateway: str | None = None
    success: bool | None = None  # 本次尝试成败（网关计数差分得到）


class TimelineOut(BaseModel):
    time: float  # 时间桶起点
    received: int  # 桶内成功尝试数
    lost: int  # 桶内失败尝试数
    pdr: float  # 桶内瞬时 PDR = received/(received+lost)


class ExperimentEventOut(BaseModel):
    id: int
    seq: int
    time: float
    event: str | None = None  # TRANSMIT / RETRANSMIT
    node: str | None = None
    sf: int | None = None
    rssi: float | None = None
    snr: float | None = None
    gateway: str | None = None
    success: bool | None = None  # 本次尝试成败（网关计数差分得到）


class ExperimentOut(BaseModel):
    id: int
    seed: int | None = None
    node_count: int | None = None
    duration: float | None = None
    area_size: float | None = None
    gateway_cfg: list | None = None  # 网关拓扑（JSON 反序列化）
    adr_enabled: bool = False
    created_at: str | None = None
    finalized: bool = False
    statistics: dict | None = None  # 终态统计（JSON 反序列化）
    nodes: list | None = None  # 终态节点快照（JSON 反序列化）
    gateways: list | None = None  # 终态网关快照（JSON 反序列化）
    events: list[ExperimentEventOut] | None = None  # 全量逐事件记录


class ExperimentConfigIn(BaseModel):
    """POST /api/simulation/config 请求体（全部可选，缺省沿用当前生效值）。"""

    node_count: int | None = None
    area_size: float | None = None
    gateways: list[list] | None = None  # [[id, x, y], ...]
    seed: int | None = None
    duration: float | None = None
    adr_enabled: bool | None = None


class ExperimentConfigOut(BaseModel):
    """当前生效的实验参数（GET /api/simulation/config 响应）。"""

    node_count: int
    area_size: float
    gateways: list[list]
    seed: int
    duration: float
    adr_enabled: bool
