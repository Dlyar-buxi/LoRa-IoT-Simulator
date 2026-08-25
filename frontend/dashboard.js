// LoRa Dashboard (Sprint 4.4.4) — 零依赖原生 JS + SVG
// 通过同源于后端挂载的 /api/* 拉取数据；无 CDN、可离线运行。
"use strict";

const API = window.location.origin;
const SVGNS = "http://www.w3.org/2000/svg";
const GW_PALETTE = ["#2b6cb0", "#dd6b20", "#38a169", "#805ad5"];

// 网关着色：按编号取调色板（支持最多 4 网关，Sprint 5.5 D6）
function gwColor(id) {
  const m = /^GW0*(\d+)$/.exec(id || "");
  const idx = m ? (parseInt(m[1], 10) - 1) : -1;
  return (idx >= 0 && idx < GW_PALETTE.length) ? GW_PALETTE[idx] : "#9ca3af";
}

const TICK_MS = 900;        // 自动运行步进间隔
const STEP_PER_TICK = 5;    // 每次推进的事件数

let autoTimer = null;

// ---------- WebSocket 实时通道（Sprint 5.1）----------
// 初始：REST 首屏加载；运行：WebSocket 实时；异常：REST 轮询降级。
let wsOnline = false;
let livePackets = [];
let ws = null;

function handleTelemetry(rec) {
  livePackets.push(rec);
  if (livePackets.length > 300) livePackets.shift();
  renderPackets(livePackets.slice(-30));
}

function setWsBadge(text, cls) {
  let b = $("ws-badge");
  if (!b) {
    const sb = $("state-badge");
    if (sb && sb.parentNode) {
      b = document.createElement("span");
      b.id = "ws-badge";
      sb.parentNode.insertBefore(b, sb.nextSibling);
    }
  }
  if (b) { b.textContent = text; b.className = "badge " + cls; }
}

function connectWs() {
  const proto = location.protocol === "https:" ? "wss://" : "ws://";
  try {
    ws = new WebSocket(proto + location.host + "/ws");
  } catch (e) {
    wsOnline = false;
    setWsBadge("WS 离线", "state-finished");
    return;
  }
  ws.onopen = () => { wsOnline = true; setWsBadge("WS 在线", "state-running"); };
  ws.onmessage = (e) => { try { handleTelemetry(JSON.parse(e.data)); } catch (_) {} };
  ws.onclose = () => { wsOnline = false; setWsBadge("WS 离线", "state-finished"); };
  ws.onerror = () => { wsOnline = false; setWsBadge("WS 离线", "state-finished"); };
}

// ---------- 工具 ----------
function $(id) { return document.getElementById(id); }

