"""REST 路由（Sprint 4.4.1）。

只读查询接口，数据全部来自 SimulationEngine 单例。
路由前缀统一为 /api，便于后续 Web Dashboard 与 MQTT 扩展。
"""

from fastapi import APIRouter, HTTPException, Query

from .database import recorder
from .engine import engine
from .models import (
    ExperimentConfigIn,
    ExperimentConfigOut,
    ExperimentEventOut,
    ExperimentOut,
    GatewayOut,
    NodeOut,
    PacketRecordOut,
    StatisticsOut,
    StatusOut,
    TimelineOut,
)

router = APIRouter(prefix="/api", tags=["simulation"])


@router.get("/simulation/config", response_model=ExperimentConfigOut)
def get_simulation_config():
    """返回当前生效的实验参数（下一次 run 将使用的拓扑）。"""
    return engine.get_config()


@router.post("/simulation/config", response_model=ExperimentConfigOut)
def set_simulation_config(cfg: ExperimentConfigIn):
    """配置下一次 simulation run 的拓扑参数（全部字段可选，缺省沿用当前）。

    校验失败返回 400：node_count<=0 / gateway 为空 / id 重复 / 坐标超出区域。
    """
    # 计算本次生效的区域（用于坐标校验：优先用请求中的 area_size）
    eff_area = cfg.area_size if cfg.area_size is not None else engine.area_size

    if cfg.node_count is not None and cfg.node_count <= 0:
        raise HTTPException(status_code=400, detail="node_count must be > 0")
    if cfg.gateways is not None:
        if not cfg.gateways:
            raise HTTPException(status_code=400, detail="gateways must be non-empty")
        ids = [g[0] for g in cfg.gateways]
        if len(ids) != len(set(ids)):
            raise HTTPException(status_code=400, detail="gateway ids must be unique")
        for g in cfg.gateways:
            if len(g) < 3:
                raise HTTPException(
                    status_code=400, detail="gateway must be [id, x, y]"
                )
            x, y = g[1], g[2]
            if not (0 <= x <= eff_area and 0 <= y <= eff_area):
                raise HTTPException(
                    status_code=400,
                    detail=f"gateway {g[0]} coords ({x},{y}) out of area [0,{eff_area}]",
                )

    engine.configure(
        node_count=cfg.node_count,
        area_size=cfg.area_size,
        gateways=cfg.gateways,
        seed=cfg.seed,
        duration=cfg.duration,
        adr_enabled=cfg.adr_enabled,
    )
    return engine.get_config()


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


@router.get("/experiments", response_model=list[ExperimentOut])
def list_experiments():
    """已落盘实验列表（最新在前，不含 events 明细）。DB 禁用时返回空列表。"""
    return recorder.list_experiments()


@router.get("/experiments/{exp_id}", response_model=ExperimentOut)
def get_experiment(
    exp_id: int,
    events_limit: int = Query(
        1000,
        ge=-1,
        description=(
            "最多返回最近 N 条 events（按 seq 升序输出尾段；默认 1000 避免"
            "大体量实验打爆响应）。显式传 -1 表示不设上限（大实验慎用）。"
        ),
    ),
):
    """单条实验详情：元信息 + 终态 JSON + events（默认最多最近 1000 条）。"""
    exp = recorder.get_experiment(exp_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    # P1-7: 默认上限 1000。传 -1 走原生 None 语义（不限制）。
    limit = None if events_limit == -1 else events_limit
    exp["events"] = recorder.get_experiment_events(exp_id, limit=limit)
    return exp
