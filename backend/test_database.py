"""SQLite 实验记录器 hermetic 验收（Sprint 5.2）。

不依赖真实 experiments.db：每个用例用 tempfile 落盘，结束即删。
覆盖：建实验 / 逐事件写入 / 终态回填 / 查询 / reset 不覆盖旧实验 / 降级安全 / 缺失返回空。

运行：python -m backend.test_database
"""

import os
import sys
import tempfile

from backend.database import ExperimentRecorder


def _new_recorder():
    """返回 (recorder, tmp_path)；调用方负责 close + remove。"""
    tmp = tempfile.mktemp(suffix=".db")
    r = ExperimentRecorder(db_path=tmp, enabled=True)
    r.connect()
    return r, tmp


def _sample_events(n=3):
    return [
        {
            "time": float(i),
            "event": "TRANSMIT",
            "node": f"Node{i + 1:03}",
            "sf": 7,
            "rssi": -100.0 + i,
            "snr": 15.0 - i,
            "gateway": "GW001" if i % 2 == 0 else "GW002",
            "success": (i % 2 == 0),
        }
        for i in range(n)
    ]


def test_create_and_query():
    r, tmp = _new_recorder()
    try:
        eid = r.begin_experiment(
            {
                "seed": 42,
                "node_count": 200,
                "duration": 60.0,
                "area_size": 2000,
                "adr_enabled": True,
                "gateway_cfg": [("GW001", 500, 500), ("GW002", 1500, 1500)],
            }
        )
        assert eid is not None, "begin_experiment 返回 None"
        for rec in _sample_events(3):
            assert r.record_event(rec) is True, "record_event 失败"

        r.finalize_experiment(
            final_stats={"throughput": 3.33, "pdr": 1.0, "retransmissions": 1},
            nodes=[{"id": "Node001", "sf": 7}],
            gateways=[{"id": "GW001", "received": 2}],
        )

        lst = r.list_experiments()
        assert len(lst) == 1, f"list 期望 1 条，实际 {len(lst)}"
        assert lst[0]["id"] == eid

        det = r.get_experiment(eid)
        assert det is not None
        assert det["statistics"] == {
            "throughput": 3.33,
            "pdr": 1.0,
            "retransmissions": 1,
        }
        assert det["finalized"] is True
        assert len(det["nodes"]) == 1
        assert det["gateway_cfg"] == [["GW001", 500, 500], ["GW002", 1500, 1500]]

        evs = r.get_experiment_events(eid)
        assert len(evs) == 3, f"events 期望 3 条，实际 {len(evs)}"
        assert evs[0]["success"] is True
        assert evs[1]["success"] is False
        assert evs[2]["success"] is True

        # limit 取最近 N 条（按 seq 升序返回）
        evs_lim = r.get_experiment_events(eid, limit=1)
        assert len(evs_lim) == 1 and evs_lim[0]["seq"] == 2
    finally:
        r.close()
        os.remove(tmp)


def test_reset_new_experiment():
    """reset -> 新实验上下文，旧实验不被覆盖。"""
    r, tmp = _new_recorder()
    try:
        e1 = r.begin_experiment({"seed": 1})
        r.record_event(
            {"time": 0.0, "event": "TRANSMIT", "node": "A", "sf": 7, "success": True}
        )
        e2 = r.begin_experiment({"seed": 1})  # 模拟 reset：先收旧再开新
        assert e2 != e1, "reset 未创建新实验"
        r.record_event(
            {"time": 0.0, "event": "TRANSMIT", "node": "B", "sf": 7, "success": True}
        )
        r.finalize_experiment()

        evs1 = r.get_experiment_events(e1)
        assert len(evs1) == 1 and evs1[0]["node"] == "A", "旧实验被覆盖"
        lst = r.list_experiments()
        assert len(lst) == 2, f"期望 2 个实验，实际 {len(lst)}"
    finally:
        r.close()
        os.remove(tmp)


def test_degrade_disabled():
    """DB_ENABLED=false 时全部操作静默降级，绝不抛异常。"""
    r = ExperimentRecorder(db_path=":memory:", enabled=False)
    assert r.record_event({"time": 0, "event": "X", "node": "A"}) is False
    assert r.list_experiments() == []
    assert r.get_experiment(1) is None
    assert r.get_experiment_events(1) == []


def test_missing():
    r, tmp = _new_recorder()
    try:
        assert r.get_experiment(999) is None
        assert r.get_experiment_events(999) == []
    finally:
        r.close()
        os.remove(tmp)


if __name__ == "__main__":
    tests = [
        test_create_and_query,
        test_reset_new_experiment,
        test_degrade_disabled,
        test_missing,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS backend.test_database :: {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL backend.test_database :: {t.__name__} -- {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR backend.test_database :: {t.__name__} -- {e}")
    if failed:
        print(f"REGRESSION FAIL={failed}")
        sys.exit(1)
    print("REGRESSION PASS (database)")
