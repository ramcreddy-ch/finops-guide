const fmtMoney = (n) => `$${Number(n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const charts = {};

function upsertChart(canvasId, config) {
  const ctx = document.getElementById(canvasId);
  if (charts[canvasId]) {
    charts[canvasId].data = config.data;
    charts[canvasId].update();
    return;
  }
  charts[canvasId] = new Chart(ctx, config);
}

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} -> ${res.status}`);
  return res.json();
}

async function refreshSummary() {
  const data = await getJSON("/api/summary");
  document.getElementById("card-today").textContent = fmtMoney(data.today_cost);
  document.getElementById("card-mtd").textContent = fmtMoney(data.month_to_date_cost);
  document.getElementById("card-forecast").textContent = fmtMoney(data.forecast?.projected_month_end);
  document.getElementById("card-anomalies").textContent = data.active_anomalies;
}

async function refreshProviderChart() {
  const data = await getJSON("/api/costs/by/provider?days=7");
  upsertChart("chart-provider", {
    type: "bar",
    data: {
      labels: data.map((d) => d.key),
      datasets: [{ label: "Cost (USD)", data: data.map((d) => d.cost), backgroundColor: "#4f8cff" }],
    },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } },
  });
}

async function refreshServiceChart() {
  const data = await getJSON("/api/costs/by/service?days=7");
  const palette = ["#4f8cff", "#3fbf6f", "#e0a72e", "#e0543a", "#9b6ff2", "#2ec8c8", "#f27ea1", "#8f9bb3"];
  upsertChart("chart-service", {
    type: "doughnut",
    data: {
      labels: data.map((d) => d.key),
      datasets: [{ data: data.map((d) => d.cost), backgroundColor: palette }],
    },
    options: { plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 10 } } } } },
  });
}

async function refreshTrendChart() {
  const data = await getJSON("/api/costs/trend?days=30");
  upsertChart("chart-trend", {
    type: "line",
    data: {
      labels: data.map((d) => d.day),
      datasets: [{
        label: "Daily spend",
        data: data.map((d) => d.cost),
        borderColor: "#4f8cff",
        backgroundColor: "rgba(79,140,255,0.15)",
        fill: true,
        tension: 0.25,
        pointRadius: 0,
      }],
    },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } },
  });
}

function fillTable(tableId, rows, rowRenderer) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  tbody.innerHTML = "";
  if (!rows.length) {
    const tr = document.createElement("tr");
    const colCount = document.querySelectorAll(`#${tableId} thead th`).length;
    tr.innerHTML = `<td colspan="${colCount}" style="color:var(--muted)">nothing to show</td>`;
    tbody.appendChild(tr);
    return;
  }
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = rowRenderer(row);
    tbody.appendChild(tr);
  }
}

async function refreshAnomalies() {
  const data = await getJSON("/api/anomalies");
  fillTable("table-anomalies", data.slice(0, 10), (r) => `
    <td>${r.resource_id}</td>
    <td>${r.service}</td>
    <td>${r.team}</td>
    <td>${fmtMoney(r.cost_amount)}</td>
    <td>${fmtMoney(r.baseline_mean)}</td>
    <td>${r.z_score ?? "n/a"}</td>
  `);
}

async function refreshBudgets() {
  const data = await getJSON("/api/budgets");
  fillTable("table-budgets", data, (r) => `
    <td>${r.name}</td>
    <td>${fmtMoney(r.actual_month_to_date)} / ${fmtMoney(r.monthly_amount)}</td>
    <td>${r.pct_consumed}%</td>
    <td>${fmtMoney(r.projected_month_end)}</td>
    <td class="status-${r.status}">${r.status.replace("_", " ")}</td>
  `);
}

async function refreshIdle() {
  const data = await getJSON("/api/optimization/idle?lookback_days=7");
  fillTable("table-idle", data.slice(0, 10), (r) => `
    <td>${r.resource_id}</td>
    <td>${r.service}</td>
    <td>${r.avg_utilization_pct}%</td>
    <td>${fmtMoney(r.projected_monthly_cost)}</td>
  `);
}

async function refreshCommitments() {
  const data = await getJSON("/api/optimization/commitments?lookback_days=14");
  fillTable("table-commitments", data.slice(0, 10), (r) => `
    <td>${r.provider}</td>
    <td>${r.service}</td>
    <td>${r.on_demand_share_pct}%</td>
    <td>${fmtMoney(r.estimated_monthly_savings)}</td>
  `);
}

async function refreshAll() {
  await Promise.allSettled([
    refreshSummary(),
    refreshProviderChart(),
    refreshServiceChart(),
    refreshTrendChart(),
    refreshAnomalies(),
    refreshBudgets(),
    refreshIdle(),
    refreshCommitments(),
  ]);
}

function connectLiveFeed() {
  const indicator = document.getElementById("live-indicator");
  const indicatorText = document.getElementById("live-indicator-text");
  const list = document.getElementById("live-feed-list");
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/live`);

  ws.onopen = () => {
    indicator.classList.add("online");
    indicator.classList.remove("offline");
    indicatorText.textContent = "live";
  };

  ws.onclose = () => {
    indicator.classList.remove("online");
    indicator.classList.add("offline");
    indicatorText.textContent = "disconnected";
    setTimeout(connectLiveFeed, 3000);
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type !== "cost_tick") return;

    const li = document.createElement("li");
    const topServices = (msg.top_services || []).map((s) => `${s.service} ${fmtMoney(s.cost)}`).join(", ");
    li.textContent = `${msg.timestamp}  ${msg.record_count} records  ${fmtMoney(msg.tick_total)}  [${topServices}]`;
    list.prepend(li);
    while (list.children.length > 30) list.removeChild(list.lastChild);

    refreshSummary();
  };
}

refreshAll();
connectLiveFeed();
setInterval(refreshAll, 20000);
