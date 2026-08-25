"""REST 路由（Sprint 4.4.1）。

只读查询接口，数据全部来自 SimulationEngine 单例。
路由前缀统一为 /api，便于后续 Web Dashboard 与 MQTT 扩展。
"""

from fastapi import APIRouter, Query

from .engine import engine
from .models import (
    GatewayOut,
    NodeOut,
    PacketRecordOut,
    StatisticsOut,
    StatusOut,
    TimelineOut,
)

router = APIRouter(prefix="/api", tags=["simulation"])


@router.get("/simulation/status", response_model=StatusOut)
def simulation_status():
    """仿真总体状态：时刻、引擎状态机、剩余事件数、生成/接收/丢失包数。"""
    return engine.get_status()


@router.post("/simulation/start")
def simulation_start():
    """开始运行（Pull 模型：仅置 running 标志，真正推进靠 /step）。"""
    engine.start()
    return engine.get_status()


@router.post("/simulation/pause")
def simulation_pause():
    """暂停（保留状态，可再次 start resume）。"""
    engine.pause()
    return engine.get_status()


@router.post("/simulation/step")
def simulation_step(steps: int = Query(1, ge=1, le=10000)):
    """推进 n 个离散事件（默认 1）。Dashboard 轮询此接口以绘制实时曲线。"""
    engine.step(steps)
    return engine.get_status()


@router.post("/simulation/stop")
def simulation_stop():
    """终止推进，保留当前状态供查看（不重置）。"""
    engine.stop()
    return engine.get_status()


@router.post("/simulation/reset")
def simulation_reset():
    """用同一 seed 重建仿真，回到 t=0 / received=0 / pending=200。"""
    engine.reset()
    return engine.get_status()


@router.get("/nodes", response_model=list[NodeOut])
def list_nodes():
    """所有节点快照：SF、RSSI/SNR、选中网关、坐标、电量、在线状态。"""
    return engine.get_nodes()


@router.get("/gateways", response_model=list[GatewayOut])
def list_gateways():
    """所有网关统计：接收包数、平均 RSSI、坐标。"""
    return engine.get_gateways()


@router.get("/statistics", response_model=StatisticsOut)
def network_statistics():
    """网络级统计：吞吐、PDR、重传次数。"""
    return engine.get_statistics()


@router.get("/packets", response_model=list[PacketRecordOut])
def list_packets(limit: int | None = Query(None, ge=1)):
    """事件级包历史（?limit=N 取最近 N 条）。"""
    return engine.get_packets(limit)


@router.get("/history", response_model=list[TimelineOut])
def timeline(bucket: float = Query(1.0, gt=0)):
    """实时链路时间桶聚合（?bucket=5 看 5 秒趋势）。"""
    return engine.get_history(bucket)


@router.get("/export/json")
def export_json():
    """组合导出：status / nodes / gateways / statistics / packets / history。"""
    return engine.get_export()
