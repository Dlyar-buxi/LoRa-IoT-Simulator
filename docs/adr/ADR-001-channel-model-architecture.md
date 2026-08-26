# ADR-001: Channel Model Architecture

Status: Accepted

Date: 2026-08-26


## 1. Context

当前 Simulator 已具备：

- Node
- Packet
- MAC
- Propagation
- Gateway
- ADR

但是 Physical Layer 建模仍然耦合在传播逻辑中。


问题：

现有模型只能回答：

"信号传播了多远？"


未来系统需要回答：

"为什么这个链路质量变化？"

包括：

- path loss
- fading
- interference
- environment
- mobility
- channel dynamics


因此引入独立 Channel Model Layer。


---

## 2. Decision

新增：

ChannelModel abstraction


位置：

Node
 ↓
Packet Generation
 ↓
Channel Model
 ↓
Propagation
 ↓
Gateway Receiver
 ↓
ADR / Controller


Channel Model 输出：

- RSSI
- SNR
- PDR
- Link Quality


Channel Model 不负责：

- MAC scheduling
- collision handling
- routing
- ADR decision


---

## 3. Why this position

Channel 属于 Physical Layer。


不放 Node：

因为 Node 不应该知道环境。


不放 Gateway：

因为 Gateway 不应该决定信号如何产生。


不放 MAC：

因为 MAC 只处理访问控制。


因此 Channel 是：

between transmission intent and reception result


---

## 4. Future Extension

接口支持：

```

ChannelModel

├── LogDistanceChannel
├── ShadowingChannel
├── RayleighChannel
├── UrbanChannel
├── IndoorChannel
├── AIChannelModel

```

未来 AI 模型作为实现：

而不是修改 Simulator Core。


---

## 5. Non-goals

本阶段：

不实现：

- ML training
- reinforcement learning
- real-world calibration
- autonomous optimization


目标：

冻结架构接口。
