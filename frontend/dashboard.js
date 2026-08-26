// LoRa Dashboard (Sprint 4.4.4 + v1.2 hardening) — 零依赖原生 JS + SVG
// 通过同源于后端挂载的 /api/* 拉取数据；无 CDN、可离线运行。
"use strict";

const API = window.location.origin;
const SVGNS = "http://www.w3.org/2000/svg";
const GW_PALETTE = ["#2b6cb0", "#dd6b20", "#38a169", "#805ad5"];

// ========== v1.2 T12 API Key 管理 (localStorage, masked display, REST+WS 注入) ==========
const LS_API_KEY = "lora_api_key";

function _loadApiKey() {
  try { return localStorage.getItem(LS_API_KEY) || ""; } catch (_) { return ""; }
}
function _saveApiKey(k) {
  try { localStorage.setItem(LS_API_KEY, k || ""); } catch (_) {}
}
function _clearApiKey() {
  try { localStorage.removeItem(LS_API_KEY); } catch (_) {}
}
function _maskKey(k) {
  if (!k) return "";
  if (k.length <= 4) return "••••";
  return k.slice(0, 2) + "••••" + k.slice(-2);
}

// 取「实际原始」密钥 (REST header / WS ?token= 用)
function getApiKeyRaw() { return _loadApiKey(); }

// 顶部 auth-bar：label + password input + 保存 / 清除
function mountAuthBar() {
  const header = document.querySelector("header");
  if (!header || document.getElementById("auth-bar")) return;
  const bar = document.createElement("div");
  bar.id = "auth-bar";
  bar.className = "auth-bar";
  bar.innerHTML =
    '<span class="auth-label">API Key</span>' +
    '<input id="auth-input" type="password" autocomplete="off" spellcheck="false" ' +
      'placeholder="set API_KEY env to enable on server">' +
    '<button id="auth-save" type="button">Save</button>' +
    '<button id="auth-clear" type="button">Clear</button>' +
    '<span id="auth-preview" class="auth-preview"></span>';
  header.appendChild(bar);

  const input = document.getElementById("auth-input");
  const save = document.getElementById("auth-save");
  const clear = document.getElementById("auth-clear");
  const prev = document.getElementById("auth-preview");

  // 初始化：如果已保存则显示 mask 预览，input placeholder 变 saved
  const existing = _loadApiKey();
  if (existing) prev.textContent = "Saved: " + _maskKey(existing);

  save.onclick = () => {
    const v = input.value.trim();
    if (v) {
      _saveApiKey(v);
      prev.textContent = "Saved: " + _maskKey(v);
      input.value = "";
      showToast("API Key saved (browser local). WS will reconnect.", "success");
      // WS 重连使用新 key
      if (ws) { try { ws.close(); } catch (_) {} }
    } else {
      showToast("Key is empty; click Clear to remove.", "warning");
    }
  };
  clear.onclick = () => {
    _clearApiKey();
    prev.textContent = "";
    input.value = "";
    showToast("API Key cleared from browser.", "info");
  };
}

// ========== v1.2 T11 全局 Toast 组件 ==========
function mountToastRoot() {
  if (document.getElementById("toast-root")) return;
  const r = document.createElement("div");
  r.id = "toast-root";
  r.className = "toast-root";
  document.body.appendChild(r);
}
function showToast(msg, kind, ms) {
  mountToastRoot();
  kind = kind || "info";
  ms = ms || (kind === "error" ? 6000 : 3200);
  const root = document.getElementById("toast-root");
  const t = document.createElement("div");
  t.className = "toast toast-" + kind;
  t.textContent = msg;
  root.appendChild(t);
  // 下一 tick 加 .in 触发 CSS transition (如果存在)
  requestAnimationFrame(() => { t.classList.add("toast-in"); });
  setTimeout(() => {
    t.classList.remove("toast-in");
    setTimeout(() => t.remove(), 280);
  }, ms);
}

