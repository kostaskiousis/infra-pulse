"use strict";

const $ = id => document.getElementById(id);
const state = { interval: 15, refreshing: false };
const formatNumber = (value, decimals = 1) => Number.isFinite(value) ? value.toFixed(decimals) : "—";
const dateLabel = iso => iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "Awaiting first scan...";

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function put(id, value) { $(id).textContent = value; }

function renderOverview(data) {
  state.interval = data.interval_seconds || 15;
  put("total-devices", data.targets);
  put("up-devices", data.up);
  put("issue-devices", data.down + data.degraded + data.errors);
  put("sample-rate", `Sampling every ${state.interval}s`);
  put("last-check", data.last_check ? `Last check: ${dateLabel(data.last_check)}` : "Awaiting first scan...");

  const available = data.devices.filter(item => item.latency_ms !== null).map(item => item.latency_ms);
  put("avg-latency", available.length ? `${formatNumber(available.reduce((a, b) => a + b, 0) / available.length)} ms` : "—");

  const online = Boolean(data.last_check) && !data.poll_error;
  put("connection-status", online ? "Monitoring active" : "Waiting for monitor");
  document.querySelector(".live-dot").classList.toggle("online", online);

  if (data.system) {
    for (const name of ["cpu", "ram", "disk"]) {
      const value = data.system[`${name}_percent`];
      put(`${name}-value`, formatNumber(value));
      $(`${name}-bar`).style.width = `${Math.min(100, Math.max(0, value))}%`;
      put(`${name}-state`, value >= 90 ? "High usage" : "Normal");
    }
    put("rx-value", formatNumber(data.system.rx_mbps, 3));
    put("tx-value", formatNumber(data.system.tx_mbps, 3));
  }

  const tbody = $("device-rows");
  tbody.replaceChildren();
  if (!data.devices.length) {
    const row = element("tr");
    const cell = element("td", "empty", "No device samples yet. Configure targets in config/targets.json.");
    cell.colSpan = 5;
    row.append(cell);
    tbody.append(row);
  }
  for (const device of data.devices) {
    const row = element("tr");
    row.append(element("td", "device-name", device.name));
    row.append(element("td", "host-text", device.host));
    const status = element("td");
    const badge = element("span", `status ${device.status}`, device.status.toUpperCase());
    if (device.error) badge.title = device.error;
    status.append(badge);
    row.append(status);
    row.append(element("td", "", device.latency_ms === null ? "—" : `${formatNumber(device.latency_ms, 2)} ms`));
    row.append(element("td", "", `${formatNumber(device.packet_loss)}%`));
    tbody.append(row);
  }
}

function polyline(samples, key, width, height, padding) {
  const points = samples.map((s, index) => {
    const x = padding + index * (width - 2 * padding) / Math.max(1, samples.length - 1);
    const y = padding + (100 - Number(s[key])) * (height - 2 * padding) / 100;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return points.join(" ");
}
function renderChart(samples) {
  const container = $("history-chart");
  container.replaceChildren();
  if (!samples.length) { container.textContent = "Collecting history…"; return; }
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 680 185");
  svg.setAttribute("preserveAspectRatio", "none");
  const width = 680, height = 185, pad = 10;
  for (const value of [0, 25, 50, 75, 100]) {
    const line = document.createElementNS(ns, "line");
    const y = pad + (100 - value) * (height - 2 * pad) / 100;
    for (const [attr, val] of [["x1", pad], ["x2", width - pad], ["y1", y], ["y2", y], ["stroke", "#25344b"], ["stroke-dasharray", "4 5"]]) line.setAttribute(attr, val);
    svg.append(line);
  }
  for (const [key, color] of [["cpu_percent", "#a07bfc"], ["ram_percent", "#47a4ff"]]) {
    const path = document.createElementNS(ns, "polyline");
    path.setAttribute("points", polyline(samples, key, width, height, pad));
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", color);
    path.setAttribute("stroke-width", "2.6");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    svg.append(path);
  }
  container.append(svg);
}
function renderEvents(events) {
  const container = $("event-rows");
  container.replaceChildren();
  if (!events.length) { container.append(element("div", "empty", "No alerts have been recorded.")); return; }
  for (const entry of events) {
    const row = element("div", "event-row");
    row.append(element("div", `event-dot ${entry.level}`));
    const info = element("div", "event-message", entry.message);
    info.append(element("span", "event-meta", `${entry.level.toUpperCase()} · ${entry.category} · ${entry.target}`));
    row.append(info);
    row.append(element("div", "event-time", dateLabel(entry.ts)));
    container.append(row);
  }
}
async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status} at ${path}`);
  return response.json();
}
async function refresh() {
  if (state.refreshing) return;
  state.refreshing = true;
  try {
    const [overview, history, events] = await Promise.all([
      fetchJson("/api/overview"), fetchJson("/api/history?limit=80"), fetchJson("/api/events?limit=20")
    ]);
    renderOverview(overview);
    renderChart(history.samples);
    renderEvents(events.events);
  } catch (error) {
    put("connection-status", "API unavailable");
    document.querySelector(".live-dot").classList.remove("online");
    console.error("InfraPulse refresh failed:", error);
  } finally {
    state.refreshing = false;
  }
}
function updateTime() { put("current-time", new Date().toLocaleTimeString()); }
updateTime();
setInterval(updateTime, 1000);
refresh();
setInterval(refresh, 5000);
