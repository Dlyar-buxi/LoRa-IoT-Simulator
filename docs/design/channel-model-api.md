# Channel Model API — Class Architecture Freeze

Status: Accepted (API frozen)
Date: 2026-08-26
Depends on: [ADR-001: Channel Model Architecture](../adr/ADR-001-channel-model-architecture.md)

## 1. Purpose

This document freezes the **Channel Model interface** — the contract between the
simulation pipeline and any concrete propagation implementation.

The goal of Task 2 is **not** to implement a propagation formula. It is to lock the
boundary so that future models can be added as drop-in implementations:

```
ChannelModel (abstract)
   │
   ├── LogDistanceChannel      (v0.1 — baseline)
   ├── ShadowingChannel        (environment randomness)
   ├── RayleighChannel         (multipath fading)
   ├── UrbanChannel            (building / obstruction)
   ├── MLChannelModel          (learned from data)
   └── DigitalTwinChannel      (live environment mirror)
```

None of these implementations may require changes to `Node`, `Gateway`, `MAC`,
or the `Simulation Engine`.

## 2. Pipeline Position (frozen, see ADR-001)

```
Node
  │  packet
  ▼
Packet Generation
  │
  ▼
TransmissionContext        ◀── built by engine, NOT by Node
  │
  ▼
ChannelModel.evaluate(context)  →  ChannelResult
  │
  ▼
Gateway Receiver
  │
  ▼
ADR / Controller
```

The `ChannelModel` is invoked **between transmission intent and reception result**.
It is a Physical-Layer abstraction owned by the engine, not by any node or gateway.

## 3. Input Contract — `TransmissionContext`

```python
@dataclass
class TransmissionContext:
    tx_node: "Node"            # sender (read-only reference)
    rx_gateway: "Gateway"      # intended receiver (read-only reference)
    distance: float            # meters, computed by engine
    tx_power: float            # dBm, node transmit power
    frequency: float           # Hz (e.g. 868e6 for EU868)
    spreading_factor: int      # SF7..SF12
    bandwidth: float           # Hz (e.g. 125e3)
    environment: str           # "urban" | "suburban" | "indoor" | "rural"
    timestamp: float           # simulation clock, seconds
```

Notes:
- `distance` is computed by the engine from node/gateway positions; the channel
  model never reads positions itself.
- `tx_node` / `rx_gateway` are passed as references for metadata only — the channel
  model must not mutate them.

## 4. Output Contract — `ChannelResult`

```python
@dataclass
class ChannelResult:
    rssi: float              # dBm, received signal strength
    snr: float               # dB, signal-to-noise ratio
    pdr: float               # 0..1, packet delivery ratio
    packet_received: bool    # True if packet passed the reception threshold
    propagation_delay: float # seconds, one-way air-time + path delay
```

Semantics:
- `rssi` / `snr` describe the wireless link quality at the gateway.
- `pdr` is the probability the packet is correctly received (0..1); `packet_received`
  is the sampled boolean outcome used by the simulation for this transmission.
- `propagation_delay` feeds timing / path-loss analysis and future mobility models.

## 5. Abstract Interface — `ChannelModel`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class TransmissionContext:
    tx_node: "Node"
    rx_gateway: "Gateway"
    distance: float
    tx_power: float
    frequency: float
    spreading_factor: int
    bandwidth: float
    environment: str
    timestamp: float

@dataclass
class ChannelResult:
    rssi: float
    snr: float
    pdr: float
    packet_received: bool
    propagation_delay: float

class ChannelModel(ABC):
    @abstractmethod
    def evaluate(self, context: TransmissionContext) -> ChannelResult:
        """Compute link quality for a single transmission.

        Implementations MUST be pure with respect to the simulation state:
        no mutation of Node / Gateway / MAC, no side effects beyond returning a result.
        """
        ...
```

This interface is the **single point of extension**. A new propagation model is a
new subclass of `ChannelModel` — nothing else in the codebase changes.

## 6. Future Implementations (interface conformance, not yet coded)

| Implementation | Models | v-target |
|---|---|---|
| `LogDistanceChannel` | distance → path loss → RSSI → SNR → PDR | v0.1 (baseline) |
| `ShadowingChannel` | + log-normal random shadowing | v0.2 |
| `RayleighChannel` | + multipath Rayleigh fading | v0.3 |
| `UrbanChannel` | + building / obstruction loss | v0.4 |
| `MLChannelModel` | learned mapping context → result | future |
| `DigitalTwinChannel` | live environment mirror | future |

All conform to `ChannelModel.evaluate()`; selection is by configuration, not by
editing call sites.

## 7. Integration Point (frozen)

The engine holds a `ChannelModel` instance and calls `evaluate()` once per
transmission to produce the `ChannelResult` consumed downstream by gateway
reception and ADR logic. Exactly where the call is inserted is decided in Task 3
(code phase) — this document only fixes the interface.

## 8. Non-goals (this Task)

- No concrete propagation math (that is Task 3 / `LogDistanceChannel`).
- No changes to `simulator/`, `backend/`, `gateway/`, `frontend/`.
- No database schema, no dashboard changes.
- No ML training, RL, or calibration.

Goal: **freeze the API so the rest of the system can depend on a stable contract.**
