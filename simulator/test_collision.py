"""
Collision detection test

使用最小 Dummy Packet，不依赖 node.py / channel.py / gateway.py，保证测试独立。
"""


from simulator.collision import CollisionDetector



class DummyPacket:


    def __init__(

            self,

            frequency,

            sf,

            tx_start,

            tx_end,

            rssi):


        self.frequency = frequency

        self.sf = sf

        self.tx_start_time = tx_start

        self.tx_end_time = tx_end

        self.rssi = rssi



detector = CollisionDetector()



print("===== Collision Test =====")

print()



# Case 1: 同频 + 同SF + 时间重叠 + RSSI 差 3dB (<6) -> 冲突

p1 = DummyPacket(868e6, 7, 10.0, 11.0, -100.0)

p2 = DummyPacket(868e6, 7, 10.5, 11.5, -103.0)

r1 = detector.check_collision(p1, p2)

print("Case1:")

print(f"Collision={r1}")

assert r1 is True



# Case 2: 时间不重叠 -> 无冲突

p3 = DummyPacket(868e6, 7, 10.0, 11.0, -100.0)

p4 = DummyPacket(868e6, 7, 12.0, 13.0, -103.0)

r2 = detector.check_collision(p3, p4)

print("Case2:")

print(f"Collision={r2}")

assert r2 is False



# Case 3: RSSI 差 20dB (>6) -> 强信号捕获弱信号 -> 无冲突

p5 = DummyPacket(868e6, 7, 10.0, 11.0, -90.0)

p6 = DummyPacket(868e6, 7, 10.5, 11.5, -110.0)

r3 = detector.check_collision(p5, p6)

print("Case3:")

print(f"Collision={r3}")

assert r3 is False



# Case 4: 不同 SF -> 可同时解调 -> 无冲突

p7 = DummyPacket(868e6, 7, 10.0, 11.0, -100.0)

p8 = DummyPacket(868e6, 12, 10.5, 11.5, -103.0)

r4 = detector.check_collision(p7, p8)

print("Case4:")

print(f"Collision={r4}")

assert r4 is False



print()

print("Collision Detector PASS")
