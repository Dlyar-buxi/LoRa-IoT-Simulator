"""SQLite 实验记录器（Sprint 5.2，Experiment Recorder）。

定位：**实验记录器（Experiment Recorder）**，不是 Simulation Core 的状态存储。
仿真核心（simulator/ gateway/）与 engine.py 完全不知道 SQLite 的存在——
本模块只经由 main.py 的 telemetry_sink（与 MQTT / WebSocket 同级的 Adapter 出口）
被动接收每条遥测记录，并落盘为「一次实验 = experiments 一行 + events 多行」。

设计纪律（与 v4.4 / v5.1 一致）：
- 不反向污染 engine：本模块不 import engine / simulator / gateway，零依赖仿真代码。
- 不成为仿真依赖：DB 不可用 / 写入异常时静默降级（与 MQTT 同策略），绝不冒泡到
  engine.step()（后者已用 try/except 包裹 sink 调用）。
- 可配置：env DB_PATH（默认 experiments.db）、DB_ENABLED（默认 true）。
- 标准库实现：仅用 sqlite3 / os / json / threading / logging / datetime，无新增依赖。

加固（v1.2 hardening P0-3）：
- WAL journal_mode：连接时执行 PRAGMA journal_mode=WAL，显著提升读-写并发吞吐
  （旧 DELETE 模式下每次 commit 都要刷全 DB 页回磁盘，WAL 仅追加 write-ahead log）。
- 批量写入 record_event：把 events INSERT 缓存在 `_pending_events` 队列里，
  满足 COUNT >= DB_BATCH_FLUSH_COUNT（默认 100）或距离上次 flush 超过
  DB_BATCH_FLUSH_SECONDS（默认 1.0）时用 executemany 一次性提交。
  这样 800 条 events 从 800 次 commit ≈ 800ms 降到 8 次 commit ≈ 几 ms。
- flush() 在 finalize / close / begin_experiment（切新实验）前显式调用，
  保证进程退出或实验切换时不丢 pending 行。

生命周期（由 main.py 在 Adapter 层驱动，不修改 engine.py）：
- begin_experiment(meta)  -> 新建 experiments 行，置为 active
- record_event(record)    -> 向 active 实验追加 events 行（无 active 时自动 lazy 建）
- finalize_experiment(...) -> 回填终态 JSON（统计 / 节点 / 网关），关闭 active
- 查询：list_experiments / get_experiment / get_experiment_events
"""

import json
import logging
import os
import sqlite3
import threading
import time as _time_mod
from datetime import datetime

logger = logging.getLogger("lora.db")


def _now_iso():
    return datetime.now().isoformat(timespec="seconds")


def _to_json(obj):
    if obj is None:
        return None
    return json.dumps(obj, ensure_ascii=False)


def _from_json(text):
    if text is None:
        return None
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


# ---------- 批量写入默认参数（env 可覆盖）----------
try:
    _raw = os.getenv("DB_BATCH_FLUSH_COUNT", "100")
    _BATCH_COUNT = max(1, int(_raw)) if _raw else 100
except (TypeError, ValueError):
    _BATCH_COUNT = 100

try:
    _raw = os.getenv("DB_BATCH_FLUSH_SECONDS", "1.0")
    _BATCH_SECONDS = max(0.05, float(_raw)) if _raw else 1.0
except (TypeError, ValueError):
    _BATCH_SECONDS = 1.0


