/* ==========================================================================
   REAMP Client Application Logic (Bootstrap 5.3 Light Theme)
   Requirement: FR-UI-001 / AC-FR-UI-001
   Connects to REST backend on http://localhost:8000
   ========================================================================== */

let currentAssetId = "ASSET-INV-01";
let pollTimer = null;

document.addEventListener("DOMContentLoaded", () => {
  initOnboardingForms();
  loadAllData();
  // Poll every 3 seconds for live telemetry updates
  pollTimer = setInterval(loadAllData, 3000);
});

async function loadAllData() {
  try {
    await Promise.all([
      fetchOverview(),
      fetchSites(),
      fetchAssets(),
      fetchAssetDetail(currentAssetId),
      fetchAlerts(),
      fetchWorkOrders(),
      fetchAdaptations(),
      fetchAuditChain(),
      fetchUsers(),
    ]);
  } catch (err) {
    console.error("REAMP polling error:", err);
  }
}

// 1. Overview KPIs
async function fetchOverview() {
  const res = await fetch("/api/overview");
  if (!res.ok) return;
  const d = await res.json();

  document.getElementById("kpi-gen-mw").innerHTML = `${d.total_generation_mw.toFixed(2)} <small class="fs-6 text-muted">MW</small>`;
  document.getElementById("kpi-cap-mw").innerText = `${d.total_capacity_mw.toFixed(1)} MW`;
  document.getElementById("kpi-health-score").innerHTML = `${d.fleet_health_index.toFixed(1)} <small class="fs-6 text-muted">/ 100</small>`;
  document.getElementById("kpi-pr-val").innerText = d.fleet_performance_ratio.toFixed(3);
  document.getElementById("kpi-alerts-count").innerText = d.active_alerts_count;
  document.getElementById("badge-alert-count").innerText = d.active_alerts_count;
  document.getElementById("kpi-co2-val").innerHTML = `${d.co2_avoided_tons.toFixed(1)} <small class="fs-6 text-muted">Tons</small>`;

  // Calculate estimated loss at PPA rate
  const lossRate = (d.total_capacity_mw - d.total_generation_mw) * 1000 * 0.10;
  document.getElementById("kpi-rev-loss").innerText = `$${Math.max(0, lossRate).toFixed(2)}/h`;
}

