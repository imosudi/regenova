/* ==========================================================================
   REGENOVA Backoffice - Application Controller Logic
   Requirement: FR-UI-001 / AC-FR-UI-001
   Strict Bootstrap 5.3 Light Theme without dark SCADA override
   Interfaces with REST API on https://api.regenova.cloud
   ========================================================================== */

const API_BASE = (window.REGENOVA_API_URL !== undefined)
  ? window.REGENOVA_API_URL
  : (window.location.hostname === 'backoffice.regenova.cloud' ? 'https://api.regenova.cloud' : '');

const ADMIN_AUTH_KEY = "regenova_admin_session";

function getStoredAdminAuth() {
  const raw = sessionStorage.getItem(ADMIN_AUTH_KEY) || localStorage.getItem(ADMIN_AUTH_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch (e) {
    return null;
  }
}

function setStoredAdminAuth(authData, remember) {
  const serialized = JSON.stringify(authData);
  sessionStorage.setItem(ADMIN_AUTH_KEY, serialized);
  if (remember) {
    localStorage.setItem(ADMIN_AUTH_KEY, serialized);
  } else {
    localStorage.removeItem(ADMIN_AUTH_KEY);
  }
}

function clearStoredAdminAuth() {
  sessionStorage.removeItem(ADMIN_AUTH_KEY);
  localStorage.removeItem(ADMIN_AUTH_KEY);
}

function apiFetch(endpoint, options = {}) {
  const url = (typeof endpoint === 'string' && endpoint.startsWith('http'))
    ? endpoint
    : `${API_BASE}${endpoint}`;

  const headers = Object.assign({}, options.headers || {});
  const auth = getStoredAdminAuth();
  if (auth && auth.token) {
    headers["Authorization"] = `Bearer ${auth.token}`;
    headers["X-Admin-Token"] = auth.token;
  }

  return fetch(url, { ...options, headers }).then((res) => {
    if (res.status === 401 && endpoint !== "/api/admin/login") {
      clearStoredAdminAuth();
      lockConsole();
    }
    return res;
  });
}

let allTenants = [];
let allUsers = [];
let pollTimer = null;

const CANONICAL_21_TABLES = [
  "organisations", "portfolios", "sites", "energy_systems", "assets",
  "users", "roles", "permissions", "user_roles", "telemetry_observations",
  "digital_twin_states", "anomaly_events", "health_indices", "predictive_rul",
  "work_orders", "work_order_actions", "yield_projections", "compliance_registry",
  "security_audit_log", "adaptation_records", "ledger_blocks"
];

document.addEventListener("DOMContentLoaded", () => {
  initAdminAuthGateway();
  initSidebarInteractions();
  initModalsAndForms();
  updateUtcClock();
  setInterval(updateUtcClock, 1000);

  const auth = getStoredAdminAuth();
  if (auth && auth.token) {
    unlockConsole(auth);
  } else {
    lockConsole();
  }
});

window.togglePasswordVisibility = function() {
  const p = document.getElementById("loginPassword");
  const icon = document.getElementById("togglePasswordIcon");
  const chk = document.getElementById("checkShowPassword");
  if (!p) return;
  const isPass = (p.type === "password");
  p.type = isPass ? "text" : "password";
  if (icon) {
    icon.className = isPass ? "bi bi-eye-slash-fill text-primary" : "bi bi-eye text-muted";
  }
  if (chk) {
    chk.checked = isPass;
  }
};

window.handleAdminLoginSubmit = async function(e) {
  if (e) e.preventDefault();
  const alertBox = document.getElementById("loginAlert");
  const emailInput = document.getElementById("loginEmail");
  const passInput = document.getElementById("loginPassword");
  const submitBtn = document.getElementById("btnLoginSubmit");
  const rememberInput = document.getElementById("rememberMe");

  const email = emailInput ? emailInput.value.trim() : "";
  const password = passInput ? passInput.value : "";
  const remember = rememberInput ? rememberInput.checked : true;

  if (!email || !password) {
    if (alertBox) {
      alertBox.className = "alert alert-warning py-2 px-3 small";
      alertBox.innerText = "Please enter both administrator email and password.";
      alertBox.classList.remove("d-none");
    }
    return;
  }

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Authenticating...`;
  }
  if (alertBox) alertBox.classList.add("d-none");

  try {
    const res = await apiFetch("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json();
    if (res.ok && data.status === "SUCCESS") {
      setStoredAdminAuth(data, remember);
      unlockConsole(data);
    } else {
      if (alertBox) {
        alertBox.className = "alert alert-danger py-2 px-3 small";
        alertBox.innerText = data.message || "Invalid administrator credentials. Access denied.";
        alertBox.classList.remove("d-none");
      }
    }
  } catch (err) {
    console.error("Login request failed:", err);
    if (alertBox) {
      alertBox.className = "alert alert-danger py-2 px-3 small";
      alertBox.innerText = "Authentication service error. Please try again.";
      alertBox.classList.remove("d-none");
    }
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `<i class="bi bi-box-arrow-in-right me-2"></i><span>Authenticate & Access Console</span>`;
    }
  }
};

function initAdminAuthGateway() {
  const form = document.getElementById("formAdminLogin");
  const toggleBtn = document.getElementById("togglePasswordBtn");
  const checkShow = document.getElementById("checkShowPassword");

  if (toggleBtn) {
    toggleBtn.onclick = window.togglePasswordVisibility;
  }
  if (checkShow) {
    checkShow.onchange = window.togglePasswordVisibility;
  }
  if (form) {
    form.onsubmit = window.handleAdminLoginSubmit;
  }
}

function unlockConsole(authData) {
  const loginScreen = document.getElementById("backofficeLoginScreen");
  const appLayout = document.getElementById("backofficeAppLayout");

  if (loginScreen) loginScreen.classList.add("d-none");
  if (appLayout) appLayout.classList.remove("d-none");

  const email = (authData && authData.user && authData.user.email) ? authData.user.email : "imosudi@gmail.com";
  const topbarEmail = document.getElementById("topbar-admin-email");
  const sidebarEmail = document.getElementById("sidebar-admin-email");

  if (topbarEmail) topbarEmail.innerText = email;
  if (sidebarEmail) sidebarEmail.innerText = email;

  // Load initial dataset
  loadAllBackofficeData();
  // Ensure polling timer is active
  if (!pollTimer) {
    pollTimer = setInterval(loadAllBackofficeData, 4000);
  }
}

function lockConsole() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  const loginScreen = document.getElementById("backofficeLoginScreen");
  const appLayout = document.getElementById("backofficeAppLayout");

  if (appLayout) appLayout.classList.add("d-none");
  if (loginScreen) loginScreen.classList.remove("d-none");

  const alertBox = document.getElementById("loginAlert");
  if (alertBox) alertBox.classList.add("d-none");
}

function handleAdminLogout() {
  clearStoredAdminAuth();
  lockConsole();
}

async function loadAllBackofficeData() {
  try {
    await Promise.all([
      fetchTenantsAndOverview(),
      fetchGlobalUsers(),
      fetchDatabaseStatus(),
      fetchAuditTrail(),
      fetchHitlWorkOrders(),
    ]);
  } catch (err) {
    console.error("Backoffice polling error:", err);
    updateApiStatusBadge(false);
  }
}

function updateApiStatusBadge(isOnline) {
  const badge = document.getElementById("topbar-api-badge");
  if (!badge) return;
  if (isOnline) {
    badge.className = "badge bg-success-subtle text-success border border-success-subtle px-3 py-2 rounded-pill d-none d-md-inline-flex align-items-center gap-1";
    badge.innerHTML = `<span class="pulse-live"></span><span class="fw-semibold font-monospace" style="font-size: 0.72rem;">API ONLINE (1 Hz)</span>`;
  } else {
    badge.className = "badge bg-danger-subtle text-danger border border-danger-subtle px-3 py-2 rounded-pill d-none d-md-inline-flex align-items-center gap-1";
    badge.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-1"></i><span class="fw-semibold font-monospace" style="font-size: 0.72rem;">API OFFLINE</span>`;
  }
}

