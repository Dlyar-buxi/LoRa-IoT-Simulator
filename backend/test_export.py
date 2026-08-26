"""数据输出层自测（Sprint 4.4.3）。

验证：
    step 至结束后 history 记录数 > 200；
    get_packets / get_history / get_export 字段齐全且自洽；
    reset 清空 history。
不修改任何 simulator/ 冻结模块。

运行：python -m backend.test_export
"""

from backend.engine import SimulationEngine


def main():
    print("===== Export Test =====")

    # 独立实例，避免扰动模块级单例 engine
    eng = SimulationEngine(duration=60.0, seed=42)
    eng.start()
    while eng.get_status()["state"] != "finished":
        eng.step(50)

    # 1) History records
    n_hist = len(eng.get_packets())
    print(f"\nHistory records:\n{n_hist}")
    assert n_hist > 200, f"history should be >200, got {n_hist}"

    # 2) Packet export
    packets = eng.get_packets()
    ok_packet = all(
        {"time", "event", "node", "sf", "rssi", "snr", "gateway", "success"} <= set(p)
        for p in packets
    )
    print("Packet export:")
    print("PASS" if ok_packet else "FAIL")
    assert ok_packet, "packet records missing fields"

    # 3) Timeline（桶聚合自洽：桶内 received+lost 总和 == history 条数）
    timeline = eng.get_history(bucket=1.0)
    total_in_buckets = sum(t["received"] + t["lost"] for t in timeline)
    assert total_in_buckets == n_hist, (
        f"timeline total {total_in_buckets} != history {n_hist}"
    )
    ok_timeline = all(
        "pdr" in t and t["received"] >= 0 and t["lost"] >= 0 for t in timeline
    )
    print("Timeline:")
    print("PASS" if ok_timeline else "FAIL")
    assert ok_timeline, "timeline malformed"

    # 关键自洽：history 中 success 数 == 状态里的 received（get_statistics 不含 received 键）
    success_count = sum(1 for p in packets if p["success"])
    assert success_count == eng.get_status()["received"], (
        f"success in history {success_count} != received {eng.get_status()['received']}"
    )

    # 4) JSON export
    export = eng.get_export()
    ok_export = {
        "status",
        "nodes",
        "gateways",
        "statistics",
        "packets",
        "history",
    } <= set(export)
    print("JSON export:")
    print("PASS" if ok_export else "FAIL")
    assert ok_export, "export missing keys"

    # bucket=5 聚合趋势
    tl5 = eng.get_history(bucket=5.0)
    print(f"\nTimeline (bucket=5) buckets: {len(tl5)}")
    assert len(tl5) <= len(timeline), "coarser bucket should not yield more buckets"

    # 5) Reset clears history
    eng.reset()
    assert len(eng.get_packets()) == 0, "history should be cleared after reset"
    print("Reset:")
    print("history cleared")

    print("\nExport Test PASS")


if __name__ == "__main__":
    main()