// 2. Sites Cards
async function fetchSites() {
  const res = await fetch("/api/sites");
  if (!res.ok) return;
  const sites = await res.json();

  const container = document.getElementById("sites-cards-row");
  if (!container) return;

  container.innerHTML = sites.map(s => {
    let techBadge = "bg-primary";
    if (s.technology === "WIND") techBadge = "bg-info text-dark";
    else if (s.technology === "BESS") techBadge = "bg-purple text-white";
    else if (s.technology === "HYBRID") techBadge = "bg-success";

    return `
      <div class="col-12 col-md-6 col-xl-3">
        <div class="card card-reamp h-100 p-3">
          <div class="d-flex justify-content-between align-items-start mb-2">
            <div>
              <div class="small text-muted font-monospace">${s.site_id}</div>
              <h6 class="fw-bold text-dark m-0">${s.name}</h6>
            </div>
            <span class="badge ${techBadge}">${s.technology}</span>
          </div>
          <div class="row g-2 mt-2 pt-2 border-top small">
            <div class="col-6">
              <span class="text-muted">Generation:</span>
              <div class="fw-bold text-success">${s.active_generation_mw} MW</div>
            </div>
            <div class="col-6">
              <span class="text-muted">Capacity:</span>
              <div class="fw-bold text-dark">${s.rated_capacity_mw} MW</div>
            </div>
            <div class="col-6">
              <span class="text-muted">Assets:</span>
              <div class="fw-bold text-primary">${s.asset_count} units</div>
            </div>
            <div class="col-6">
              <span class="text-muted">Location:</span>
              <div class="fw-bold text-muted">${s.latitude.toFixed(1)}°, ${s.longitude.toFixed(1)}°</div>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join("");

  // Update onboarding facility counts & table
  const facStat = document.getElementById("stat-onboard-facilities");
  if (facStat) facStat.innerText = sites.length;
  const facPill = document.getElementById("count-pill-facilities");
  if (facPill) facPill.innerText = sites.length;

  const facTbody = document.getElementById("directory-facilities-tbody");
  if (facTbody) {
    facTbody.innerHTML = sites.map(s => {
      let techBadge = "bg-primary";
      if (s.technology === "WIND") techBadge = "bg-info text-dark";
      else if (s.technology === "BESS") techBadge = "bg-secondary";
      else if (s.technology === "HYBRID") techBadge = "bg-success";

      return `
        <tr>
          <td class="font-monospace fw-bold text-dark">${s.site_id}</td>
          <td class="fw-semibold">${s.name}</td>
          <td><span class="badge ${techBadge}">${s.technology}</span></td>
          <td class="fw-bold text-dark">${s.rated_capacity_mw.toFixed(1)} MW</td>
          <td class="small text-muted">${s.latitude.toFixed(2)}°, ${s.longitude.toFixed(2)}°</td>
          <td class="fw-semibold text-primary">${s.asset_count} units</td>
          <td class="fw-bold text-success">${s.active_generation_mw} MW</td>
        </tr>
      `;
    }).join("");
  }

  // Update facility select dropdown for device onboarding
  const facSelect = document.getElementById("device-facility");
  if (facSelect) {
    const currentVal = facSelect.value;
    facSelect.innerHTML = sites.map(s => 
      `<option value="${s.site_id}">${s.name} (${s.site_id})</option>`
    ).join("");
    if (currentVal && sites.some(s => s.site_id === currentVal)) {
      facSelect.value = currentVal;
    }
  }
}

// 3. Assets Cards & Sidebar
async function fetchAssets() {
  const res = await fetch("/api/assets");
  if (!res.ok) return;
  const assets = await res.json();

  // Overview Asset Grid
  const row = document.getElementById("assets-cards-row");
  if (row) {
    row.innerHTML = assets.map(a => {
      let badgeClass = "bg-primary";
      if (a.technology === "WIND" || a.asset_type.includes("TURBINE")) badgeClass = "bg-info text-dark";
      else if (a.technology === "BESS" || a.asset_type.includes("BESS")) badgeClass = "bg-secondary";
      else if (a.technology === "HYBRID") badgeClass = "bg-success";

      const healthClass = a.health_index > 90 ? "text-success" : (a.health_index > 75 ? "text-warning" : "text-danger");

      return `
        <div class="col-12 col-md-6 col-xl-3">
          <div class="card card-reamp h-100 p-3" style="cursor: pointer;" onclick="selectAsset('${a.asset_id}')">
            <div class="d-flex justify-content-between align-items-start mb-2">
              <div>
                <div class="small text-muted font-monospace">${a.asset_id}</div>
                <h6 class="fw-bold text-dark m-0">${a.name}</h6>
                <div class="small text-muted">${a.site_name}</div>
              </div>
              <span class="badge ${badgeClass}">${a.technology}</span>
            </div>
            <div class="row g-2 mt-2 pt-2 border-top small">
              <div class="col-6">
                <span class="text-muted">Power Output:</span>
                <div class="fw-bold text-primary">${a.current_power_kw.toFixed(1)} kW</div>
              </div>
              <div class="col-6">
                <span class="text-muted">Health Index:</span>
                <div class="fw-bold ${healthClass}">${a.health_index.toFixed(1)}</div>
              </div>
              <div class="col-6">
                <span class="text-muted">Perf. Ratio:</span>
                <div class="fw-bold text-dark">${a.performance_ratio.toFixed(3)}</div>
              </div>
              <div class="col-6">
                <span class="text-muted">Rated Power:</span>
                <div class="fw-bold text-dark">${a.rated_power_kw} kW</div>
              </div>
            </div>
          </div>
        </div>
      `;
    }).join("");
  }

  // Update onboarding device counts & table
  const devStat = document.getElementById("stat-onboard-devices");
  if (devStat) devStat.innerText = assets.length;
  const devPill = document.getElementById("count-pill-devices");
  if (devPill) devPill.innerText = assets.length;

  const devTbody = document.getElementById("directory-devices-tbody");
  if (devTbody) {
    devTbody.innerHTML = assets.map(a => {
      let badgeClass = "bg-primary";
      if (a.technology === "WIND" || a.asset_type.includes("TURBINE")) badgeClass = "bg-info text-dark";
      else if (a.technology === "BESS" || a.asset_type.includes("BESS")) badgeClass = "bg-secondary";
      else if (a.technology === "HYBRID") badgeClass = "bg-success";

      return `
        <tr>
          <td class="font-monospace fw-bold text-dark">${a.asset_id}</td>
          <td class="fw-semibold">${a.name}</td>
          <td class="small text-muted">${a.site_name}</td>
          <td><span class="badge ${badgeClass}">${a.asset_type}</span></td>
          <td class="small">${a.model}</td>
          <td class="fw-bold text-dark">${a.rated_power_kw} kW</td>
          <td><span class="badge bg-success-subtle text-success border border-success-subtle">${a.status}</span></td>
          <td>
            <button class="btn btn-sm btn-outline-primary py-0 px-2" onclick="selectAsset('${a.asset_id}'); switchTab('tab-twin')">
              <i class="bi bi-eye me-1"></i> Inspect
            </button>
          </td>
        </tr>
      `;
    }).join("");
  }
}

function selectAsset(assetId) {
  currentAssetId = assetId;
  const twinTabTrigger = document.querySelector("#twin-tab");
  if (twinTabTrigger) {
    const tabInstance = bootstrap.Tab.getOrCreateInstance(twinTabTrigger);
    tabInstance.show();
  }
  fetchAssetDetail(assetId);
  fetchAssets();
}

// 4. Asset Detail & Digital Twin
async function fetchAssetDetail(assetId) {
  const res = await fetch(`/api/asset/${assetId}`);
  if (!res.ok) return;
  const d = await res.json();

  document.getElementById("dt-asset-id").innerText = d.asset_id;
  document.getElementById("dt-asset-name").innerText = d.name;
  document.getElementById("dt-asset-site").innerText = `${d.site_name} (${d.rated_power_kw} kW Rated Model: ${d.model})`;

  const techBadge = document.getElementById("dt-tech-badge");
  techBadge.innerText = d.technology;
  techBadge.className = "badge fs-6 px-3 py-2 " + (
    d.technology === "WIND" ? "bg-info text-dark" : (d.technology === "BESS" ? "bg-secondary" : (d.technology === "HYBRID" ? "bg-success" : "bg-primary"))
  );

  // Digital Twin Operating State (AC-FR-TWN-001)
  const stateBadge = document.getElementById("dt-state-badge");
  if (d.digital_twin_state === "FAULT") {
    stateBadge.className = "badge bg-danger-subtle text-danger border border-danger-subtle px-2 py-1";
    stateBadge.innerHTML = `<i class="bi bi-exclamation-octagon me-1"></i> STATE: FAULT (AC-FR-TWN-001)`;
  } else {
    stateBadge.className = "badge bg-success-subtle text-success border border-success-subtle px-2 py-1";
    stateBadge.innerHTML = `<i class="bi bi-check-circle me-1"></i> STATE: RUNNING (AC-FR-TWN-001)`;
  }

  // Digital Twin State Residuals
  const dt = d.digital_twin || {};
  document.getElementById("dt-res-power").innerText = `${dt.power_residual_kw !== undefined ? (dt.power_residual_kw > 0 ? "+" : "") + dt.power_residual_kw : "0.0"} kW`;
  document.getElementById("dt-res-temp").innerText = `${dt.temperature_residual_c !== undefined ? (dt.temperature_residual_c > 0 ? "+" : "") + dt.temperature_residual_c : "0.0"} °C`;
  document.getElementById("dt-res-base").innerText = (d.baseline_multiplier || 1.0).toFixed(4);

  // Circular Gauges
  const powerKw = dt.power_ac_kw || (d.rated_power_kw * d.performance_ratio);
  const powerPct = Math.min(1.0, powerKw / Math.max(1.0, d.rated_power_kw));
  setGauge("dt-gauge-power", "dt-text-power", powerPct, `${Math.round(powerKw)}<small class="fs-6 text-muted">kW</small>`);

  const healthPct = Math.min(1.0, d.health_index / 100.0);
  setGauge("dt-gauge-health", "dt-text-health", healthPct, d.health_index.toFixed(1));

  const prPct = Math.min(1.0, d.performance_ratio / 1.1);
  setGauge("dt-gauge-pr", "dt-text-pr", prPct, d.performance_ratio.toFixed(2));

  const tempVal = dt.temperature_heatsink_c || 48.0;
  const tempPct = Math.min(1.0, tempVal / 100.0);
  setGauge("dt-gauge-temp", "dt-text-temp", tempPct, `${tempVal.toFixed(1)}<small class="fs-6 text-muted">°C</small>`);

  // 7-Dimension Health Progress Bars (AC-FR-HLT-001)
  const dims = d.health_dimensions || {};
  const progressContainer = document.getElementById("health-progress-bars");
  if (progressContainer) {
    const dimMeta = [
      { key: "performance", label: "1. Performance Yield Index (IEC 61724-1 / IEC 61400-12-1)", weight: "25%" },
      { key: "thermal_arrhenius", label: "2. Thermal Dissipation & Arrhenius Stress Acceleration (E_a = 0.7 eV)", weight: "20%" },
      { key: "availability", label: "3. Operational Availability & Uptime Ratio", weight: "15%" },
      { key: "communication", label: "4. Communication Link & Packet Integrity (Zero Drop)", weight: "10%" },
      { key: "fault_history", label: "5. Alarm Frequency & Historic Fault Severity", weight: "10%" },
      { key: "degradation_age", label: "6. Component Mechanical / Chemical Ageing", weight: "10%" },
      { key: "sensor_confidence", label: "7. Sensor Measurement Quality & Noise Floor", weight: "10%" },
    ];

    progressContainer.innerHTML = dimMeta.map(m => {
      const val = dims[m.key] || 95.0;
      const color = val > 90 ? "bg-success" : (val > 70 ? "bg-warning" : "bg-danger");
      return `
        <div class="mb-3">
          <div class="d-flex justify-content-between small fw-semibold mb-1">
            <span>${m.label} <span class="badge bg-light text-muted border ms-1">w=${m.weight}</span></span>
            <span class="font-monospace">${val.toFixed(1)} / 100</span>
          </div>
          <div class="progress" style="height: 10px;">
            <div class="progress-bar ${color}" role="progressbar" style="width: ${val}%;" aria-valuenow="${val}" aria-valuemin="0" aria-valuemax="100"></div>
          </div>
        </div>
      `;
    }).join("");
  }

  // Explainable AI: SHAP Features (AC-FR-XAI-001)
  const shapList = d.shap_explanation || [];
  const shapContainer = document.getElementById("shap-features-container");
  if (shapContainer) {
    shapContainer.innerHTML = shapList.map(s => {
      const isPositive = s.shap_value > 0;
      const badgeColor = isPositive ? "bg-danger text-white" : "bg-info text-dark";
      const icon = isPositive ? "bi-arrow-up-circle-fill text-danger" : "bi-arrow-down-circle-fill text-info";
      return `
        <div class="col-12 col-md-4">
          <div class="card card-reamp h-100 p-3 bg-light border">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <span class="badge bg-dark">Rank #${s.rank}</span>
              <span class="badge ${badgeColor}">${s.direction}</span>
            </div>
            <h6 class="fw-bold text-dark m-0"><i class="bi ${icon} me-2"></i>${s.sensor_name}</h6>
            <div class="font-monospace small text-primary mt-1">${s.feature}</div>
            <div class="mt-2 pt-2 border-top small text-secondary">${s.description}</div>
            <div class="mt-2 pt-1 small fw-bold text-dark">SHAP Impact Value: <span class="font-monospace text-primary">${s.shap_value > 0 ? '+' : ''}${s.shap_value.toFixed(3)}</span></div>
          </div>
        </div>
      `;
    }).join("");
  }
}

function setGauge(barId, textId, pct, htmlVal) {
  const bar = document.getElementById(barId);
  const txt = document.getElementById(textId);
  if (!bar || !txt) return;
  const total = 251.2;
  bar.style.strokeDashoffset = total * (1.0 - Math.max(0, Math.min(1.0, pct)));
  txt.innerHTML = htmlVal;
}

// 5. Alerts Table
async function fetchAlerts() {
  const res = await fetch("/api/alerts");
  if (!res.ok) return;
  const alerts = await res.json();

  const tbody = document.getElementById("alerts-tbody");
  if (!tbody) return;

  if (alerts.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">No active anomalies detected across the fleet.</td></tr>`;
    return;
  }

  tbody.innerHTML = alerts.map(a => {
    let sevBadge = "bg-info text-dark";
    if (a.severity === "CRITICAL") sevBadge = "bg-danger";
    else if (a.severity === "WARNING") sevBadge = "bg-warning text-dark";

    const isResolved = a.status === "RESOLVED";
    const actions = isResolved ? 
      `<span class="badge bg-light text-muted border">RESOLVED</span>` : 
      `<button class="btn btn-sm btn-outline-secondary py-0 px-2 me-1" onclick="acknowledgeAlert('${a.alert_id}')">Ack</button>
       <button class="btn btn-sm btn-outline-danger py-0 px-2" onclick="resolveAlert('${a.alert_id}')">Resolve</button>`;

    return `
      <tr>
        <td class="font-monospace fw-bold">${a.alert_id}</td>
        <td class="fw-semibold">${a.asset_id}</td>
        <td><span class="badge ${sevBadge}">${a.severity}</span></td>
        <td class="font-monospace text-primary">${a.title}</td>
        <td class="small">${a.description}</td>
        <td class="small text-muted font-monospace">${a.timestamp.slice(11, 19)} UTC</td>
        <td>${actions}</td>
      </tr>
    `;
  }).join("");
}

// 6. CMMS Work Orders & HITL Queue (AC-FR-MAIN-001 & AC-FR-XAI-002)
async function fetchWorkOrders() {
  const res = await fetch("/api/work-orders");
  if (!res.ok) return;
  const wos = await res.json();

  const tbody = document.getElementById("cmms-tbody");
  if (!tbody) return;

  if (wos.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No maintenance work orders pending.</td></tr>`;
    return;
  }

  tbody.innerHTML = wos.map(wo => {
    const isPending = wo.status === "PENDING_HITL_APPROVAL";
    const hitlGate = isPending ? 
      `<button class="btn btn-sm btn-primary py-1 px-3 fw-semibold" onclick="approveWorkOrder('${wo.work_order_id}')">
        <i class="bi bi-shield-check me-1"></i> Approve (HITL Gate)
       </button>` : 
      `<span class="badge bg-success-subtle text-success border border-success-subtle px-2 py-1">APPROVED</span>`;

    return `
      <tr>
        <td class="font-monospace fw-bold">${wo.work_order_id}</td>
        <td class="fw-semibold">${wo.asset_id}</td>
        <td><span class="badge ${wo.priority === 'P1' ? 'bg-danger' : 'bg-warning text-dark'}">${wo.priority}</span></td>
        <td class="fw-medium">${wo.title}</td>
        <td class="font-monospace small">${wo.status}</td>
        <td class="text-muted small">${wo.assigned_technician_id || "Unassigned"}</td>
        <td class="small text-muted font-monospace">${wo.created_at.slice(11, 19)} UTC</td>
        <td>${hitlGate}</td>
      </tr>
    `;
  }).join("");
}

// 7. Adaptive Intelligence & Safety Interlock
async function fetchAdaptations() {
  const res = await fetch("/api/adaptations");
  if (!res.ok) return;
  const acts = await res.json();

  const tbody = document.getElementById("adaptive-tbody");
  if (!tbody) return;

  if (acts.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No model adaptations currently pending. Baselines nominal.</td></tr>`;
    return;
  }

  tbody.innerHTML = acts.map(ac => {
    const isPending = ac.status === "PENDING_HITL_APPROVAL";
    const actionCell = isPending ?
      `<button class="btn btn-sm btn-warning py-1 px-2 fw-semibold" onclick="approveAdaptation('${ac.action_id}')">
        Chief Engineer Sign-Off
       </button>` :
      `<span class="badge bg-success-subtle text-success border border-success-subtle">ACTIVE</span>`;

    return `
      <tr>
        <td class="font-monospace fw-bold">${ac.action_id}</td>
        <td>${ac.asset_id}</td>
        <td><span class="badge bg-light text-dark border">${ac.type}</span></td>
        <td class="font-monospace small">${ac.target_metric}</td>
        <td class="font-monospace fw-bold ${ac.percentage_shift < 0 ? 'text-danger' : 'text-success'}">${ac.percentage_shift > 0 ? '+' : ''}${ac.percentage_shift}%</td>
        <td><span class="badge ${ac.requires_hitl ? 'bg-danger' : 'bg-info text-dark'}">${ac.requires_hitl ? 'YES (>10%)' : 'NO (Auto)'}</span></td>
        <td class="font-monospace small">${ac.status}</td>
        <td>${actionCell}</td>
      </tr>
    `;
  }).join("");
}

// 8. Cryptographic Audit Trail
async function fetchAuditChain() {
  const res = await fetch("/api/audit-chain");
  if (!res.ok) return;
  const d = await res.json();

  const badge = document.getElementById("audit-chain-status");
  if (badge) {
    if (d.is_valid) {
      badge.className = "badge bg-success-subtle text-success border border-success-subtle px-3 py-2";
      badge.innerHTML = `<i class="bi bi-shield-check me-1"></i> CHAIN VERIFIED: UNTAMPERED (${d.total_entries} BLOCKS)`;
    } else {
      badge.className = "badge bg-danger-subtle text-danger border border-danger-subtle px-3 py-2";
      badge.innerHTML = `<i class="bi bi-shield-x me-1"></i> CORRUPTION AT BLOCK #${d.corrupted_index}`;
    }
  }

  const tbody = document.getElementById("audit-tbody");
  if (!tbody) return;

  tbody.innerHTML = d.recent_entries.map(e => `
    <tr>
      <td class="fw-bold text-dark">${e.entry_id}</td>
      <td class="text-muted">${e.timestamp.slice(11, 19)} UTC</td>
      <td class="text-primary">${e.actor_id}</td>
      <td class="fw-semibold">${e.action}</td>
      <td>${e.resource_id}</td>
      <td><span class="badge bg-light text-success border">${e.outcome}</span></td>
      <td class="text-muted" title="${e.entry_hash}">${e.entry_hash.slice(0, 16)}...</td>
    </tr>
  `).join("");
}

// ----------------------------------------------------------------------------
// Interactive Simulation & Action Handlers
// ----------------------------------------------------------------------------

async function injectScenario(scenario) {
  const box = document.getElementById("inject-feedback-box");
  box.className = "alert alert-info mt-3 mb-0 small py-2 d-block";
  box.innerHTML = `<div class="spinner-border spinner-border-sm me-1" role="status"></div> Injecting '${scenario}' telemetry into ${currentAssetId}...`;

  try {
    const res = await fetch("/api/telemetry/inject", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ asset_id: currentAssetId, scenario: scenario }),
    });
    const result = await res.json();
    box.className = "alert alert-success mt-3 mb-0 small py-2 d-block";
    box.innerHTML = `<strong>Success:</strong> Telemetry scenario <code>${scenario}</code> ingested. Digital twin state machine & residuals re-evaluated.`;
    loadAllData();
  } catch (err) {
    box.className = "alert alert-danger mt-3 mb-0 small py-2 d-block";
    box.innerText = `Error injecting telemetry: ${err.message}`;
  }
}

