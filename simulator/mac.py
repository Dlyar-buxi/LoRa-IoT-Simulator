"""
LoRa MAC State Machine

Sprint 3.1.1: 状态管理 / 发送流程 / 成功确认 / 失败重试
Sprint 4.1:    随机退避（WAIT_BACKOFF）/ 配置驱动 MAX_RETRY

状态机（双路径兼容）：
  IDLE --start_transmission--> TRANSMITTING
  TRANSMITTING --handle_success--> IDLE
  TRANSMITTING --handle_failure--> RETRY            (retry_count <= MAX_RETRY)
  TRANSMITTING --handle_failure--> IDLE            (超次丢弃，retry_count 复位)
  RETRY --start_backoff--> WAIT_BACKOFF
  WAIT_BACKOFF --retry_transmission--> TRANSMITTING
  RETRY --retry_transmission--> TRANSMITTING        (兼容 Sprint 3 旧测试)
"""


from enum import Enum, auto

from simulator import config



class MacState(Enum):

    IDLE = auto()

    TRANSMITTING = auto()

    WAIT_ACK = auto()

    RETRY = auto()

    WAIT_BACKOFF = auto()



class LoRaMAC:


    def __init__(self, node):

        self.node = node

        self.state = MacState.IDLE

        self.retry_count = 0

        self.max_retry = config.MAX_RETRY

        self.current_packet = None



    def generate_packet(self):

        """
        从节点生成数据包
        """

        self.current_packet = (

            self.node.create_packet()

        )


        return self.current_packet



    def start_transmission(self):

        """
        开始发送
        """


        if self.current_packet is None:

            self.generate_packet()



        self.state = MacState.TRANSMITTING


        return self.current_packet



    def wait_ack(self):

        """
        等待ACK
        """


        if self.state == MacState.TRANSMITTING:

            self.state = MacState.WAIT_ACK



    def handle_success(self):

        """
        发送成功：复位状态机，retry_count 清零（协议状态保持干净）
        """


        self.retry_count = 0


        self.state = MacState.IDLE



    def handle_failure(self):

        """
        发送失败：retry_count 自增，
        未超上限进入 RETRY，超上限丢弃并复位。
        """


        self.retry_count += 1



        if self.retry_count <= self.max_retry:

            self.state = MacState.RETRY


        else:

            self.retry_count = 0

            self.state = MacState.IDLE



    def start_backoff(self):

        """
        进入随机退避等待：RETRY -> WAIT_BACKOFF。
        """


        if self.state == MacState.RETRY:

            self.state = MacState.WAIT_BACKOFF



    def retry_transmission(self):

        """
        重传：RETRY 或 WAIT_BACKOFF 都进入发送态。
        兼容 Sprint 3 旧测试（RETRY -> TRANSMITTING），
        同时支持 Sprint 4.1 新流程（WAIT_BACKOFF -> TRANSMITTING）。
        """


        if self.state in (MacState.RETRY, MacState.WAIT_BACKOFF):

            self.state = MacState.TRANSMITTING