// ----------------------------------------------------------------------------
// 1. Tenants & Global Overview Aggregation
// ----------------------------------------------------------------------------

async function fetchTenantsAndOverview() {
  try {
    const res = await apiFetch("/api/tenants");
    if (!res.ok) {
      updateApiStatusBadge(false);
      return;
    }
    updateApiStatusBadge(true);
    const data = await res.json();
    allTenants = data.tenants || [];

    // Update Tenant Count Badges
    const badgeCount = document.getElementById("badge-tenants-count");
    if (badgeCount) badgeCount.innerText = allTenants.length;
    const kpiTenants = document.getElementById("kpi-tenants-count");
    if (kpiTenants) kpiTenants.innerText = allTenants.length;

    // Populate Modals & Filter dropdowns
    populateTenantSelectors();

    // Query per-tenant overviews to aggregate cross-tenant metrics
    const tenantOverviews = await Promise.all(
      allTenants.map(async (t) => {
        try {
          const oRes = await apiFetch("/api/overview", {
            headers: { "X-Tenant-ID": t.tenant_id }
          });
          if (oRes.ok) {
            return await oRes.json();
          }
        } catch (e) {
          console.warn(`Failed overview for tenant ${t.tenant_id}:`, e);
        }
        return null;
      })
    );

    let globalCapacity = 0;
    let globalGeneration = 0;
    let globalSites = 0;
    let globalAssets = 0;
    let globalAlerts = 0;
    let globalCo2 = 0;
    let healthWeightedSum = 0;
    let validOverviews = 0;

    tenantOverviews.forEach((ov, idx) => {
      const t = allTenants[idx];
      if (ov) {
        globalCapacity += ov.total_capacity_mw || t.capacity_mw || 0;
        globalGeneration += ov.total_generation_mw || 0;
        globalSites += ov.total_sites || t.sites_count || 0;
        globalAssets += ov.total_assets || t.assets_count || 0;
        globalAlerts += ov.active_alerts_count || t.active_alerts_count || 0;
        globalCo2 += ov.co2_avoided_tons || 0;
        if (ov.fleet_health_index) {
          healthWeightedSum += ov.fleet_health_index;
          validOverviews++;
        }
      } else {
        globalCapacity += t.capacity_mw || 0;
        globalSites += t.sites_count || 0;
        globalAssets += t.assets_count || 0;
        globalAlerts += t.active_alerts_count || 0;
      }
    });

    const avgHealth = validOverviews > 0 ? (healthWeightedSum / validOverviews) : 98.4;
    const hourlyRevenue = globalGeneration * 1000 * 0.085; // $85/MWh average PPA
    const hourlyLoss = Math.max(0, (globalCapacity - globalGeneration) * 1000 * 0.085);

    // Update Global KPIs
    document.getElementById("kpi-total-capacity").innerHTML = `${globalCapacity.toFixed(1)} <small class="fs-6 text-muted">MW</small>`;
    document.getElementById("kpi-total-generation").innerText = `${globalGeneration.toFixed(2)} MW`;
    document.getElementById("kpi-fleet-health").innerHTML = `${avgHealth.toFixed(1)} <small class="fs-6 text-muted">/ 100</small>`;
    document.getElementById("kpi-assets-count").innerHTML = `${globalAssets} <small class="fs-6 text-muted">units</small>`;
    document.getElementById("kpi-sites-count").innerText = globalSites;
    document.getElementById("kpi-revenue-flow").innerHTML = `$${hourlyRevenue.toFixed(2)} <small class="fs-6 text-muted">/ hr</small>`;
    document.getElementById("kpi-revenue-loss").innerText = `$${hourlyLoss.toFixed(2)} / hr`;
    document.getElementById("kpi-active-alerts").innerText = globalAlerts;
    document.getElementById("kpi-co2-tons").innerHTML = `${globalCo2.toFixed(1)} <small class="fs-6 text-muted">Tons</small>`;

    // Render Cross-Tenant Grid
    renderCrossTenantGrid(tenantOverviews);

    // Render Tenants Management Table
    renderTenantsTable(tenantOverviews);

  } catch (err) {
    console.error("Error in fetchTenantsAndOverview:", err);
  }
}