// ========== 网关着色 ==========
function gwColor(id) {
  const m = /^GW0*(\d+)$/.exec(id || "");
  const idx = m ? (parseInt(m[1], 10) - 1) : -1;
  return (idx >= 0 && idx < GW_PALETTE.length) ? GW_PALETTE[idx] : "#9ca3af";
}

const TICK_MS = 900;        // 自动运行步进间隔
const STEP_PER_TICK = 5;    // 每次推进的事件数

// P1-8: 链式 setTimeout，不堆叠请求
let autoTimer = null;
let autoRunning = false;

// ========== v1.2 T11 WebSocket + 指数退避重连 (1s → 30s cap) ==========
let wsOnline = false;
let livePackets = [];
let ws = null;
let wsBackoffMs = 1000;      // 起始 1s
const WS_BACKOFF_MAX = 30000;// 封顶 30s
let wsReconnectTimer = null; // 便于后续可 cancel

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
  // 清任何未完成的重连计划
  if (wsReconnectTimer != null) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
  const proto = location.protocol === "https:" ? "wss://" : "ws://";
  const key = getApiKeyRaw();
  const qs = key ? ("?token=" + encodeURIComponent(key)) : "";
  let sock;
  try {
    sock = new WebSocket(proto + location.host + "/ws" + qs);
  } catch (e) {
    wsOnline = false;
    setWsBadge("WS 离线", "state-finished");
    _scheduleWsReconnect();
    return;
  }
  ws = sock;
  setWsBadge("WS 连接中…", "state-paused");

  sock.onopen = () => {
    wsOnline = true;
    wsBackoffMs = 1000;                 // 成功立刻重置退避
    setWsBadge("WS 在线", "state-running");
  };
  sock.onmessage = (e) => {
    try { handleTelemetry(JSON.parse(e.data)); } catch (_) {}
  };
  sock.onerror = () => {
    wsOnline = false;
    setWsBadge("WS 离线", "state-finished");
  };
  sock.onclose = () => {
    wsOnline = false;
    setWsBadge("WS 离线", "state-finished");
    _scheduleWsReconnect();
  };
}

function _scheduleWsReconnect() {
  if (wsReconnectTimer != null) return;
  const next = wsBackoffMs;
  wsBackoffMs = Math.min(WS_BACKOFF_MAX, Math.floor(wsBackoffMs * 2)); // 指数 ×2
  // 30s 到达顶之后，用户会感知 "30s 自动重试"
  setWsBadge("WS 重试 " + (next / 1000).toFixed(0) + "s", "state-finished");
  wsReconnectTimer = setTimeout(() => {
    wsReconnectTimer = null;
    connectWs();
  }, next);
}

// ========== 工具 + API Key 注入 ==========
function $(id) { return document.getElementById(id); }

function _authHeaders(extra) {
  const h = Object.assign({}, extra || {});
  const k = getApiKeyRaw();
  if (k) h["X-API-Key"] = k;
  return h;
}

