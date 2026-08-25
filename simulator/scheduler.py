"""
LoRa Simulation Scheduler

Sprint 3.2

离散事件仿真(DES)调度器：
- 维护仿真时钟 current_time（秒）
- 事件优先队列(heapq)，按 (time, event_id) 排序
- run() 跳转到下一个事件时间并执行回调

职责边界：
- 只管"什么时候发生什么"
- 不管 PHY / RSSI / 碰撞 / Gateway 接收
  （那些属于 channel.py / gateway.py / collision.py）
"""

import heapq
from dataclasses import dataclass, field
from typing import Callable


@dataclass(order=True)
class Event:
    """离散事件。

    排序关键字：time -> event_id（event_id 自增保证同时间事件稳定有序）。
    callback 不参与比较（函数不可排序），故标记 compare=False。
    """

    time: float
    event_id: int
    node_id: str = ""
    action: str = ""
    callback: Callable = field(compare=False, default=None)


class Scheduler:
    """仿真时钟 + 事件优先队列。"""

    def __init__(self):
        self.current_time = 0.0
        self.event_queue = []
        self.event_counter = 0

    def add_event(self, time, node_id, action, callback):
        """登记一个未来事件，插入优先队列（heapq.heappush 维持堆结构）。"""
        self.event_counter += 1
        event = Event(
            time=float(time),
            event_id=self.event_counter,
            node_id=node_id,
            action=action,
            callback=callback,
        )
        heapq.heappush(self.event_queue, event)
        return event

    def run(self):
        """离散事件主循环：按时间顺序弹出并执行事件回调。"""
        while self.event_queue:
            event = heapq.heappop(self.event_queue)
            self.current_time = event.time
            if event.callback is not None:
                event.callback(event)

    def pending(self):
        """剩余未执行事件数（便于测试/调试）。"""
        return len(self.event_queue)