function populateTenantSelectors() {
  // 1. User Filter Select
  const filterSelect = document.getElementById("backoffice-filter-tenant");
  if (filterSelect) {
    const currentVal = filterSelect.value || "ALL";
    filterSelect.innerHTML = `<option value="ALL">All Tenants</option>` + allTenants.map(t =>
      `<option value="${t.tenant_id}" ${t.tenant_id === currentVal ? 'selected' : ''}>${t.name} (${t.tenant_id})</option>`
    ).join("");
  }

  // 2. User Create Modal Tenant Select
  const modalSelect = document.getElementById("modal-user-tenant");
  if (modalSelect) {
    const currentVal = modalSelect.value || (allTenants[0] ? allTenants[0].tenant_id : "");
    modalSelect.innerHTML = allTenants.map(t =>
      `<option value="${t.tenant_id}" ${t.tenant_id === currentVal ? 'selected' : ''}>${t.name} (${t.tenant_id})</option>`
    ).join("");
  }
}

function renderCrossTenantGrid(overviews) {
  const container = document.getElementById("cross-tenant-grid");
  if (!container) return;

  container.innerHTML = allTenants.map((t, idx) => {
    const ov = overviews[idx] || {};
    const genMw = (ov.total_generation_mw !== undefined) ? ov.total_generation_mw.toFixed(1) : "--";
    const capMw = t.capacity_mw !== undefined ? t.capacity_mw.toFixed(1) : "--";
    const health = (ov.fleet_health_index !== undefined) ? ov.fleet_health_index.toFixed(1) : "98.5";
    const alerts = (ov.active_alerts_count !== undefined) ? ov.active_alerts_count : (t.active_alerts_count || 0);

    return `
      <div class="col-12 col-md-6 col-xl-4">
        <div class="card card-reamp h-100 p-3 border-top border-3 border-primary">
          <div class="d-flex justify-content-between align-items-start mb-2">
            <div>
              <span class="badge badge-tenant-pill mb-1">${t.tenant_id}</span>
              <h6 class="fw-bold text-dark m-0">${t.name}</h6>
            </div>
            <span class="badge bg-light text-dark border small">${t.billing_tier || 'ENTERPRISE'}</span>
          </div>
          <div class="row g-2 mt-2 pt-2 border-top small">
            <div class="col-6">
              <span class="text-muted">Generation:</span>
              <div class="fw-bold text-success">${genMw} / ${capMw} MW</div>
            </div>
            <div class="col-6">
              <span class="text-muted">Health (AHI):</span>
              <div class="fw-bold text-primary">${health} / 100</div>
            </div>
            <div class="col-6">
              <span class="text-muted">Facilities & Assets:</span>
              <div class="fw-semibold text-dark">${t.sites_count} sites • ${t.assets_count} assets</div>
            </div>
            <div class="col-6">
              <span class="text-muted">Active Alerts:</span>
              <div class="fw-bold ${alerts > 0 ? 'text-danger' : 'text-muted'}">${alerts} active</div>
            </div>
          </div>
          <div class="mt-3 pt-2 border-top d-flex justify-content-between align-items-center">
            <span class="badge badge-status-active"><i class="bi bi-shield-check me-1"></i>Isolated Partition</span>
            <a href="https://regenova.cloud/" target="_blank" class="btn btn-xs btn-outline-primary py-0 px-2 small" style="font-size: 0.72rem;">
              <i class="bi bi-box-arrow-up-right me-1"></i>View Sites
            </a>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

function renderTenantsTable(overviews) {
  const tbody = document.getElementById("tenants-table-tbody");
  if (!tbody) return;

  tbody.innerHTML = allTenants.map((t, idx) => {
    const ov = overviews[idx] || {};
    const cap = t.capacity_mw || (ov.total_capacity_mw || 0);
    const alerts = (ov.active_alerts_count !== undefined) ? ov.active_alerts_count : (t.active_alerts_count || 0);

    return `
      <tr>
        <td class="font-monospace fw-bold text-dark">${t.tenant_id}</td>
        <td class="fw-semibold">${t.name}</td>
        <td><span class="badge bg-light text-dark border font-monospace">${t.code || '--'}</span></td>
        <td><span class="badge bg-indigo-subtle text-primary border border-primary-subtle">${t.billing_tier || 'ENTERPRISE'}</span></td>
        <td class="fw-bold text-primary">${cap.toFixed(1)} MW</td>
        <td>${t.sites_count || 0} sites</td>
        <td>${t.assets_count || 0} units</td>
        <td>${t.users_count || 0} users</td>
        <td>
          <span class="badge ${alerts > 0 ? 'bg-danger' : 'bg-light text-muted border'}">${alerts}</span>
        </td>
        <td><span class="badge badge-status-active">${t.status || 'ACTIVE'}</span></td>
        <td class="text-end">
          <a href="https://regenova.cloud/" target="_blank" class="btn btn-xs btn-outline-primary py-1 px-2" style="font-size: 0.75rem;">
            <i class="bi bi-box-arrow-up-right me-1"></i>Access Portal
          </a>
        </td>
      </tr>
    `;
  }).join("");
}

// ----------------------------------------------------------------------------
// 2. Global User Directory & RBAC Administration
// ----------------------------------------------------------------------------

async function fetchGlobalUsers() {
  try {
    const res = await apiFetch("/api/users?all=true");
    if (!res.ok) return;
    const data = await res.json();
    allUsers = data.users || [];

    const badgeUsers = document.getElementById("badge-users-count");
    if (badgeUsers) badgeUsers.innerText = allUsers.length;

    renderBackofficeUsers();
  } catch (err) {
    console.error("Error fetching global users:", err);
  }
}

function renderBackofficeUsers() {
  const filterTenantEl = document.getElementById("backoffice-filter-tenant");
  const filterSearchEl = document.getElementById("backoffice-filter-search");

  const filterTenant = filterTenantEl ? filterTenantEl.value : "ALL";
  const filterSearch = (filterSearchEl ? filterSearchEl.value : "").toLowerCase().trim();

  const filtered = allUsers.filter(u => {
    if (filterTenant !== "ALL" && u.tenant_id !== filterTenant) return false;
    if (filterSearch) {
      const matchName = (u.name || "").toLowerCase().includes(filterSearch);
      const matchEmail = (u.email || "").toLowerCase().includes(filterSearch);
      const matchId = (u.user_id || "").toLowerCase().includes(filterSearch);
      if (!matchName && !matchEmail && !matchId) return false;
    }
    return true;
  });

  const tbody = document.getElementById("backoffice-users-tbody");
  if (!tbody) return;

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4"><i class="bi bi-person-x fs-3 d-block mb-1"></i>No users match the selected filter.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(u => {
    const isSuspended = (u.status === "SUSPENDED");
    const statusBadge = isSuspended
      ? `<span class="badge badge-status-suspended"><i class="bi bi-dash-circle me-1"></i>SUSPENDED</span>`
      : `<span class="badge badge-status-active"><i class="bi bi-check-circle me-1"></i>ACTIVE</span>`;

    const permsHtml = (u.permissions || []).slice(0, 2).map(p =>
      `<span class="badge bg-light text-dark border me-1" style="font-size: 0.68rem;">${p}</span>`
    ).join("") + ((u.permissions && u.permissions.length > 2) ? `<span class="badge bg-light text-muted border" style="font-size: 0.68rem;">+${u.permissions.length - 2}</span>` : '');

    const toggleStatusAction = isSuspended
      ? `<button class="btn btn-xs btn-outline-success py-0 px-2 me-1" onclick="toggleUserStatus('${u.user_id}', 'ACTIVE')" title="Reactivate user access" style="font-size: 0.72rem;"><i class="bi bi-play-circle me-1"></i>Activate</button>`
      : `<button class="btn btn-xs btn-outline-warning py-0 px-2 me-1" onclick="toggleUserStatus('${u.user_id}', 'SUSPENDED')" title="Suspend user access" style="font-size: 0.72rem;"><i class="bi bi-pause-circle me-1"></i>Suspend</button>`;

    return `
      <tr>
        <td class="font-monospace fw-bold text-dark">${u.user_id}</td>
        <td>
          <div class="fw-semibold text-dark">${u.name}</div>
          <div class="text-muted small">${u.email}</div>
        </td>
        <td><span class="badge badge-tenant-pill">${u.tenant_id}</span></td>
        <td>
          <select class="form-select form-select-sm py-0 px-2 fw-semibold" style="font-size: 0.75rem; width: auto;" onchange="updateUserRole('${u.user_id}', this.value)">
            <option value="OPERATOR" ${u.role === 'OPERATOR' ? 'selected' : ''}>Operator</option>
            <option value="CHIEF_ENGINEER" ${u.role === 'CHIEF_ENGINEER' ? 'selected' : ''}>Chief Engineer</option>
            <option value="SECURITY_ADMIN" ${u.role === 'SECURITY_ADMIN' ? 'selected' : ''}>Security Admin</option>
            <option value="VIEWER" ${u.role === 'VIEWER' ? 'selected' : ''}>Viewer</option>
          </select>
        </td>
        <td>${statusBadge}</td>
        <td>
          <code class="user-select-all small">${(u.token || "TOK-ACTIVE").substring(0, 14)}...</code>
        </td>
        <td>${permsHtml}</td>
        <td class="text-end">
          <div class="d-inline-flex align-items-center">
            ${toggleStatusAction}
            <button class="btn btn-xs btn-outline-primary py-0 px-2" onclick="regenerateUserToken('${u.user_id}')" title="Regenerate HMAC security token" style="font-size: 0.72rem;">
              <i class="bi bi-arrow-repeat me-1"></i>New Token
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

async function updateUserRole(userId, newRole) {
  try {
    const res = await apiFetch("/api/users/update-role", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, role: newRole }),
    });
    const data = await res.json();
    if (data.status === "SUCCESS") {
      fetchGlobalUsers();
      fetchAuditTrail();
    } else {
      alert(`Role update failed: ${data.message || 'Unknown error'}`);
      fetchGlobalUsers();
    }
  } catch (err) {
    alert(`Network error updating role: ${err.message}`);
  }
}