async function acknowledgeAlert(alertId) {
  await fetch("/api/alerts/acknowledge", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ alert_id: alertId }),
  });
  loadAllData();
}

async function resolveAlert(alertId) {
  await fetch("/api/alerts/resolve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ alert_id: alertId }),
  });
  loadAllData();
}

async function approveWorkOrder(woId) {
  await fetch("/api/work-orders/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ work_order_id: woId }),
  });
  loadAllData();
}

async function proposeAdaptation(shiftPct) {
  const box = document.getElementById("adapt-feedback-box");
  box.className = "alert alert-warning mt-3 mb-0 small py-2 d-block";
  box.innerText = `Proposing ${shiftPct}% baseline shift...`;

  const res = await fetch("/api/adaptations/propose", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ asset_id: currentAssetId, shift_pct: shiftPct }),
  });
  const data = await res.json();
  if (data.requires_hitl) {
    box.className = "alert alert-danger mt-3 mb-0 small py-2 d-block";
    box.innerHTML = `🛡️ <strong>HITL SAFETY INTERLOCK ACTIVE:</strong> Shift of ${shiftPct}% exceeds ±10% autonomous threshold. Status: <code>${data.status}</code>. Chief Engineer approval required.`;
  } else {
    box.className = "alert alert-success mt-3 mb-0 small py-2 d-block";
    box.innerHTML = `🌿 <strong>Autonomous Adaptation:</strong> Shift of ${shiftPct}% applied safely within operational boundaries.`;
  }
  loadAllData();
}

