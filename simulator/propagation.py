"""
LoRa propagation model

实现：
- Distance calculation
- Log-distance path loss
- Shadow fading

单位：
distance : meter
frequency: Hz
power    : dBm
"""


import math
import random


class PropagationModel:


    def __init__(
            self,
            frequency=868e6,
            path_loss_exponent=3.0,
            shadow_std=4.0):


        """
        frequency:
            LoRa EU868 默认频率


        path_loss_exponent:

            2.0  空旷自由空间

            2.7~3.5 农业/郊区

            3.0 当前模型


        shadow_std:

            阴影衰落标准差 dB

        """


        self.frequency = frequency

        self.n = path_loss_exponent

        self.shadow_std = shadow_std



    def calculate_distance(
            self,
            x1,
            y1,
            x2,
            y2):


        """
        二维距离

        单位:
        meter
        """


        distance = math.sqrt(

            (x1-x2)**2 +

            (y1-y2)**2

        )


        return distance



    def calculate_reference_loss(
            self,
            d0=1):


        """
        计算1米参考损耗

        Friis公式
        """


        c = 3e8


        wavelength = (
            c /
            self.frequency
        )


        loss = (

            20 *
            math.log10(

                4 *
                math.pi *
                d0 /
                wavelength

            )

        )


        return loss



    def calculate_path_loss(
            self,
            distance):


        """
        Log Distance Model


        PL(d)=PL(d0)+10*n*log(d/d0)

        """


        if distance < 1:

            distance = 1



        pl0 = self.calculate_reference_loss()



        path_loss = (

            pl0 +

            10 *
            self.n *
            math.log10(distance)

        )



        shadow = random.gauss(

            0,

            self.shadow_std

        )


        return path_loss + shadow