async function toggleUserStatus(userId, newStatus) {
  try {
    const res = await apiFetch("/api/users/toggle-status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, status: newStatus }),
    });
    const data = await res.json();
    if (data.status === "SUCCESS") {
      fetchGlobalUsers();
      fetchAuditTrail();
    } else {
      alert(`Status toggle failed: ${data.message || 'Unknown error'}`);
    }
  } catch (err) {
    alert(`Network error toggling status: ${err.message}`);
  }
}

async function regenerateUserToken(userId) {
  if (!confirm(`Regenerate HMAC security token for ${userId}? Existing sessions will be revoked.`)) {
    return;
  }
  try {
    const res = await apiFetch("/api/users/regenerate-token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId }),
    });
    const data = await res.json();
    if (data.status === "SUCCESS") {
      const token = data.token || data.new_token;
      alert(`New HMAC Token issued for ${userId}:\n\n${token}`);
      fetchGlobalUsers();
      fetchAuditTrail();
    } else {
      alert(`Token regeneration failed: ${data.message || 'Unknown error'}`);
    }
  } catch (err) {
    alert(`Network error regenerating token: ${err.message}`);
  }
}

// ----------------------------------------------------------------------------
// 3. Infrastructure & Database Diagnostics
// ----------------------------------------------------------------------------

