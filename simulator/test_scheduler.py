"""
Scheduler discrete-event simulation test
"""

from simulator.scheduler import Scheduler


def test_scheduler():
    executed = []

    def tx_callback(event):
        print(f"[{event.time}s]")
        print(f"{event.node_id} {event.action}")
        executed.append(event.node_id)

    sched = Scheduler()

    print("===== Scheduler Test =====")
    print()
    print("Initial time:")
    print(f"{sched.current_time:.1f}")
    print()
    print("Add events:")

    # 故意逆序加入，验证 heap 按时间排序
    sched.add_event(5.0, "Node001", "TRANSMIT", tx_callback)
    sched.add_event(2.0, "Node002", "TRANSMIT", tx_callback)
    print()
    print("Run simulation")
    print()
    sched.run()
    print()
    print("Final time:")
    print(f"{sched.current_time:.1f}")
    print()

    # 验证执行顺序：2.0s 的 Node002 必须先于 5.0s 的 Node001
    assert executed == ["Node002", "Node001"], (
        f"execution order wrong: {executed}"
    )
    assert abs(sched.current_time - 5.0) < 1e-9
    print("Scheduler PASS")


if __name__ == "__main__":
    test_scheduler()
