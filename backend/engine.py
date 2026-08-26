"""Simulation Engine Adapter（Sprint 4.4.2，交互式）。

把 simulator.Simulation 包装成可被 Backend / Dashboard 控制的交互式引擎：

    idle -> ready -> running <-> paused -> finished

- 构建时只建拓扑 + 排程，**不自动运行**（不再导入即跑完，避免终态）。
- step(n) 直接驱动冻结 Scheduler 的事件堆（heapq.heappop），
  不修改任何 simulator/ 冻结模块，零重复计算。
- 全部只读查询（get_status/get_nodes/...）数据来自现有仿真状态。

加固（v1.2 hardening）：
- `_lock`: threading.RLock 保护所有状态变更 + 查询；避免 FastAPI 线程池并发
  同时 step/reset/configure/get_* 造成的堆状态/history 错乱。
- `history`: collections.deque(maxlen=HISTORY_MAX_LEN) 环形缓冲，
  大实验下不会无限吃内存。
- `register_reset_hook` / `register_configure_hook`: 显式生命周期钩子，
  替换 main.py 里对 engine.reset / engine.configure 的 monkey-patch。

v1 拓扑（网关位置硬编码，避免改动已冻结的 simulator/config.py）：
    GW001 (500, 500)
    GW002 (1500, 1500)
"""

import collections
import heapq
import os
import random
import threading

from simulator import config
from simulator.node import SensorNode
from simulator.simulation import Simulation
from gateway.gateway import Gateway


# v1 固定拓扑：2 网关（不改冻结的 config.py）
GATEWAY_POSITIONS = [
    ("GW001", 500, 500),
    ("GW002", 1500, 1500),
]

# 在导入期捕获 config 默认 ADR（运行期 _build 会按实验重绑 config.ADR_ENABLED，
# 此处锁定「文件默认」，避免默认构造行为随运行期绑定漂移）。
DEFAULT_ADR_ENABLED = config.ADR_ENABLED

# history 环形缓冲上限（环境变量可覆盖，0=无限制但不推荐）
try:
    _raw = os.getenv("ENGINE_HISTORY_MAX_LEN", "10000")
    HISTORY_MAX_LEN = int(_raw) if _raw else 10000
except (TypeError, ValueError):
    HISTORY_MAX_LEN = 10000