async function fetchDatabaseStatus() {
  try {
    const res = await apiFetch("/api/database/status");
    if (!res.ok) return;
    const d = await res.json();

    const hostEl = document.getElementById("infra-db-host");
    if (hostEl) hostEl.innerText = d.host || "db.regenova.cloud";
    const portEl = document.getElementById("infra-db-port");
    if (portEl) portEl.innerText = d.port || "5432";
    const nameEl = document.getElementById("infra-db-name");
    if (nameEl) nameEl.innerText = d.dbname || "regenova_db";
    const userEl = document.getElementById("infra-db-user");
    if (userEl) userEl.innerText = d.user || "regenova_db";
    const tablesEl = document.getElementById("infra-db-tables");
    if (tablesEl) tablesEl.innerText = d.tables_count || 21;

    // Render Canonical Tables Grid
    const container = document.getElementById("canonical-tables-list");
    if (container) {
      container.innerHTML = CANONICAL_21_TABLES.map(table => `
        <div class="col-12 col-sm-6 col-md-4 col-xl-3">
          <div class="p-2 bg-light border rounded d-flex align-items-center justify-content-between">
            <span class="text-dark fw-semibold"><i class="bi bi-file-earmark-spreadsheet me-1 text-primary"></i>${table}</span>
            <span class="badge bg-success-subtle text-success border border-success-subtle" style="font-size: 0.65rem;">RLS</span>
          </div>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Error fetching DB status:", err);
  }
}

// ----------------------------------------------------------------------------
// 4. Cryptographic Audit Ledger
// ----------------------------------------------------------------------------

async function fetchAuditTrail() {
  try {
    const res = await apiFetch("/api/audit-chain");
    if (!res.ok) return;
    const d = await res.json();
    const entries = d.recent_entries || [];

    const tbody = document.getElementById("backoffice-audit-tbody");
    if (!tbody) return;

    if (entries.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-3">No audit entries found.</td></tr>`;
      return;
    }

    tbody.innerHTML = entries.map(e => `
      <tr>
        <td class="fw-bold text-dark">#${e.sequence_id}</td>
        <td class="text-muted">${e.timestamp.replace('T', ' ').substring(0, 19)}</td>
        <td><span class="badge bg-dark text-white">${e.action}</span></td>
        <td><span class="badge bg-light text-dark border">${e.actor_id}</span></td>
        <td><span class="badge badge-tenant-pill">${e.tenant_id}</span></td>
        <td class="text-truncate" style="max-width: 220px;" title="${JSON.stringify(e.payload_summary)}">
          <code>${JSON.stringify(e.payload_summary)}</code>
        </td>
        <td title="${e.previous_hash}"><code>${(e.previous_hash || '').substring(0, 10)}...</code></td>
        <td title="${e.block_hash}"><code class="text-success fw-bold">${(e.block_hash || '').substring(0, 12)}...</code></td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Error fetching audit trail:", err);
  }
}

// ----------------------------------------------------------------------------
// 5. HITL Approvals Queue
// ----------------------------------------------------------------------------

async function fetchHitlWorkOrders() {
  try {
    const res = await apiFetch("/api/work-orders");
    if (!res.ok) return;
    const orders = await res.json();
    const pending = (orders || []).filter(o => o.status === "PENDING_HITL_APPROVAL" || o.status === "DISPATCHED");

    const badgeCount = document.getElementById("badge-hitl-count");
    if (badgeCount) badgeCount.innerText = pending.length;

    const tbody = document.getElementById("backoffice-hitl-tbody");
    if (!tbody) return;

    if (pending.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4"><i class="bi bi-check2-circle text-success fs-3 d-block mb-1"></i>No work orders requiring immediate HITL approval.</td></tr>`;
      return;
    }

    tbody.innerHTML = pending.map(w => `
      <tr>
        <td class="font-monospace fw-bold text-dark">${w.order_id}</td>
        <td class="fw-semibold">${w.asset_id}</td>
        <td><span class="badge badge-tenant-pill">${w.tenant_id || 'ORG-HELIOS-GLOBAL'}</span></td>
        <td><span class="badge bg-danger">${w.urgency || 'HIGH'}</span></td>
        <td class="text-dark small">${w.action_summary || w.procedure || 'Emergency inspection'}</td>
        <td class="fw-bold text-danger">$${(w.estimated_cost_usd || 1250).toFixed(2)}</td>
        <td><span class="badge bg-warning-subtle text-dark border border-warning-subtle">${w.status}</span></td>
        <td class="text-end">
          <button class="btn btn-xs btn-success py-1 px-2" onclick="approveHitlOrder('${w.order_id}')" style="font-size: 0.75rem;">
            <i class="bi bi-check-circle me-1"></i>Approve & Dispatch
          </button>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Error fetching HITL work orders:", err);
  }
}

async function approveHitlOrder(orderId) {
  try {
    const res = await apiFetch("/api/work-orders/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order_id: orderId, reviewer_id: "SECURITY_ADMIN" }),
    });
    const data = await res.json();
    alert(`Work order ${orderId} approved for dispatch.`);
    fetchHitlWorkOrders();
    fetchAuditTrail();
  } catch (err) {
    alert(`Error approving work order: ${err.message}`);
  }
}

// ----------------------------------------------------------------------------
// 6. Modals & Forms Initialization
// ----------------------------------------------------------------------------

function initModalsAndForms() {
  // 1. Tenant Enrolment Form
  const formTenant = document.getElementById("form-backoffice-enroll-tenant");
  if (formTenant) {
    formTenant.addEventListener("submit", async (e) => {
      e.preventDefault();
      const alertBox = document.getElementById("tenant-enroll-alert");
      const btnSubmit = document.getElementById("btn-backoffice-enroll-submit");

      alertBox.className = "alert alert-danger small d-none mb-3";
      btnSubmit.disabled = true;
      btnSubmit.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Enrolling...`;

      try {
        const payload = {
          tenant_id: document.getElementById("backoffice-tenant-id").value.trim().toUpperCase(),
          name: document.getElementById("backoffice-tenant-name").value.trim(),
          code: document.getElementById("backoffice-tenant-code").value.trim().toUpperCase(),
          billing_tier: document.getElementById("backoffice-tenant-tier").value,
          admin_name: document.getElementById("backoffice-admin-name").value.trim(),
          admin_email: document.getElementById("backoffice-admin-email").value.trim(),
        };

        const res = await apiFetch("/api/onboarding/tenant", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();

        if (data.status === "SUCCESS") {
          formTenant.reset();
          const modalEl = document.getElementById("modalEnrollTenant");
          const modalInstance = bootstrap.Modal.getInstance(modalEl);
          if (modalInstance) modalInstance.hide();

          await fetchTenantsAndOverview();
          fetchGlobalUsers();
          fetchAuditTrail();
        } else {
          alertBox.className = "alert alert-danger small d-block mb-3";
          alertBox.innerText = `Enrolment failed: ${data.message || 'Unknown error'}`;
        }
      } catch (err) {
        alertBox.className = "alert alert-danger small d-block mb-3";
        alertBox.innerText = `Network error: ${err.message}`;
      } finally {
        btnSubmit.disabled = false;
        btnSubmit.innerHTML = `<i class="bi bi-shield-check me-1"></i> Enrol Organization`;
      }
    });
  }

  // 2. User Provisioning Form
  const formUser = document.getElementById("form-backoffice-create-user");
  if (formUser) {
    formUser.addEventListener("submit", async (e) => {
      e.preventDefault();
      const alertBox = document.getElementById("user-create-alert");
      const btnSubmit = document.getElementById("btn-backoffice-user-submit");

      alertBox.className = "alert alert-danger small d-none mb-3";
      btnSubmit.disabled = true;
      btnSubmit.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Provisioning...`;

      try {
        const payload = {
          name: document.getElementById("modal-user-name").value.trim(),
          email: document.getElementById("modal-user-email").value.trim(),
          role: document.getElementById("modal-user-role").value,
          tenant_id: document.getElementById("modal-user-tenant").value.trim(),
        };

        const res = await apiFetch("/api/onboarding/user", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();

        if (data.status === "SUCCESS") {
          formUser.reset();
          const modalEl = document.getElementById("modalCreateUser");
          const modalInstance = bootstrap.Modal.getInstance(modalEl);
          if (modalInstance) modalInstance.hide();

          alert(`User ${data.user.user_id} (${data.user.name}) provisioned under ${payload.tenant_id}.\n\nIssued Token: ${data.user.token}`);
          fetchGlobalUsers();
          fetchAuditTrail();
        } else {
          alertBox.className = "alert alert-danger small d-block mb-3";
          alertBox.innerText = `Provisioning failed: ${data.message || 'Unknown error'}`;
        }
      } catch (err) {
        alertBox.className = "alert alert-danger small d-block mb-3";
        alertBox.innerText = `Network error: ${err.message}`;
      } finally {
        btnSubmit.disabled = false;
        btnSubmit.innerHTML = `<i class="bi bi-key-fill me-1"></i> Provision & Generate Token`;
      }
    });
  }
}

// ----------------------------------------------------------------------------
// 7. Navigation & Utilities
// ----------------------------------------------------------------------------

function initSidebarInteractions() {
  const sidebarToggleBtn = document.getElementById("sidebarToggleBtn");
  const sidebar = document.getElementById("reampSidebar");
  const backdrop = document.getElementById("sidebarBackdrop");

  if (sidebarToggleBtn && sidebar && backdrop) {
    sidebarToggleBtn.addEventListener("click", () => {
      sidebar.classList.toggle("show");
      backdrop.classList.toggle("show");
    });

    backdrop.addEventListener("click", () => {
      sidebar.classList.remove("show");
      backdrop.classList.remove("show");
    });
  }

  // Sync section titles on tab switch
  const tabElements = document.querySelectorAll('#backofficeTab button[data-bs-toggle="tab"]');
  const sectionTitle = document.getElementById("topbar-section-title");

  const tabTitles = {
    "overview-tab": '<i class="bi bi-speedometer2 text-primary me-2"></i> Global Platform Overview',
    "tenants-tab": '<i class="bi bi-buildings text-indigo me-2"></i> Tenant Partitions & Resource Limits',
    "users-tab": '<i class="bi bi-people text-success me-2"></i> Global Platform User Directory & RBAC',
    "infra-tab": '<i class="bi bi-database-gear text-purple me-2"></i> Database & API Infrastructure Diagnostics',
    "audit-tab": '<i class="bi bi-shield-check text-secondary me-2"></i> Cryptographic Governance & Audit Ledger',
    "hitl-tab": '<i class="bi bi-wrench-adjustable text-warning me-2"></i> Global HITL Work Order Queue & Emergency Oversight',
  };

  tabElements.forEach(tab => {
    tab.addEventListener("shown.bs.tab", (event) => {
      const targetId = event.target.id;
      if (sectionTitle && tabTitles[targetId]) {
        sectionTitle.innerHTML = tabTitles[targetId];
      }
      if (window.innerWidth < 992 && sidebar && backdrop) {
        sidebar.classList.remove("show");
        backdrop.classList.remove("show");
      }
    });
  });
}

function updateUtcClock() {
  const clockEl = document.getElementById("sidebar-utc-clock");
  if (clockEl) {
    const now = new Date();
    clockEl.innerText = now.toUTCString().split(" ")[4] + " UTC";
  }
}
