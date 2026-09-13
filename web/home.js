/* ==========================================================================
   REGENOVA Public Home Page Controller
   Requirement: FR-UI-001 / AC-FR-UI-001
   Interfaces with REST API on https://api.regenova.cloud
   ========================================================================== */

const API_BASE = (window.REGENOVA_API_URL !== undefined)
  ? window.REGENOVA_API_URL
  : (window.location.hostname === 'regenova.cloud' ? 'https://api.regenova.cloud' : '');

function apiFetch(endpoint, options = {}) {
  const url = (typeof endpoint === 'string' && endpoint.startsWith('http'))
    ? endpoint
    : `${API_BASE}${endpoint}`;
  return fetch(url, options);
}

let selectedLoginTenant = "ORG-HELIOS-GLOBAL";

document.addEventListener("DOMContentLoaded", () => {
  fetchLiveTelemetry();
  probeTwinFieldSubApi();
  initPreEnrolmentForm();
  initLoginModal();
});

// ----------------------------------------------------------------------------
// 1. Live Telemetry & Platform Stats
// ----------------------------------------------------------------------------

async function fetchLiveTelemetry() {
  try {
    const [overviewRes, tenantsRes] = await Promise.all([
      apiFetch("/api/overview"),
      apiFetch("/api/tenants")
    ]);

    if (overviewRes.ok) {
      const ov = await overviewRes.json();
      const capEl = document.getElementById("stat-hero-capacity");
      if (capEl) capEl.innerHTML = `${ov.total_capacity_mw.toFixed(1)} <small class="fs-6 text-muted">MW</small>`;

      const genEl = document.getElementById("stat-hero-gen");
      if (genEl) genEl.innerText = `${ov.total_generation_mw.toFixed(2)} MW`;

      const healthEl = document.getElementById("stat-hero-health");
      if (healthEl) healthEl.innerHTML = `${ov.fleet_health_index.toFixed(1)} <small class="fs-6 text-muted">/ 100</small>`;

      const assetsEl = document.getElementById("stat-hero-assets");
      if (assetsEl) assetsEl.innerHTML = `${ov.total_assets || 7} <small class="fs-6 text-muted">assets</small>`;
    }

    if (tenantsRes.ok) {
      const tData = await tenantsRes.json();
      const tenants = tData.tenants || [];
      const tenantCountEl = document.getElementById("stat-hero-tenants");
      if (tenantCountEl) tenantCountEl.innerText = tenants.length;
    }
  } catch (err) {
    console.warn("Could not fetch live telemetry for home page:", err);
  }
}

async function probeTwinFieldSubApi() {
  const badge = document.getElementById("home-twinfield-live-badge");
  if (!badge) return;
  try {
    let res;
    try {
      res = await fetch("https://twinfield.regenova.cloud/health", { method: "GET", mode: "cors" });
    } catch (e) {
      res = await apiFetch("/api/twinfield/status");
    }
    if (res && res.ok) {
      const data = await res.json();
      badge.className = "badge bg-success-subtle text-success border border-success-subtle px-2 py-1 font-monospace";
      badge.innerHTML = `<i class="bi bi-circle-fill me-1" style="font-size: 0.55rem;"></i>SUB-API ONLINE (v${data.version || '0.3.0'})`;
    } else {
      badge.className = "badge bg-warning-subtle text-warning border border-warning-subtle px-2 py-1 font-monospace";
      badge.innerHTML = `<i class="bi bi-exclamation-triangle me-1" style="font-size: 0.55rem;"></i>SUB-API STANDBY`;
    }
  } catch (e) {
    badge.className = "badge bg-warning-subtle text-warning border border-warning-subtle px-2 py-1 font-monospace";
    badge.innerHTML = `<i class="bi bi-exclamation-triangle me-1" style="font-size: 0.55rem;"></i>SUB-API STANDBY`;
  }
}

// ----------------------------------------------------------------------------
// 2. Pre-Enrolment Form Handler
// ----------------------------------------------------------------------------

function initPreEnrolmentForm() {
  const form = document.getElementById("form-home-pre-enroll");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const alertBox = document.getElementById("pre-enroll-alert");
    const btnSubmit = document.getElementById("btn-submit-pre-enroll");

    alertBox.className = "alert alert-info small py-2 d-block mb-3";
    alertBox.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Provisioning isolated enterprise partition and issuing security credentials...`;
    btnSubmit.disabled = true;

    try {
      const tenantId = document.getElementById("enrol-tenant-id").value.trim().toUpperCase();
      const payload = {
        tenant_id: tenantId,
        name: document.getElementById("enrol-org-name").value.trim(),
        code: document.getElementById("enrol-short-code").value.trim().toUpperCase(),
        billing_tier: document.getElementById("enrol-billing-tier").value,
        admin_name: document.getElementById("enrol-admin-name").value.trim(),
        admin_email: document.getElementById("enrol-admin-email").value.trim(),
      };

      const res = await apiFetch("/api/onboarding/tenant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (data.status === "SUCCESS") {
        alertBox.className = "alert alert-success small py-3 d-block mb-3";
        alertBox.innerHTML = `
          <div class="d-flex align-items-center gap-2 mb-2">
            <i class="bi bi-check-circle-fill text-success fs-5"></i>
            <strong class="fs-6">Organisation Enrolment Approved!</strong>
          </div>
          <p class="mb-2">Enterprise partition <code>${data.tenant_id}</code> (${data.name}) has been provisioned with strict Row Level Security (RLS) isolation.</p>
          <div class="bg-light p-2 rounded border font-monospace small mb-3">
            <div>Primary Admin: <strong>${data.admin_user_id}</strong> (${data.admin_email})</div>
            <div>HMAC Security Token: <code class="user-select-all text-primary">${data.admin_token}</code></div>
          </div>
          <a href="/portal.html?tenant_id=${data.tenant_id}" class="btn btn-sm btn-primary fw-semibold">
            <i class="bi bi-box-arrow-in-right me-1"></i> Launch Operations Portal as ${data.tenant_id}
          </a>
        `;
        form.reset();
        fetchLiveTelemetry();
      } else {
        alertBox.className = "alert alert-danger small py-2 d-block mb-3";
        alertBox.innerText = `Enrolment error: ${data.message || 'Unable to complete pre-enrolment'}`;
      }
    } catch (err) {
      alertBox.className = "alert alert-danger small py-2 d-block mb-3";
      alertBox.innerText = `Network error: ${err.message}`;
    } finally {
      btnSubmit.disabled = false;
    }
  });
}

// ----------------------------------------------------------------------------
// 3. Operator Login & Portal Access Modal
// ----------------------------------------------------------------------------

function initLoginModal() {
  const btnEnterPortal = document.getElementById("btn-enter-portal");
  if (btnEnterPortal) {
    btnEnterPortal.addEventListener("click", () => {
      window.location.href = "/portal.html";
    });
  }
}