class SimulationEngine:
    """交互式仿真引擎：构建即就绪，按调用方节奏 step 推进。

    线程安全：所有公共方法（configure / start / pause / stop / reset / step
    + 全部 get_* 查询）都走 self._lock（RLock，允许同一线程重入）。
    这保证 FastAPI 默认线程池在并发请求下不会把 scheduler 事件堆、
    history 缓冲和状态机读写出错。
    """

    def __init__(
        self,
        duration=60.0,
        seed=None,
        node_count=None,
        area_size=None,
        gateway_positions=None,
        adr_enabled=None,
    ):
        # 参数化实验入口：所有拓扑参数默认沿用冻结 config 的当前值，
        # 单例 SimulationEngine() 无参构造行为完全不变（200/2/2000/seed42/60s/ADR）。
        self.duration = duration
        self.seed = seed if seed is not None else config.SEED
        self.node_count = node_count if node_count is not None else config.NODE_COUNT
        self.area_size = area_size if area_size is not None else config.AREA_SIZE
        self.gateway_positions = (
            gateway_positions if gateway_positions is not None else GATEWAY_POSITIONS
        )
        self.adr_enabled = (
            adr_enabled if adr_enabled is not None else DEFAULT_ADR_ENABLED
        )
        self.sim = None
        # 状态机：idle(未建) -> ready(已建未跑) -> running <-> paused -> finished
        self.state = "idle"
        # P0-2: 环形缓冲 deque。maxlen=0 按 None（无限）处理但不推荐。
        if HISTORY_MAX_LEN and HISTORY_MAX_LEN > 0:
            self.history: collections.deque = collections.deque(maxlen=HISTORY_MAX_LEN)
        else:
            self.history: collections.deque = collections.deque()
        self._node_map = {}        # node_id -> SensorNode（O(1) 查找）
        self._gw_map = {}          # gateway id -> Gateway（O(1) 查找）
        self._telemetry_sink = None  # 可选遥测出口（单 callable，默认 None）
        # P0-4: 生命周期钩子，替代外部 monkey-patch
        #   pre_* : _build 之前执行（如 finalize 旧实验——需要读旧的 engine 状态）
        #   post_*: _build 之后执行（如 begin 新实验 DB 上下文）
        self._pre_reset_hooks = []
        self._post_reset_hooks = []
        self._pre_configure_hooks = []
        self._post_configure_hooks = []
        # P0-1: 公共锁（RLock：允许 step 内被 sink 调用 get_* 时不自锁）
        self._lock = threading.RLock()
        self._build()

    # ---------- 生命周期钩子（P0-4：替代 monkey-patch）----------

    def register_pre_reset_hook(self, fn):
        """注册「reset 真正执行 _build 之前」回调 fn() -> None。

        典型用途：main.py 里 finalize 旧实验（需要读旧 engine 状态）。
        """
        if not callable(fn):
            raise TypeError("reset hook must be callable")
        self._pre_reset_hooks.append(fn)

    def register_reset_hook(self, fn):
        """注册「reset 完成 (_build 之后)」回调 fn() -> None。

        典型用途：main.py 里为新实验开 DB 上下文。
        """
        if not callable(fn):
            raise TypeError("reset hook must be callable")
        self._post_reset_hooks.append(fn)

    def register_pre_configure_hook(self, fn):
        """注册「configure 真正执行 _build 之前」回调 fn() -> None。语义同 pre_reset。"""
        if not callable(fn):
            raise TypeError("configure hook must be callable")
        self._pre_configure_hooks.append(fn)

    def register_configure_hook(self, fn):
        """注册「configure 完成 (_build 之后)」回调 fn() -> None。语义同 reset hook。"""
        if not callable(fn):
            raise TypeError("configure hook must be callable")
        self._post_configure_hooks.append(fn)

    def _run_hooks(self, hooks):
        """执行一组钩子，任何异常内部吞掉（静默降级，不中断仿真）。"""
        for fn in hooks:
            try:
                fn()
            except Exception:
                pass

    # ---------- 拓扑构建（只读，不运行）----------

    def _build_topology(self):
        rng = random.Random(self.seed)
        nodes = [
            SensorNode(
                f"Node{i + 1:03}",
                rng.uniform(0, self.area_size),
                rng.uniform(0, self.area_size),
            )
            for i in range(self.node_count)
        ]
        gateways = [
            Gateway(gid, x, y) for gid, x, y in self.gateway_positions
        ]
        return nodes, gateways

    def _build(self):
        """构建仿真并排程，但**不运行**（交互式前置）。

        ADR 运行期绑定：每次重建都把 config.ADR_ENABLED 重新绑定为本实验值，
        避免不同实验之间 ADR 开关串味（不修改冻结 config.py 文件 / simulation.py）。

        注意：_build 内部假设调用方已经拿了 self._lock（所有公共入口都会拿）。
        """
        config.ADR_ENABLED = self.adr_enabled
        nodes, gateways = self._build_topology()
        self.sim = Simulation(nodes, gateways, self.duration)
        self._node_map = {n.node_id: n for n in nodes}
        self._gw_map = {g.id: g for g in gateways}
        # P0-2: 同步重置为 deque（保持构造时相同的 maxlen 语义）
        if HISTORY_MAX_LEN and HISTORY_MAX_LEN > 0:
            self.history = collections.deque(maxlen=HISTORY_MAX_LEN)
        else:
            self.history = collections.deque()
        self.state = "ready"

    # ---------- 参数化实验入口 ----------

    def configure(
        self,
        node_count=None,
        area_size=None,
        gateways=None,
        seed=None,
        duration=None,
        adr_enabled=None,
    ):
        """更新实验参数并重建拓扑（等价「参数化 reset」，回到 ready 状态）。

        - 仅更新显式传入的参数，其余沿用当前实例值。
        - 不创建第二个 engine；不影响已设置的 telemetry sink。
        - 每次重建都重新绑定 config.ADR_ENABLED（见 _build）。
        - P0-4: _build 前执行 pre_configure_hooks（可 finalize 旧实验），
          _build 后执行 post_configure_hooks（可开新实验 DB 上下文）。
        """
        with self._lock:
            # P0-4 pre：旧 engine 状态（stats/nodes/gateways）仍可用，finalize 放这里
            self._run_hooks(self._pre_configure_hooks)
            if node_count is not None:
                self.node_count = node_count
            if area_size is not None:
                self.area_size = area_size
            if gateways is not None:
                self.gateway_positions = gateways
            if seed is not None:
                self.seed = seed
            if duration is not None:
                self.duration = duration
            if adr_enabled is not None:
                self.adr_enabled = adr_enabled
            self._build()
            # P0-4 post：新实验拓扑已就绪，begin DB 上下文放这里
            self._run_hooks(self._post_configure_hooks)
            return self.state

    # ---------- 生命周期（状态机）----------

    def start(self):
        """置为 running（Pull 模型：仅切状态，不阻塞、不自动跑）。"""
        with self._lock:
            if self.state in ("ready", "paused"):
                self.state = "running"
            return self.state

    def pause(self):
        """运行态 -> 暂停（保留状态，可 resume）。"""
        with self._lock:
            if self.state == "running":
                self.state = "paused"
            return self.state

    def stop(self):
        """终止推进，保留当前状态供查看（不重置）。"""
        with self._lock:
            if self.state != "finished":
                self.state = "finished"
            return self.state

    def reset(self):
        """用同一 seed 重建，回到 t=0 / received=0 / pending=200。

        P0-4: _build 前执行 pre_reset_hooks（可 finalize 旧实验），
              _build 后执行 post_reset_hooks（可开新实验 DB 上下文）。
        """
        with self._lock:
            # pre：旧 engine 状态仍可用（stats/nodes/gateways）
            self._run_hooks(self._pre_reset_hooks)
            self._build()
            # post：新实验已就绪
            self._run_hooks(self._post_reset_hooks)
            return self.state

    def set_telemetry_sink(self, sink):
        """注入遥测出口（单 callable，默认 None）。

        每次 step() 生成一条 history 记录后调用 sink(record)。
        不引入 queue / thread / observer 框架——仅一个可选回调。
        sink 异常会被 step() 内部吞掉，绝不中断仿真推进。
        """
        with self._lock:
            self._telemetry_sink = sink

    def step(self, n=1):
        """推进 n 个离散事件（直接驱动冻结 Scheduler 的事件堆）。

        不修改 simulator/ 任何冻结模块：event_queue / current_time 是
        Scheduler 的公开属性，事件回调会正确改写 Simulation 全部状态
        （重传事件也会被 push 回同一个堆）。

        整个方法在 self._lock 下执行：避免并发 step 导致 heapq 被双线程
        同时 pop（会抛 IndexError/AssertionError 或静默损坏堆序）。
        """
        with self._lock:
            if self.sim is None or self.state == "finished":
                return 0
            if not self.sim.scheduler.event_queue:
                self.state = "finished"
                return 0

            executed = 0
            for _ in range(n):
                if not self.sim.scheduler.event_queue:
                    self.state = "finished"
                    break
                event = heapq.heappop(self.sim.scheduler.event_queue)
                self.sim.scheduler.current_time = event.time

                # 采集：回调前快照各网关 (success, failed) 计数
                before = {
                    gw.id: (gw.success_count, gw.failed_count)
                    for gw in self.sim.gateways
                }
                if event.callback is not None:
                    event.callback(event)

                # 回调后节点已更新 last_rssi/snr/selected_gateway/sf
                node = self._node_map.get(event.node_id)
                if node is not None:
                    gw_id = node.selected_gateway
                    success = None
                    if gw_id in before:
                        b_s, b_f = before[gw_id]
                        gw = self._gw_map[gw_id]
                        if gw.success_count > b_s:
                            success = True
                        elif gw.failed_count > b_f:
                            success = False
                    record = {
                        "time": round(self.sim.scheduler.current_time, 2),
                        "event": event.action,
                        "node": node.node_id,
                        "sf": node.sf,
                        "rssi": node.last_rssi,
                        "snr": node.last_snr,
                        "gateway": gw_id,
                        "success": success,
                    }
                    self.history.append(record)
                    # 遥测出口：append history 后立即外发（MQTT/WS），异常不影响仿真
                    # 注意：sink 内若调用 engine.get_*，因 RLock 可重入，不会死锁
                    if self._telemetry_sink is not None:
                        try:
                            self._telemetry_sink(record)
                        except Exception:
                            pass
                executed += 1

            if not self.sim.scheduler.event_queue:
                self.state = "finished"
            return executed

    # ---- 状态查询（数据来自现有仿真状态，零重复计算）----
    # 所有 get_* 加锁：读 sim / history 期间避免写并发造成的半更新快照。

    def get_status(self):
        with self._lock:
            stats = self.sim.statistics()
            return {
                "time": round(self.sim.scheduler.current_time, 2),
                "running": self.state == "running",
                "state": self.state,
                "pending": len(self.sim.scheduler.event_queue),
                "generated": stats["generated"],
                "received": stats["received"],
                "lost": stats["lost"],
            }

    def get_config(self):
        """返回当前生效的实验参数（供 GET /api/simulation/config）。"""
        with self._lock:
            return {
                "node_count": self.node_count,
                "area_size": self.area_size,
                "gateways": [list(g) for g in self.gateway_positions],
                "seed": self.seed,
                "duration": self.duration,
                "adr_enabled": self.adr_enabled,
            }

    def get_nodes(self):
        with self._lock:
            return [
                {
                    "id": n.node_id,
                    "sf": n.sf,
                    "rssi": n.last_rssi,
                    "snr": n.last_snr,
                    "gateway": n.selected_gateway,
                    "x": n.x,
                    "y": n.y,
                    "battery": n.battery,
                    "online": n.online,
                }
                for n in self.sim.nodes
            ]

    def get_gateways(self):
        with self._lock:
            result = []
            for gw in self.sim.gateways:
                s = gw.statistics()
                result.append({
                    "id": gw.id,
                    "received": s.get("received", 0),
                    "avg_rssi": s.get("avg_rssi"),
                    "x": gw.x,
                    "y": gw.y,
                })
            return result

    def get_statistics(self):
        with self._lock:
            stats = self.sim.statistics()
            generated = stats["generated"]
            received = stats["received"]
            pdr = (received / generated) if generated else 0.0
            return {
                "throughput": stats["throughput"],
                "pdr": pdr,
                "retransmissions": stats["retransmissions"],
            }

    def get_packets(self, limit=None):
        """事件级包历史（最近 limit 条，默认全部）。"""
        with self._lock:
            if limit is None:
                return list(self.history)
            if limit >= len(self.history):
                return list(self.history)
            # deque 不支持负切片，转 list 后取尾部
            return list(self.history)[-limit:]

    def get_history(self, bucket=1.0):
        """把包历史按时间桶聚合为实时链路曲线。

        bucket_pdr = received / (received + lost)；仅输出非空桶，按时间升序。
        """
        with self._lock:
            if bucket <= 0:
                bucket = 1.0
            buckets = {}
            for rec in self.history:
                key = round(int(rec["time"] // bucket) * bucket, 2)
                slot = buckets.setdefault(key, {"received": 0, "lost": 0})
                if rec["success"]:
                    slot["received"] += 1
                else:
                    slot["lost"] += 1
            timeline = []
            for t in sorted(buckets):
                r = buckets[t]["received"]
                l = buckets[t]["lost"]
                pdr = (r / (r + l)) if (r + l) > 0 else 1.0
                timeline.append({
                    "time": t,
                    "received": r,
                    "lost": l,
                    "pdr": round(pdr, 4),
                })
            return timeline

    def get_export(self):
        """组合导出（供离线分析 / 前端下载）。"""
        # 注意：这里调用各个 get_* 会分别拿一次 self._lock（RLock，没问题），
        # 但如果需要"全一致快照"，应该在一个 with self._lock 下做。
        # 当前 API 语义允许各字段有 0~N 事件的时间差，故不做更强约束。
        return {
            "status": self.get_status(),
            "nodes": self.get_nodes(),
            "gateways": self.get_gateways(),
            "statistics": self.get_statistics(),
            "packets": self.get_packets(),
            "history": self.get_history(),
        }


# 模块级单例：应用启动时构建并排程（就绪态，不自动运行）
engine = SimulationEngine()