async function approveAdaptation(actionId) {
  await fetch("/api/adaptations/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action_id: actionId }),
  });
  loadAllData();
}

// ----------------------------------------------------------------------------
// 9. Users & Onboarding Directory Logic
// ----------------------------------------------------------------------------

async function fetchUsers() {
  try {
    const res = await fetch("/api/users");
    if (!res.ok) return;
    const data = await res.json();
    const users = data.users || [];

    const statCount = document.getElementById("stat-onboard-users");
    if (statCount) statCount.innerText = users.length;
    const pillCount = document.getElementById("count-pill-users");
    if (pillCount) pillCount.innerText = users.length;

    const tbody = document.getElementById("directory-users-tbody");
    if (tbody) {
      tbody.innerHTML = users.map(u => {
        let roleBadge = "bg-primary";
        if (u.role === "CHIEF_ENGINEER") roleBadge = "bg-purple text-white";
        else if (u.role === "SECURITY_ADMIN") roleBadge = "bg-danger";
        else if (u.role === "VIEWER") roleBadge = "bg-secondary";

        const permsHtml = (u.permissions || []).slice(0, 3).map(p => 
          `<span class="badge bg-light text-dark border me-1">${p}</span>`
        ).join("") + ((u.permissions && u.permissions.length > 3) ? `<span class="badge bg-light text-muted border">+${u.permissions.length - 3}</span>` : '');

        return `
          <tr>
            <td class="font-monospace fw-bold text-dark">${u.user_id}</td>
            <td class="fw-semibold">${u.name}</td>
            <td class="text-muted small">${u.email}</td>
            <td><span class="badge ${roleBadge}">${u.role}</span></td>
            <td class="small font-monospace">${u.tenant_id}</td>
            <td><code class="user-select-all small">${u.token || "TOK-ACTIVE"}</code></td>
            <td>${permsHtml}</td>
            <td><span class="badge bg-success-subtle text-success border border-success-subtle"><i class="bi bi-check-circle me-1"></i>${u.status}</span></td>
          </tr>
        `;
      }).join("");
    }
  } catch (err) {
    console.error("Error fetching users:", err);
  }
}