class ExperimentRecorder:
    """把 telemetry 流落盘为可回放 / 可对比的实验记录。

    线程安全：engine.step() 经 sink 从 FastAPI 线程池调用，故所有写操作加锁。
    """

    def __init__(self, db_path=None, enabled=None):
        # env 覆盖：DB_ENABLED 默认 true；DB_PATH 默认 experiments.db（项目根）
        if enabled is None:
            enabled = os.getenv("DB_ENABLED", "true").lower() in (
                "1", "true", "yes", "on",
            )
        if db_path is None:
            db_path = os.getenv("DB_PATH", "experiments.db")

        self.enabled = enabled
        self.db_path = db_path
        self._conn = None
        self._active_id = None
        self._seq = 0
        self._last_time = None
        self._lock = threading.Lock()
        # 终态采集回调（由 main.py 注册：拉 engine 当前状态），解耦仿真代码
        self._finalizer = None
        # P0-3: 批量写入
        self._batch_count = _BATCH_COUNT
        self._batch_seconds = _BATCH_SECONDS
        self._pending_events = []  # list[tuple]：executemany 的参数队列
        self._last_flush = 0.0     # monotonic time 秒，用于时间阈值判定

    # ---------- 连接 / 降级 ----------

    def connect(self):
        """打开连接并建表。失败则静默降级（enabled=False），不阻断应用。

        P0-3: 连接成功后显式开启 WAL journal_mode（executemany 批量写入 +
        后台 checkpointer，吞吐提升一个数量级）。WAL 开启失败不降级。
        """
        if not self.enabled:
            return False
        try:
            self._conn = sqlite3.connect(
                self.db_path, check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            # P0-3: 开启 WAL（失败仅记日志，不影响功能，退回 DELETE 模式）
            try:
                cur = self._conn.execute("PRAGMA journal_mode=WAL")
                mode = (cur.fetchone() or [None])[0]
                if mode and str(mode).lower() != "wal":
                    logger.warning(
                        "SQLite journal_mode 未切换到 WAL（当前=%s），写入将较慢", mode
                    )
            except Exception as w:  # noqa: BLE001
                logger.warning("SQLite PRAGMA WAL 失败（不影响功能）：%s", w)
            self.ensure_schema()
            self._last_flush = _time_mod.monotonic()
            logger.info("SQLite Recorder 已连接：%s", self.db_path)
            return True
        except Exception as e:  # noqa: BLE001 - 任何异常都降级
            logger.warning("SQLite 初始化失败，录制已禁用：%s", e)
            self._conn = None
            self.enabled = False
            return False

    # ---------- 批量 flush（P0-3）----------

    def flush(self):
        """把 pending_events 队列 executemany 一次性提交并 commit。

        任何异常静默降级（返回 False）；成功（含队列为空）返回 True。
        调用方负责拿 self._lock；内部不重复加锁以避免死锁。
        """
        if not self._pending_events:
            self._last_flush = _time_mod.monotonic()
            return True
        if self._conn is None:
            self._pending_events.clear()
            return False
        try:
            self._conn.executemany(
                """
                INSERT INTO events
                    (experiment_id, seq, time, event, node, sf,
                     rssi, snr, gateway, success)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._pending_events,
            )
            self._conn.commit()
            self._pending_events.clear()
            self._last_flush = _time_mod.monotonic()
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning("flush 失败，丢弃 %d 条 pending events：%s",
                           len(self._pending_events), e)
            # 出错就清队列，避免下次再次爆炸
            self._pending_events.clear()
            self._last_flush = _time_mod.monotonic()
            return False

    def close(self):
        with self._lock:
            # P0-3: 关库前强制 flush pending events，避免丢失尾部数据
            if self._conn is not None:
                try:
                    self.flush()
                except Exception:  # noqa: BLE001
                    pass
                try:
                    self._conn.close()
                except Exception:  # noqa: BLE001
                    pass
                self._conn = None

    def ensure_schema(self):
        if self._conn is None:
            return
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                seed                INTEGER,
                node_count          INTEGER,
                duration            REAL,
                area_size           REAL,
                gateway_cfg         TEXT,
                adr_enabled         INTEGER,
                created_at          TEXT,
                finalized           INTEGER DEFAULT 0,
                final_statistics_json TEXT,
                nodes_json          TEXT,
                gateways_json       TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                seq           INTEGER,
                time          REAL,
                event         TEXT,
                node          TEXT,
                sf            INTEGER,
                rssi          REAL,
                snr           REAL,
                gateway       TEXT,
                success       INTEGER,
                FOREIGN KEY (experiment_id) REFERENCES experiments(id)
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_exp ON events(experiment_id)"
        )
        self._conn.commit()

    # ---------- 实验生命周期 ----------

    def set_finalizer(self, fn):
        """注册终态采集回调 fn() -> dict{statistics, nodes, gateways}。

        main.py 在 Adapter 层把 engine 的当前状态喂给 Recorder，避免本模块
        反向依赖仿真代码。
        """
        self._finalizer = fn

    def begin_experiment(self, meta=None):
        """新建一条 experiments 记录并置为 active。

        若已有 active 实验，先 best-effort finalize（支持 reset -> 新实验，
        不覆盖旧实验）。返回新 experiment id；降级或失败时返回 None。

        P0-3: 在 finalize 旧实验 + 建新实验前先 flush pending events
        （切实验时 pending_events 里的行都属于旧 experiment_id，不能留到
        新实验；此时不 flush 就会把旧实验数据混进新实验的 executemany）。
        """
        if not self.enabled or self._conn is None:
            return None
        meta = meta or {}
        with self._lock:
            # P0-3: 先把旧实验的 pending events 落盘，再 finalize+建新实验
            self.flush()
            # 关闭尚未 finalize 的旧实验（reset 场景）
            if self._active_id is not None:
                self._finalize_active()
            try:
                cur = self._conn.execute(
                    """
                    INSERT INTO experiments
                        (seed, node_count, duration, area_size,
                         gateway_cfg, adr_enabled, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        meta.get("seed"),
                        meta.get("node_count"),
                        meta.get("duration"),
                        meta.get("area_size"),
                        _to_json(meta.get("gateway_cfg")),
                        1 if meta.get("adr_enabled") else 0,
                        _now_iso(),
                    ),
                )
                self._conn.commit()
                self._active_id = cur.lastrowid
                self._seq = 0
                self._last_time = None
                return self._active_id
            except Exception as e:  # noqa: BLE001
                logger.warning("begin_experiment 失败：%s", e)
                return None

    def record_event(self, record):
        """向 active 实验追加一条 events 记录（批量写入版）。

        - 无 active 实验时 lazy 自动建（保证仿真流不被打断）。
        - P0-3: 单行不直接 commit，而是 append 到 pending_events；
          满足「队列长度 >= batch_count」或「距离上次 flush >= batch_seconds」
          时统一用 executemany 批量提交。
        - 任何异常静默降级返回 False，绝不冒泡。
        """
        if not self.enabled or self._conn is None:
            return False
        with self._lock:
            if self._active_id is None:
                if not self._ensure_active():
                    return False
            try:
                success = record.get("success")
                self._pending_events.append((
                    self._active_id,
                    self._seq,
                    record.get("time"),
                    record.get("event"),
                    record.get("node"),
                    record.get("sf"),
                    record.get("rssi"),
                    record.get("snr"),
                    record.get("gateway"),
                    1 if success is True else (0 if success is False else None),
                ))
                self._seq += 1
                self._last_time = record.get("time")
                # 批量触发条件：COUNT 或 TIME 任一满足
                now = _time_mod.monotonic()
                if (
                    len(self._pending_events) >= self._batch_count
                    or (now - self._last_flush) >= self._batch_seconds
                ):
                    self.flush()
                return True
            except Exception as e:  # noqa: BLE001
                logger.warning("record_event 失败（静默降级）：%s", e)
                return False

    def finalize_experiment(self, final_stats=None, nodes=None, gateways=None):
        """回填当前 active 实验的终态 JSON 并关闭它。"""
        if not self.enabled or self._conn is None or self._active_id is None:
            return False
        with self._lock:
            return self._write_finalize(final_stats, nodes, gateways)

    def _finalize_active(self):
        """用注册的 finalizer 采集终态后回填（不抛异常）。"""
        final_stats = nodes = gateways = None
        if self._finalizer is not None:
            try:
                payload = self._finalizer() or {}
                final_stats = payload.get("statistics")
                nodes = payload.get("nodes")
                gateways = payload.get("gateways")
            except Exception:  # noqa: BLE001
                pass
        return self._write_finalize(final_stats, nodes, gateways)

    def _write_finalize(self, final_stats, nodes, gateways):
        """写终态 JSON + 关闭 active。

        P0-3: UPDATE 前必须 flush pending events，保证 events 行落盘后再
        把实验标记为 finalized（否则用户打开 finalized=1 的实验详情
        会发现 events 行数比实际少了 pending 里的那些）。
        """
        if self._active_id is None:
            return False
        try:
            # P0-3: 先 events 落盘，再标记 finalized
            self.flush()
            self._conn.execute(
                """
                UPDATE experiments
                SET finalized = 1,
                    final_statistics_json = ?,
                    nodes_json = ?,
                    gateways_json = ?
                WHERE id = ?
                """,
                (_to_json(final_stats), _to_json(nodes), _to_json(gateways),
                 self._active_id),
            )
            self._conn.commit()
            self._active_id = None
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning("finalize_experiment 失败：%s", e)
            return False

    def _ensure_active(self):
        if self._active_id is not None:
            return True
        if not self.enabled or self._conn is None:
            return False
        self._active_id = self.begin_experiment({})
        return self._active_id is not None

    # ---------- 查询 API（供 /api/experiments 端点）----------

    def list_experiments(self):
        """返回实验列表（最新在前），不含 events 明细。降级时返回空列表。"""
        if not self.enabled or self._conn is None:
            return []
        try:
            rows = self._conn.execute(
                """
                SELECT id, seed, node_count, duration, area_size,
                       adr_enabled, created_at, finalized
                FROM experiments ORDER BY id DESC
                """
            ).fetchall()
            return [_experiment_summary(r) for r in rows]
        except Exception as e:  # noqa: BLE001
            logger.warning("list_experiments 失败：%s", e)
            return []

    def get_experiment(self, exp_id):
        """返回单条实验元信息（含终态 JSON 反序列化）；不存在返回 None。"""
        if not self.enabled or self._conn is None:
            return None
        try:
            row = self._conn.execute(
                """
                SELECT id, seed, node_count, duration, area_size,
                       gateway_cfg, adr_enabled, created_at, finalized,
                       final_statistics_json, nodes_json, gateways_json
                FROM experiments WHERE id = ?
                """,
                (exp_id,),
            ).fetchone()
            if row is None:
                return None
            return _experiment_detail(row)
        except Exception as e:  # noqa: BLE001
            logger.warning("get_experiment 失败：%s", e)
            return None

    def get_experiment_events(self, exp_id, limit=None):
        """返回某实验的 events（按 seq 升序）；limit 取最近 N 条。降级/不存在返回空。"""
        if not self.enabled or self._conn is None:
            return []
        try:
            if limit is not None:
                rows = self._conn.execute(
                    """
                    SELECT * FROM (
                        SELECT id, seq, time, event, node, sf, rssi, snr,
                               gateway, success
                        FROM events WHERE experiment_id = ?
                        ORDER BY seq DESC LIMIT ?
                    ) ORDER BY seq ASC
                    """,
                    (exp_id, int(limit)),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """
                    SELECT id, seq, time, event, node, sf, rssi, snr,
                           gateway, success
                    FROM events WHERE experiment_id = ? ORDER BY seq ASC
                    """,
                    (exp_id,),
                ).fetchall()
            return [_event_row(r) for r in rows]
        except Exception as e:  # noqa: BLE001
            logger.warning("get_experiment_events 失败：%s", e)
            return []


# ---------- 行 -> dict 转换 ----------

def _experiment_summary(row):
    return {
        "id": row["id"],
        "seed": row["seed"],
        "node_count": row["node_count"],
        "duration": row["duration"],
        "area_size": row["area_size"],
        "adr_enabled": bool(row["adr_enabled"]),
        "created_at": row["created_at"],
        "finalized": bool(row["finalized"]),
    }


def _experiment_detail(row):
    return {
        "id": row["id"],
        "seed": row["seed"],
        "node_count": row["node_count"],
        "duration": row["duration"],
        "area_size": row["area_size"],
        "gateway_cfg": _from_json(row["gateway_cfg"]),
        "adr_enabled": bool(row["adr_enabled"]),
        "created_at": row["created_at"],
        "finalized": bool(row["finalized"]),
        "statistics": _from_json(row["final_statistics_json"]),
        "nodes": _from_json(row["nodes_json"]),
        "gateways": _from_json(row["gateways_json"]),
    }


def _event_row(row):
    success = row["success"]
    return {
        "id": row["id"],
        "seq": row["seq"],
        "time": row["time"],
        "event": row["event"],
        "node": row["node"],
        "sf": row["sf"],
        "rssi": row["rssi"],
        "snr": row["snr"],
        "gateway": row["gateway"],
        "success": None if success is None else bool(success),
    }


# 模块级单例：main.py 在 lifespan 中 connect()，其余经此单例访问。
recorder = ExperimentRecorder()
