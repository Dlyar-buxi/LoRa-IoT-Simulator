# LoRa 智能农业 / 工业物联网网络仿真与监控平台

**LoRa-based Smart Agriculture & Industrial IoT Network Simulation and Monitoring Platform**

一个覆盖「嵌入式节点 → LoRa 无线 → 网关 → MQTT → 后端 → Web 可视化」的完整物联网仿真平台。
当前仓库为 **工程设计文档 V1.0** 对应的代码骨架，按 Sprint 逐步落地。

## 技术栈

- 语言：Python 3.12+
- 仿真层：纯标准库（Step 1 即可运行）
- 通信：自研 LoRa 信道 / MAC 模型（后续接真实 STM32 + SX127x）
- 云平台：FastAPI + SQLite + MQTT（Mosquitto / EMQX）
- 前端：HTML + JS（Leaflet 地图 + ECharts 曲线）

## 目录结构

```
LoRa-IoT-Simulator/
├── simulator/      # 节点、传感器、信道、MAC、能量模型（含 config）
├── gateway/        # LoRa 网关
├── network_server/ # 网络服务器 / 设备管理 / ADR
├── backend/        # FastAPI + MQTT + SQLite
├── frontend/       # Web 监控面板
├── analysis/       # 性能分析与可视化
├── requirements.txt
└── README.md
```

## 快速开始（Step 1）

```bash
cd LoRa-IoT-Simulator
python -m venv venv
source venv/Scripts/activate      # Windows: venv\Scripts\activate
python simulator/main.py
```

输出将创建 200 个虚拟节点，并打印前 5 个节点的位置、电量、SF 与传感数据。

## 开发路线

| Sprint | 内容 |
| ------ | ---- |
| 1 | 工程框架、SensorNode、Packet、基础仿真 |
| 2 | Channel：RSSI / SNR / 路径损耗 / 碰撞 |
| 3 | Gateway、MQTT、Network Server |
| 4 | FastAPI、SQLite、Web Dashboard |
| 5 | ADR、性能分析、可视化 |
| 6 | 多网关、能耗模型、Demo 视频与 README |

## 配置

所有仿真参数集中在 `simulator/config.py`（区域大小、节点数、LoRa 物理层、
能量模型、路径损耗模型、随机种子）。
