"""传感器模型。

每个传感器基于一个基准值 + 高斯噪声生成读数，
并做合理的物理范围截断（如湿度 0~100%）。
后续 Sprint 可加入时间周期（昼夜光照）与空间相关性。
"""


class Sensor:
    """传感器基类。"""

    name = "sensor"

    def __init__(self, rng, base, noise):
        self.rng = rng          # random.Random 实例
        self.base = base        # 基准读数
        self.noise = noise      # 标准差

    def read(self):
        return round(self.base + self.rng.gauss(0, self.noise), 2)


class TemperatureSensor(Sensor):
    name = "temperature"

    def read(self):
        v = self.base + self.rng.gauss(0, self.noise)
        return round(max(-20.0, min(60.0, v)), 2)   # ℃


class HumiditySensor(Sensor):
    name = "humidity"

    def read(self):
        v = self.base + self.rng.gauss(0, self.noise)
        return round(max(0.0, min(100.0, v)), 2)    # %


class SoilSensor(Sensor):
    name = "soil"

    def read(self):
        v = self.base + self.rng.gauss(0, self.noise)
        return round(max(0.0, min(100.0, v)), 2)    # %


class LightSensor(Sensor):
    name = "light"

    def read(self):
        v = self.base + self.rng.gauss(0, self.noise)
        return round(max(0.0, v), 2)                # lux


class CO2Sensor(Sensor):
    name = "co2"

    def read(self):
        v = self.base + self.rng.gauss(0, self.noise)
        return round(max(300.0, v), 2)              # ppm