function initOnboardingForms() {
  // 1. User Form
  const formUser = document.getElementById("form-onboard-user");
  if (formUser) {
    formUser.addEventListener("submit", async (e) => {
      e.preventDefault();
      const alertBox = document.getElementById("user-onboard-alert");
      alertBox.className = "alert alert-info mt-3 small py-2 d-block";
      alertBox.innerHTML = `<div class="spinner-border spinner-border-sm me-1"></div> Provisioning user and generating HMAC token...`;

      try {
        const payload = {
          name: document.getElementById("user-name").value.trim(),
          email: document.getElementById("user-email").value.trim(),
          role: document.getElementById("user-role").value,
          tenant_id: document.getElementById("user-tenant").value.trim(),
        };
        const res = await fetch("/api/onboarding/user", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.status === "SUCCESS") {
          alertBox.className = "alert alert-success mt-3 small py-2 d-block";
          alertBox.innerHTML = `<strong>Success:</strong> User <code>${data.user.user_id}</code> (${data.user.name}) provisioned with role <code>${data.user.role}</code>.<br>Issued Token: <code class="user-select-all">${data.user.token}</code>`;
          formUser.reset();
          document.getElementById("user-tenant").value = "ORG-HELIOS-GLOBAL";
          fetchUsers();
          fetchAuditChain();
        } else {
          alertBox.className = "alert alert-danger mt-3 small py-2 d-block";
          alertBox.innerText = `Error: ${data.message || "Failed to onboard user"}`;
        }
      } catch (err) {
        alertBox.className = "alert alert-danger mt-3 small py-2 d-block";
        alertBox.innerText = `Network error: ${err.message}`;
      }
    });
  }

  // 2. Facility Form
  const formFacility = document.getElementById("form-onboard-facility");
  if (formFacility) {
    formFacility.addEventListener("submit", async (e) => {
      e.preventDefault();
      const alertBox = document.getElementById("facility-onboard-alert");
      alertBox.className = "alert alert-info mt-3 small py-2 d-block";
      alertBox.innerHTML = `<div class="spinner-border spinner-border-sm me-1"></div> Registering generation facility topology...`;

      try {
        const payload = {
          name: document.getElementById("facility-name").value.trim(),
          facility_id: document.getElementById("facility-id").value.trim().toUpperCase(),
          rated_capacity_mw: parseFloat(document.getElementById("facility-capacity").value),
          technology: document.getElementById("facility-tech").value,
          latitude: parseFloat(document.getElementById("facility-lat").value),
          longitude: parseFloat(document.getElementById("facility-lng").value),
        };
        const res = await fetch("/api/onboarding/facility", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.status === "SUCCESS") {
          alertBox.className = "alert alert-success mt-3 small py-2 d-block";
          alertBox.innerHTML = `<strong>Success:</strong> Facility <code>${data.entity_id}</code> successfully registered and added to portfolio.`;
          formFacility.reset();
          fetchSites();
          fetchOverview();
          fetchAuditChain();
        } else {
          alertBox.className = "alert alert-danger mt-3 small py-2 d-block";
          alertBox.innerText = `Error: ${data.message || "Failed to onboard facility"}`;
        }
      } catch (err) {
        alertBox.className = "alert alert-danger mt-3 small py-2 d-block";
        alertBox.innerText = `Network error: ${err.message}`;
      }
    });
  }

  // 3. Device Form
  const formDevice = document.getElementById("form-onboard-device");
  if (formDevice) {
    formDevice.addEventListener("submit", async (e) => {
      e.preventDefault();
      const alertBox = document.getElementById("device-onboard-alert");
      alertBox.className = "alert alert-info mt-3 small py-2 d-block";
      alertBox.innerHTML = `<div class="spinner-border spinner-border-sm me-1"></div> Provisioning device, generating HMAC secret & registering sensors...`;

      try {
        const payload = {
          name: document.getElementById("device-name").value.trim(),
          device_id: document.getElementById("device-id").value.trim().toUpperCase(),
          facility_id: document.getElementById("device-facility").value,
          asset_type: document.getElementById("device-type").value,
          rated_power_kw: parseFloat(document.getElementById("device-power").value),
          model: document.getElementById("device-model").value.trim(),
          provision_digital_twin: document.getElementById("device-twin").checked,
        };
        const res = await fetch("/api/onboarding/device", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.status === "SUCCESS") {
          alertBox.className = "alert alert-success mt-3 small py-2 d-block";
          alertBox.innerHTML = `<strong>Success:</strong> Device <code>${data.entity_id}</code> onboarded with ${data.details.sensors_count} telemetry channels.<br>Edge Secret: <code class="user-select-all">${data.details.device_secret}</code>`;
          formDevice.reset();
          fetchAssets();
          fetchSites();
          fetchOverview();
          fetchAuditChain();
        } else {
          alertBox.className = "alert alert-danger mt-3 small py-2 d-block";
          alertBox.innerText = `Error: ${data.message || "Failed to onboard device"}`;
        }
      } catch (err) {
        alertBox.className = "alert alert-danger mt-3 small py-2 d-block";
        alertBox.innerText = `Network error: ${err.message}`;
      }
    });
  }
}

function switchTab(tabId) {
  const triggerEl = document.querySelector(`button[data-bs-target="#${tabId}"]`);
  if (triggerEl && typeof bootstrap !== "undefined") {
    const tab = bootstrap.Tab.getOrCreateInstance(triggerEl);
    tab.show();
  }
}