async function apiGet(path) {
  const r = await fetch(API + path, { cache: "no-store" });
  if (!r.ok) throw new Error(path + " HTTP " + r.status);
  return r.json();
}
async function apiPost(path) {
  const r = await fetch(API + path, { method: "POST", cache: "no-store" });
  if (!r.ok) throw new Error(path + " HTTP " + r.status);
  return r.json();
}
async function apiPostJson(path, body) {
  const r = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let detail = "HTTP " + r.status;
    try {
      const j = await r.json();
      if (j && j.detail) detail = j.detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return r.json();
}
function svgEl(tag, attrs) {
  const e = document.createElementNS(SVGNS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  return e;
}

// ---------- 刷新与渲染 ----------
async function refresh() {
  try {
    const calls = [
      apiGet("/api/simulation/status"),
      apiGet("/api/statistics"),
      apiGet("/api/nodes"),
      apiGet("/api/gateways"),
      apiGet("/api/history"),
    ];
    // WS 在线时，packet 表由实时通道驱动；离线时回退 REST 拉取
    if (!wsOnline) calls.push(apiGet("/api/packets?limit=30"));
    const results = await Promise.all(calls);
    const [status, stats, nodes, gateways, history] = results;
    const packets = wsOnline ? livePackets.slice(-30) : results[5];
    renderStatus(status, stats);
    renderTopology(nodes, gateways);
    renderPdr(history);
    renderRssi(nodes);
    renderSf(nodes);
    renderPackets(packets);
  } catch (e) {
    console.error("refresh failed:", e);
  }
}

function renderStatus(s, stats) {
  $("kpi-pdr").textContent = (stats.pdr * 100).toFixed(1) + "%";
  $("kpi-throughput").textContent = stats.throughput.toFixed(2);
  $("kpi-received").textContent = s.received;
  $("kpi-lost").textContent = s.lost;
  $("kpi-time").textContent = s.time.toFixed(2);
  $("kpi-pending").textContent = s.pending;
  const badge = $("state-badge");
  badge.textContent = s.state;
  badge.className = "badge state-" + s.state;
}

function renderTopology(nodes, gateways) {
  const root = $("topo");
  root.innerHTML = "";
  for (const g of gateways) {
    root.appendChild(svgEl("rect", {
      x: g.x - 18, y: g.y - 18, width: 36, height: 36,
      fill: "#111827", stroke: "#ffffff", "stroke-width": 3,
    }));
    const t = svgEl("text", {
      x: g.x, y: g.y + 6, fill: "#fff", "font-size": 20, "text-anchor": "middle",
    });
    t.textContent = g.id;
    root.appendChild(t);
  }
  for (const n of nodes) {
    const c = n.gateway ? gwColor(n.gateway) : "#9ca3af";
    root.appendChild(svgEl("circle", { cx: n.x, cy: n.y, r: 6, fill: c, "fill-opacity": 0.85 }));
  }
}

function renderPdr(history) {
  const root = $("pdr-chart");
  root.innerHTML = "";
  if (!history.length) return;
  const W = 600, H = 300, P = 36;
  const maxT = Math.max(1, ...history.map(h => h.time));
  const x = t => P + (t / maxT) * (W - 2 * P);
  const y = p => H - P - p * (H - 2 * P);
  root.appendChild(svgEl("line", { x1: P, y1: H - P, x2: W - P, y2: H - P, stroke: "#cbd5e1" }));
  root.appendChild(svgEl("line", { x1: P, y1: P, x2: P, y2: H - P, stroke: "#cbd5e1" }));
  const pts = history.map(h => x(h.time) + "," + y(h.pdr)).join(" ");
  root.appendChild(svgEl("polyline", { points: pts, fill: "none", stroke: "#2b6cb0", "stroke-width": 2 }));
}

function barChart(rootId, entries, color) {
  const root = $(rootId);
  root.innerHTML = "";
  const W = 600, H = 300, P = 36;
  const max = Math.max(1, ...entries.map(e => e.v));
  const n = entries.length;
  const bw = (W - 2 * P) / n;
  root.appendChild(svgEl("line", { x1: P, y1: H - P, x2: W - P, y2: H - P, stroke: "#cbd5e1" }));
  entries.forEach((e, i) => {
    const h = (e.v / max) * (H - 2 * P);
    const x0 = P + i * bw + 4;
    root.appendChild(svgEl("rect", { x: x0, y: H - P - h, width: bw - 8, height: h, fill: color }));
    const t = svgEl("text", {
      x: x0 + (bw - 8) / 2, y: H - P + 16, "text-anchor": "middle",
      "font-size": 12, fill: "#475569",
    });
    t.textContent = e.k;
    root.appendChild(t);
  });
}

function renderRssi(nodes) {
  const buckets = {};
  for (let v = -130; v <= -70; v += 10) buckets[v] = 0;
  for (const n of nodes) {
    if (n.rssi == null) continue;
    const b = Math.floor(n.rssi / 10) * 10;
    if (buckets[b] !== undefined) buckets[b]++;
  }
  const entries = Object.keys(buckets).map(k => ({ k: k, v: buckets[k] }));
  barChart("rssi-chart", entries, "#38a169");
}

function renderSf(nodes) {
  const counts = {};
  for (let sf = 7; sf <= 12; sf++) counts[sf] = 0;
  for (const n of nodes) counts[n.sf] = (counts[n.sf] || 0) + 1;
  const entries = [];
  for (let sf = 7; sf <= 12; sf++) entries.push({ k: "SF" + sf, v: counts[sf] });
  barChart("sf-chart", entries, "#805ad5");
}

function renderPackets(packets) {
  const tb = $("packet-tbody");
  tb.innerHTML = "";
  for (const p of packets.slice(-30)) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      "<td>" + p.time.toFixed(2) + "</td>" +
      "<td>" + p.event + "</td>" +
      "<td>" + p.node + "</td>" +
      "<td>" + p.sf + "</td>" +
      "<td>" + (p.rssi == null ? "-" : p.rssi.toFixed(1)) + "</td>" +
      "<td>" + (p.snr == null ? "-" : p.snr.toFixed(1)) + "</td>" +
      "<td>" + (p.gateway || "-") + "</td>" +
      "<td>" + (p.success == null ? "-" : (p.success ? "✓" : "✗")) + "</td>";
    tb.appendChild(tr);
  }
}

// ---------- 实验配置面板（Sprint 5.5）----------
// 网关坐标由前端按网格规则自动布点，用户只填数量（1–4）
function gwPositions(count, area) {
  const margin = area * 0.15;
  const usable = area - 2 * margin;
  const cols = Math.ceil(Math.sqrt(count));
  const rows = Math.ceil(count / cols);
  const pts = [];
  for (let i = 0; i < count; i++) {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const x = Math.round(margin + ((col + 0.5) / cols) * usable);
    const y = Math.round(margin + ((row + 0.5) / rows) * usable);
    pts.push(["GW" + String(i + 1).padStart(3, "0"), x, y]);
  }
  return pts;
}

function setCfgMsg(text, kind) {
  const m = $("cfg-msg");
  if (!m) return;
  m.textContent = text || "";
  m.className = "cfg-msg" + (kind ? " " + kind : "");
}

// 页面加载时预填当前生效配置（D4）
async function fetchCurrentConfig() {
  try {
    const cfg = await apiGet("/api/simulation/config");
    if (cfg.node_count != null) $("cfg-node_count").value = cfg.node_count;
    if (cfg.area_size != null) $("cfg-area_size").value = cfg.area_size;
    if (cfg.seed != null) $("cfg-seed").value = cfg.seed;
    if (cfg.duration != null) $("cfg-duration").value = cfg.duration;
    if (cfg.adr_enabled != null) $("cfg-adr_enabled").checked = cfg.adr_enabled;
    if (Array.isArray(cfg.gateways)) $("cfg-gateway_count").value = cfg.gateways.length;
  } catch (e) {
    console.error("prefill config failed:", e);
  }
}

// 提交配置：停 auto-run → POST → 刷新 → 提示（D3/D5）
function applyConfig() {
  setCfgMsg("", "");
  let payload;
  try {
    const node_count = parseInt($("cfg-node_count").value, 10);
    const area_size = parseFloat($("cfg-area_size").value);
    const seed = parseInt($("cfg-seed").value, 10);
    const duration = parseFloat($("cfg-duration").value);
    const adr_enabled = $("cfg-adr_enabled").checked;
    const gateway_count = parseInt($("cfg-gateway_count").value, 10);
    if (!(node_count > 0)) throw new Error("node_count must be > 0");
    if (!(area_size > 0)) throw new Error("area_size must be > 0");
    if (!(gateway_count >= 1 && gateway_count <= 4)) throw new Error("gateway_count must be 1–4");
    payload = {
      node_count, area_size, seed, duration, adr_enabled,
      gateways: gwPositions(gateway_count, area_size),
    };
  } catch (e) {
    setCfgMsg("Invalid input: " + e.message, "error");
    return;
  }
  // 停止自动运行，避免 Apply 后立即推进导致实验边界混乱（D3）
  if (autoTimer) {
    clearInterval(autoTimer);
    autoTimer = null;
    const chk = $("chk-auto");
    if (chk) chk.checked = false;
  }
  apiPostJson("/api/simulation/config", payload)
    .then(() => {
      setCfgMsg("Configuration applied. Press Start to run.", "ok");
      refresh();
    })
    .catch((e) => {
      setCfgMsg("Apply failed: " + e.message, "error");
    });
}

function bindConfigPanel() {
  const btn = $("btn-apply");
  if (btn) btn.onclick = applyConfig;
  fetchCurrentConfig();
}

// ---------- 控制 ----------
function tick() {
  apiPost("/api/simulation/step?steps=" + STEP_PER_TICK)
    .then(refresh)
    .catch(e => console.error("tick error:", e));
}

function setAuto(on) {
  if (on) {
    if (autoTimer) return;
    apiPost("/api/simulation/start").catch(() => {});
    autoTimer = setInterval(tick, TICK_MS);
  } else if (autoTimer) {
    clearInterval(autoTimer);
    autoTimer = null;
  }
}

function bindControls() {
  $("btn-start").onclick = () => apiPost("/api/simulation/start").then(refresh);
  $("btn-pause").onclick = () => apiPost("/api/simulation/pause").then(refresh);
  $("btn-step").onclick = () => apiPost("/api/simulation/step?steps=1").then(refresh);
  $("btn-reset").onclick = () => apiPost("/api/simulation/reset").then(refresh);
  $("chk-auto").onchange = (e) => setAuto(e.target.checked);
}

window.addEventListener("DOMContentLoaded", () => {
  bindControls();
  bindConfigPanel();
  refresh();
  setInterval(refresh, 1500);  // 基础轮询，保证手动操作后 KPI 即时刷新
  if ($("chk-auto").checked) setAuto(true);
  connectWs();  // 实时通道：连上后 packet 表转由 /ws 驱动
});