async function apiGet(path) {
  const r = await fetch(API + path, {
    cache: "no-store",
    headers: _authHeaders(),
  });
  if (r.status === 401) showToast("Unauthorized — save a valid API Key (top-right).", "warning", 6000);
  if (!r.ok) throw new Error(path + " HTTP " + r.status);
  return r.json();
}
async function apiPost(path) {
  const r = await fetch(API + path, {
    method: "POST",
    cache: "no-store",
    headers: _authHeaders(),
  });
  if (r.status === 401) showToast("Unauthorized — save a valid API Key (top-right).", "warning", 6000);
  if (!r.ok) throw new Error(path + " HTTP " + r.status);
  return r.json();
}
async function apiPostJson(path, body) {
  const r = await fetch(API + path, {
    method: "POST",
    headers: _authHeaders({ "Content-Type": "application/json" }),
    cache: "no-store",
    body: JSON.stringify(body),
  });
  if (r.status === 401) showToast("Unauthorized — save a valid API Key (top-right).", "warning", 6000);
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

// ========== 刷新与渲染 ==========
async function refresh() {
  try {
    const calls = [
      apiGet("/api/simulation/status"),
      apiGet("/api/statistics"),
      apiGet("/api/nodes"),
      apiGet("/api/gateways"),
      apiGet("/api/history"),
    ];
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

// ========== 实验配置面板 ==========
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

// ========== v1.2 T12 applyConfig：disabled + loading + 10s 强制恢复 ==========
function applyConfig() {
  setCfgMsg("", "");
  const btn = $("btn-apply");
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
    showToast("Invalid input: " + e.message, "error");
    return;
  }

  // 停 auto-run
  if (autoRunning || autoTimer != null) {
    setAuto(false);
    const chk = $("chk-auto");
    if (chk) chk.checked = false;
  }

  // 进入 loading 态
  let recovered = false;
  const originalLabel = btn ? (btn.textContent || "Apply") : "Apply";
  const restore = (why) => {
    if (recovered) return;
    recovered = true;
    if (btn) {
      btn.disabled = false;
      btn.classList.remove("btn-loading");
      btn.textContent = originalLabel;
    }
  };
  if (btn) {
    btn.disabled = true;
    btn.classList.add("btn-loading");
    btn.textContent = "Applying…";
  }
  // 10 s 强制恢复安全阀 (TR: Apply 按钮 10s 内从 loading 态恢复)
  const safetyTimer = setTimeout(() => {
    if (!recovered) {
      restore("timeout");
      setCfgMsg("Apply timed out (>10s). Check network / API key.", "error");
      showToast("Apply timed out (>10s).", "error");
    }
  }, 10000);

  apiPostJson("/api/simulation/config", payload)
    .then(() => {
      setCfgMsg("Configuration applied. Press Start to run.", "ok");
      showToast("Configuration applied. Press Start.", "success");
      restore("ok");
      clearTimeout(safetyTimer);
      return refresh();
    })
    .catch((e) => {
      setCfgMsg("Apply failed: " + e.message, "error");
      showToast("Apply failed: " + e.message, "error");
      restore("err");
      clearTimeout(safetyTimer);
    });
}

function bindConfigPanel() {
  const btn = $("btn-apply");
  if (btn) btn.onclick = applyConfig;
  fetchCurrentConfig();
}

// ========== 控制 ==========
function tick() {
  return apiPost("/api/simulation/step?steps=" + STEP_PER_TICK)
    .then(refresh)
    .catch(e => { console.error("tick error:", e); });
}

// P1-8: 链式 setTimeout，不堆叠请求
async function autoTickLoop() {
  if (!autoRunning) return;
  try { await tick(); } catch (_) {}
  if (autoRunning) autoTimer = setTimeout(autoTickLoop, TICK_MS);
}

function setAuto(on) {
  if (on) {
    if (autoRunning) return;
    autoRunning = true;
    apiPost("/api/simulation/start").catch(() => {});
    autoTimer = setTimeout(autoTickLoop, 0);
  } else {
    autoRunning = false;
    if (autoTimer != null) {
      clearTimeout(autoTimer);
      autoTimer = null;
    }
  }
}

function bindControls() {
  $("btn-start").onclick = () => apiPost("/api/simulation/start").then(refresh).catch(e => showToast("Start failed: " + e.message, "error"));
  $("btn-pause").onclick = () => apiPost("/api/simulation/pause").then(refresh).catch(e => showToast("Pause failed: " + e.message, "error"));
  $("btn-step").onclick = () => apiPost("/api/simulation/step?steps=1").then(refresh).catch(e => showToast("Step failed: " + e.message, "error"));
  $("btn-reset").onclick = () => apiPost("/api/simulation/reset").then(refresh).catch(e => showToast("Reset failed: " + e.message, "error"));
  $("chk-auto").onchange = (e) => setAuto(e.target.checked);
}

window.addEventListener("DOMContentLoaded", () => {
  mountToastRoot();           // T11 toast
  mountAuthBar();             // T12 API Key UI
  bindControls();
  bindConfigPanel();
  refresh();
  setInterval(refresh, 1500); // 基础轮询
  if ($("chk-auto").checked) setAuto(true);
  connectWs();                // 实时通道（含指数退避重连）
});
