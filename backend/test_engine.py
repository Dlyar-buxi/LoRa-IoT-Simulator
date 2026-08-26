"""Engine 交互式生命周期自测（Sprint 4.4.2）。

验证：
    构建即就绪(不自动运行) -> start -> step 推进 current_time/received 增长
    -> 队列耗尽变 finished -> reset 回到 t=0/received=0/pending=200
    -> stop 保留状态 / pause 可恢复

运行：python -m backend.test_engine
"""

from backend.engine import SimulationEngine


def main():
    print("===== Interactive Engine Test =====")

    # 独立实例，避免扰动模块级单例 engine
    eng = SimulationEngine(duration=60.0, seed=42)

    # 1) 构建后不自动运行：pending=200, received=0, state=ready, time=0
    st = eng.get_status()
    assert st["pending"] == 200, f"pending should be 200, got {st['pending']}"
    assert st["received"] == 0, f"received should be 0, got {st['received']}"
    assert st["state"] == "ready", f"state should be ready, got {st['state']}"
    assert st["time"] == 0.0, f"time should be 0, got {st['time']}"
    print(
        f"[1] build (no auto-run): pending={st['pending']} "
        f"received={st['received']} state={st['state']} time={st['time']}"
    )

    # 2) start -> running（Pull 模型：仅切状态）
    eng.start()
    assert eng.get_status()["state"] == "running"
    print("[2] start -> running")

    # 3) step(10) 推进：current_time 前进、received 不降、精确执行 10 个事件
    before = eng.get_status()
    executed = eng.step(10)
    after = eng.get_status()
    assert executed == 10, f"step(10) should execute 10, got {executed}"
    assert after["time"] > before["time"], "time should advance after step"
    assert after["received"] >= before["received"], "received should not decrease"
    print(
        f"[3] step(10): executed={executed} time={after['time']} "
        f"received={after['received']} pending={after['pending']} "
        f"state={after['state']}"
    )

    # 4) 持续推进至结束 -> finished, pending=0, received=200
    total = 10
    while eng.get_status()["state"] != "finished":
        total += eng.step(50)
    fin = eng.get_status()
    assert fin["state"] == "finished", f"state should be finished, got {fin['state']}"
    assert fin["pending"] == 0, f"pending should be 0, got {fin['pending']}"
    assert fin["received"] == 200, f"received should be 200, got {fin['received']}"
    print(
        f"[4] drain: total_events={total} received={fin['received']} "
        f"pending={fin['pending']} state={fin['state']}"
    )

    # 5) reset 回到初始：ready / received=0 / pending=200 / time=0
    eng.reset()
    rs = eng.get_status()
    assert rs["state"] == "ready", f"state should be ready, got {rs['state']}"
    assert rs["received"] == 0, f"received should be 0, got {rs['received']}"
    assert rs["pending"] == 200, f"pending should be 200, got {rs['pending']}"
    assert rs["time"] == 0.0, f"time should be 0, got {rs['time']}"
    print(
        f"[5] reset: state={rs['state']} received={rs['received']} "
        f"pending={rs['pending']} time={rs['time']}"
    )

    # 6) pause / resume 语义
    eng.start()
    assert eng.get_status()["state"] == "running"
    eng.pause()
    assert eng.get_status()["state"] == "paused"
    eng.start()  # resume
    assert eng.get_status()["state"] == "running"
    print("[6] lifecycle: ready -> running -> paused -> running OK")

    # 7) stop 保留状态（不重置）—— 验证 stop 前的值被原样保留
    before_stop = eng.get_status()["received"]
    eng.stop()
    stp = eng.get_status()
    assert stp["state"] == "finished", f"state should be finished, got {stp['state']}"
    assert stp["received"] == before_stop, (
        f"stop should preserve received, got {stp['received']} (before={before_stop})"
    )
    print(f"[7] stop: state={stp['state']} (received preserved={stp['received']})")

    print("Interactive Engine Test PASS")


if __name__ == "__main__":
    main()
