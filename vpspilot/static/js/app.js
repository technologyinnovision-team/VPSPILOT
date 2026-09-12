/**
 * VPSPilot SPA Controller
 * Handles Navigation, Telemetry WebSocket, Services, Processes, and VPS Configuration
 */

let activeTab = "overview";
let metricsSocket = null;
let allServices = [];
let allProcesses = [];
let currentLogService = null;

function formatBytes(bytes, decimals = 1) {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
}

function formatRate(bytesPerSec) {
  if (!bytesPerSec || bytesPerSec === 0) return "0 KB/s";
  if (bytesPerSec < 1024 * 1024) {
    return (bytesPerSec / 1024).toFixed(1) + " KB/s";
  }
  return (bytesPerSec / (1024 * 1024)).toFixed(1) + " MB/s";
}

function formatUptime(seconds) {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h ${mins}m`;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m ${seconds % 60}s`;
}

// --- Tab Navigation ---

function setupTabs() {
  document.querySelectorAll(".nav-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tab;
      switchTab(target);
    });
  });
}

function switchTab(tabId) {
  activeTab = tabId;
  document.querySelectorAll(".nav-tab").forEach((t) => {
    t.classList.toggle("active", t.dataset.tab === tabId);
  });
  document.querySelectorAll(".tab-pane").forEach((pane) => {
    pane.classList.toggle("active", pane.id === `tab-${tabId}`);
  });

  if (tabId === "terminal") {
    setTimeout(() => {
      if (window.initTerminal) window.initTerminal();
      if (window.fitTerminal) window.fitTerminal();
    }, 100);
  } else if (tabId === "services") {
    fetchServices();
  } else if (tabId === "processes") {
    fetchProcesses();
  } else if (tabId === "vpsconfig") {
    fetchVPSConfig();
  }
}

// --- Auth & Session ---

async function checkAuthStatus() {
  try {
    const res = await fetch("/api/auth/status");
    const data = await res.json();
    if (data.authenticated) {
      document.getElementById("login-screen").style.display = "none";
      document.getElementById("nav-username").textContent = data.username || "admin";
      initApp();
    } else {
      document.getElementById("login-screen").style.display = "flex";
    }
  } catch (err) {
    console.error("Auth status check failed:", err);
    document.getElementById("login-screen").style.display = "flex";
  }
}

async function handleLoginSubmit(e) {
  e.preventDefault();
  const user = document.getElementById("login-username").value.trim();
  const pwd = document.getElementById("login-password").value;
  const errEl = document.getElementById("login-error");
  errEl.textContent = "";

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user, password: pwd })
    });
    const data = await res.json();
    if (data.success) {
      localStorage.setItem("vpspilot_token", data.token);
      document.getElementById("login-screen").style.display = "none";
      document.getElementById("nav-username").textContent = data.username || user;
      initApp();
    } else {
      errEl.textContent = data.error || "Authentication failed.";
    }
  } catch (err) {
    errEl.textContent = "Server unreachable. Please check network.";
  }
}

async function handleLogout() {
  try {
    await fetch("/api/auth/logout", { method: "POST" });
  } catch (e) {}
  localStorage.removeItem("vpspilot_token");
  window.location.reload();
}

// --- Real-time Telemetry (WebSocket) ---

function initMetricsWebSocket() {
  if (metricsSocket && metricsSocket.readyState === WebSocket.OPEN) return;

  const token = localStorage.getItem("vpspilot_token") || "";
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/metrics?token=${encodeURIComponent(token)}`;

  metricsSocket = new WebSocket(wsUrl);

  metricsSocket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      updateTelemetryUI(data);
    } catch (e) {
      console.warn("Invalid telemetry packet:", e);
    }
  };

  metricsSocket.onclose = () => {
    // Reconnect after delay
    setTimeout(() => {
      if (document.getElementById("login-screen").style.display === "none") {
        initMetricsWebSocket();
      }
    }, 3000);
  };
}

function updateTelemetryUI(data) {
  // System Info
  if (data.system) {
    document.getElementById("sys-hostname").textContent = data.system.hostname;
    document.getElementById("sys-distro").textContent = data.system.distro;
    document.getElementById("sys-kernel").textContent = data.system.kernel;
    document.getElementById("sys-uptime").textContent = formatUptime(data.system.uptime_seconds);
  }

  // CPU
  if (data.cpu) {
    const cpuTotal = Math.round(data.cpu.total_percent);
    document.getElementById("cpu-val").textContent = `${cpuTotal}%`;
    const cpuBar = document.getElementById("cpu-bar");
    cpuBar.style.width = `${cpuTotal}%`;
    cpuBar.className = `progress-bar ${cpuTotal > 85 ? "danger" : cpuTotal > 60 ? "warning" : ""}`;

    document.getElementById("cpu-sub").textContent = `${data.cpu.core_count} Cores • Load: ${data.cpu.load_1m}, ${data.cpu.load_5m}, ${data.cpu.load_15m}`;

    // Render cores grid
    const coresGrid = document.getElementById("cpu-cores-grid");
    if (coresGrid && data.cpu.cores) {
      coresGrid.innerHTML = data.cpu.cores.map((c, i) => `
        <div class="core-item">
          <div class="core-name">C${i}</div>
          <div class="core-val" style="color: ${c > 85 ? '#ef4444' : c > 60 ? '#f59e0b' : '#10b981'}">${Math.round(c)}%</div>
        </div>
      `).join("");
    }
  }

  // Memory
  if (data.memory && data.memory.ram) {
    const ram = data.memory.ram;
    const ramPercent = Math.round(ram.percent);
    document.getElementById("ram-val").textContent = `${ramPercent}%`;
    const ramBar = document.getElementById("ram-bar");
    ramBar.style.width = `${ramPercent}%`;
    ramBar.className = `progress-bar ${ramPercent > 85 ? "danger" : ramPercent > 70 ? "warning" : ""}`;
    document.getElementById("ram-sub").textContent = `${formatBytes(ram.used)} / ${formatBytes(ram.total)} (${formatBytes(ram.available)} free)`;
  }

  // Network Rates
  if (data.network) {
    document.getElementById("net-rx-rate").textContent = formatRate(data.network.rx_rate_bps);
    document.getElementById("net-tx-rate").textContent = formatRate(data.network.tx_rate_bps);
    document.getElementById("net-total-sub").textContent = `↓ ${formatBytes(data.network.bytes_recv)} | ↑ ${formatBytes(data.network.bytes_sent)}`;
  }

  // Disks
  if (data.disks && data.disks.length > 0) {
    const rootDisk = data.disks.find(d => d.mountpoint === "/") || data.disks[0];
    const diskPercent = Math.round(rootDisk.percent);
    document.getElementById("disk-val").textContent = `${diskPercent}%`;
    const diskBar = document.getElementById("disk-bar");
    diskBar.style.width = `${diskPercent}%`;
    diskBar.className = `progress-bar ${diskPercent > 85 ? "danger" : diskPercent > 70 ? "warning" : ""}`;
    document.getElementById("disk-sub").textContent = `${formatBytes(rootDisk.used)} / ${formatBytes(rootDisk.total)} on ${rootDisk.mountpoint}`;

    // Disks table in overview
    const diskTbody = document.getElementById("disks-tbody");
    if (diskTbody) {
      diskTbody.innerHTML = data.disks.map(d => `
        <tr>
          <td><strong>${d.mountpoint}</strong></td>
          <td>${d.device}</td>
          <td>${d.fstype}</td>
          <td>${formatBytes(d.used)} / ${formatBytes(d.total)}</td>
          <td>
            <div style="display:flex; align-items:center; gap:0.5rem;">
              <div class="progress-bar-container" style="flex:1; margin:0;">
                <div class="progress-bar ${d.percent > 85 ? 'danger' : d.percent > 70 ? 'warning' : ''}" style="width: ${d.percent}%"></div>
              </div>
              <span style="font-size:0.8rem; font-weight:600;">${Math.round(d.percent)}%</span>
            </div>
          </td>
        </tr>
      `).join("");
    }
  }
}

// --- Services Management ---

async function fetchServices() {
  const tbody = document.getElementById("services-tbody");
  tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 2rem;">Loading services...</td></tr>`;

  try {
    const res = await fetch("/api/services/list");
    const data = await res.json();
    if (data.success) {
      allServices = data.services;
      renderServices();
    } else {
      tbody.innerHTML = `<tr><td colspan="5" style="color:var(--danger); text-align:center;">Failed to load services</td></tr>`;
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="color:var(--danger); text-align:center;">Error fetching services: ${err}</td></tr>`;
  }
}

function renderServices() {
  const tbody = document.getElementById("services-tbody");
  const filter = document.getElementById("services-status-filter").value;
  const search = document.getElementById("services-search-input").value.toLowerCase().trim();

  let filtered = allServices.filter(s => {
    if (filter === "active" && s.active !== "active") return false;
    if (filter === "inactive" && s.active !== "inactive") return false;
    if (filter === "failed" && s.active !== "failed") return false;
    if (search && !s.name.toLowerCase().includes(search) && !(s.description && s.description.toLowerCase().includes(search))) return false;
    return true;
  });

  document.getElementById("services-count").textContent = `${filtered.length} of ${allServices.length}`;

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 2rem; color:var(--text-muted);">No matching services found</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(s => {
    const isActive = s.active === "active";
    const isFailed = s.active === "failed";
    const badgeClass = isActive ? "badge-active" : isFailed ? "badge-failed" : "badge-inactive";

    return `
      <tr>
        <td>
          <div style="font-weight:600; font-family:var(--font-mono); font-size:0.85rem;">${s.clean_name}</div>
          <div style="font-size:0.75rem; color:var(--text-muted);">${s.description || ""}</div>
        </td>
        <td><span class="badge ${badgeClass}"><span class="status-dot"></span>${s.active}</span></td>
        <td><span style="font-size:0.8rem; color:var(--text-muted); font-family:var(--font-mono);">${s.sub}</span></td>
        <td><span style="font-size:0.8rem; color:var(--text-muted);">${s.load}</span></td>
        <td>
          <div style="display:flex; gap:0.4rem; justify-content:flex-end;">
            ${isActive ? `
              <button class="btn btn-sm btn-outline" onclick="controlService('${s.name}', 'restart')">Restart</button>
              <button class="btn btn-sm btn-danger" onclick="controlService('${s.name}', 'stop')">Stop</button>
            ` : `
              <button class="btn btn-sm btn-success" onclick="controlService('${s.name}', 'start')">Start</button>
            `}
            <button class="btn btn-sm btn-outline" onclick="viewServiceLogs('${s.name}')">Logs</button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

async function controlService(serviceName, action) {
  if (action === "stop" && !confirm(`Are you sure you want to STOP service '${serviceName}'?`)) {
    return;
  }
  try {
    const res = await fetch("/api/services/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ service: serviceName, action })
    });
    const data = await res.json();
    if (data.success) {
      setTimeout(() => fetchServices(), 800);
    } else {
      alert(`Service action failed: ${data.error}`);
    }
  } catch (err) {
    alert(`Network error controlling service: ${err}`);
  }
}

async function viewServiceLogs(serviceName) {
  currentLogService = serviceName;
  document.getElementById("log-modal-title").textContent = `Logs: ${serviceName}`;
  const logBox = document.getElementById("service-log-box");
  logBox.textContent = "Loading journalctl logs...";
  document.getElementById("log-modal").classList.add("open");

  try {
    const res = await fetch(`/api/services/logs?service=${encodeURIComponent(serviceName)}&lines=150`);
    const data = await res.json();
    if (data.success) {
      logBox.textContent = data.logs || "(No recent journal records found for this unit)";
      logBox.scrollTop = logBox.scrollHeight;
    } else {
      logBox.textContent = `Failed to load logs: ${data.error}`;
    }
  } catch (err) {
    logBox.textContent = `Error: ${err}`;
  }
}

function refreshCurrentLogs() {
  if (currentLogService) {
    viewServiceLogs(currentLogService);
  }
}

function copyLogsToClipboard() {
  const content = document.getElementById("service-log-box").textContent;
  navigator.clipboard.writeText(content).then(() => {
    alert("Logs copied to clipboard!");
  });
}

function closeLogModal() {
  document.getElementById("log-modal").classList.remove("open");
}

// --- Processes Management ---

async function fetchProcesses() {
  const tbody = document.getElementById("processes-tbody");
  const sort = document.getElementById("proc-sort-select").value;
  tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2rem;">Inspecting processes...</td></tr>`;

  try {
    const res = await fetch(`/api/processes/list?sort=${sort}&limit=80`);
    const data = await res.json();
    if (data.success) {
      allProcesses = data.processes;
      renderProcesses();
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="color:var(--danger); text-align:center;">Error: ${err}</td></tr>`;
  }
}

function renderProcesses() {
  const tbody = document.getElementById("processes-tbody");
  const search = document.getElementById("proc-search-input").value.toLowerCase().trim();

  let filtered = allProcesses.filter(p => {
    if (search && !p.name.toLowerCase().includes(search) && !p.cmdline.toLowerCase().includes(search) && !String(p.pid).includes(search)) return false;
    return true;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2rem; color:var(--text-muted);">No matching processes</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(p => `
    <tr>
      <td style="font-family:var(--font-mono); font-weight:600;">${p.pid}</td>
      <td style="font-weight:600;">${p.name}</td>
      <td>${p.user}</td>
      <td style="font-family:var(--font-mono); color: ${p.cpu_percent > 50 ? '#ef4444' : '#f3f4f6'}; font-weight:600;">${p.cpu_percent}%</td>
      <td style="font-family:var(--font-mono);">${p.memory_percent}%</td>
      <td style="font-family:var(--font-mono); font-size:0.75rem; color:var(--text-muted); max-width: 320px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${p.cmdline}">${p.cmdline}</td>
      <td>
        <button class="btn btn-sm btn-danger" onclick="killProcess(${p.pid}, '${p.name}')">Kill</button>
      </td>
    </tr>
  `).join("");
}

async function killProcess(pid, name) {
  if (!confirm(`Terminate process PID ${pid} (${name})?`)) return;
  try {
    const res = await fetch("/api/processes/signal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pid, signal: "SIGTERM" })
    });
    const data = await res.json();
    if (data.success) {
      setTimeout(() => fetchProcesses(), 500);
    } else {
      alert(`Could not terminate process: ${data.error}`);
    }
  } catch (err) {
    alert(`Error: ${err}`);
  }
}

// --- VPS Configuration ---

async function fetchVPSConfig() {
  try {
    const res = await fetch("/api/config/get");
    const data = await res.json();
    if (data.success) {
      const cfg = data.config;

      // Hostname & Timezone
      document.getElementById("cfg-hostname-input").value = cfg.hostname || "";
      document.getElementById("cfg-current-tz").textContent = cfg.timezone || "UTC";

      const tzSelect = document.getElementById("cfg-timezone-select");
      if (cfg.available_timezones) {
        tzSelect.innerHTML = cfg.available_timezones.map(tz => `
          <option value="${tz}" ${tz === cfg.timezone ? "selected" : ""}>${tz}</option>
        `).join("");
      }

      // DNS
      const dnsEl = document.getElementById("cfg-dns-list");
      if (dnsEl && cfg.dns_resolvers) {
        dnsEl.textContent = cfg.dns_resolvers.join(", ") || "None found";
      }

      // SSH
      if (cfg.ssh) {
        document.getElementById("ssh-status-badge").textContent = cfg.ssh.active ? "Active" : "Inactive";
        document.getElementById("ssh-status-badge").className = `badge ${cfg.ssh.active ? 'badge-active' : 'badge-inactive'}`;
        document.getElementById("ssh-port-val").textContent = cfg.ssh.port || "22";
        document.getElementById("ssh-root-login").textContent = cfg.ssh.permit_root_login || "default";
        document.getElementById("ssh-pwd-auth").textContent = cfg.ssh.password_auth || "default";
      }

      // Firewall (UFW)
      if (cfg.firewall) {
        const fw = cfg.firewall;
        const fwToggle = document.getElementById("fw-toggle-btn");
        const fwBadge = document.getElementById("fw-status-badge");

        if (fw.backend === "ufw") {
          fwBadge.textContent = fw.active ? "UFW Active" : "UFW Inactive";
          fwBadge.className = `badge ${fw.active ? 'badge-active' : 'badge-inactive'}`;
          fwToggle.textContent = fw.active ? "Disable Firewall" : "Enable Firewall";
          fwToggle.className = `btn btn-sm ${fw.active ? 'btn-danger' : 'btn-success'}`;
          renderFirewallRules(fw.rules || []);
        } else {
          fwBadge.textContent = "Backend: " + fw.backend;
          fwBadge.className = "badge badge-info";
          fwToggle.style.display = "none";
        }
      }

      // Updates
      if (cfg.updates) {
        document.getElementById("updates-count").textContent = `${cfg.updates.upgradable_count} packages pending update`;
      }
    }
  } catch (err) {
    console.error("Config fetch error:", err);
  }
}

function renderFirewallRules(rules) {
  const tbody = document.getElementById("fw-rules-tbody");
  if (!rules || rules.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">No rules active. Standard policy applies.</td></tr>`;
    return;
  }

  tbody.innerHTML = rules.map(r => `
    <tr>
      <td style="font-family:var(--font-mono); font-weight:600;">#${r.id}</td>
      <td style="font-weight:600;">${r.to}</td>
      <td><span class="badge ${r.action === 'ALLOW' ? 'badge-active' : 'badge-danger'}">${r.action}</span></td>
      <td>${r.direction}</td>
      <td style="display:flex; justify-content:space-between; align-items:center;">
        <span>${r.from}</span>
        <button class="btn btn-sm btn-danger" onclick="deleteFirewallRule('${r.id}')">Delete</button>
      </td>
    </tr>
  `).join("");
}

async function saveHostname(e) {
  e.preventDefault();
  const hostname = document.getElementById("cfg-hostname-input").value.trim();
  if (!hostname) return;
  try {
    const res = await fetch("/api/config/hostname", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hostname })
    });
    const data = await res.json();
    if (data.success) {
      alert("Hostname successfully changed to: " + hostname);
      fetchVPSConfig();
    } else {
      alert("Error setting hostname: " + data.error);
    }
  } catch (err) {
    alert("Error: " + err);
  }
}

async function saveTimezone(e) {
  e.preventDefault();
  const tz = document.getElementById("cfg-timezone-select").value;
  try {
    const res = await fetch("/api/config/timezone", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ timezone: tz })
    });
    const data = await res.json();
    if (data.success) {
      alert("Timezone set to: " + tz);
      fetchVPSConfig();
    } else {
      alert("Error setting timezone: " + data.error);
    }
  } catch (err) {
    alert("Error: " + err);
  }
}

async function addFirewallRule(e) {
  e.preventDefault();
  const port = document.getElementById("fw-port-input").value.trim();
  const action = document.getElementById("fw-action-select").value;
  if (!port) return;

  try {
    const res = await fetch("/api/config/firewall/rule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ port_or_service: port, action })
    });
    const data = await res.json();
    if (data.success) {
      document.getElementById("fw-port-input").value = "";
      fetchVPSConfig();
    } else {
      alert("Firewall rule error: " + data.error);
    }
  } catch (err) {
    alert("Error: " + err);
  }
}

async function deleteFirewallRule(ruleId) {
  if (!confirm(`Delete firewall rule #${ruleId}?`)) return;
  try {
    const res = await fetch("/api/config/firewall/rule", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rule_id: ruleId })
    });
    const data = await res.json();
    if (data.success) {
      fetchVPSConfig();
    } else {
      alert("Could not delete rule: " + data.error);
    }
  } catch (err) {
    alert("Error: " + err);
  }
}

async function toggleFirewall() {
  const fwBadge = document.getElementById("fw-status-badge");
  const isCurrentlyActive = fwBadge.textContent.includes("Active");
  const action = isCurrentlyActive ? "disable" : "enable";

  if (!confirm(`Are you sure you want to ${action.toUpperCase()} the firewall?`)) return;

  try {
    const res = await fetch("/api/config/firewall/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enable: !isCurrentlyActive })
    });
    const data = await res.json();
    if (data.success) {
      fetchVPSConfig();
    } else {
      alert("Toggle error: " + data.error);
    }
  } catch (err) {
    alert("Error: " + err);
  }
}

async function executePower(action) {
  const code = prompt(`TYPE '${action.toUpperCase()}' to confirm system ${action}:`);
  if (code !== action.toUpperCase()) {
    alert("Action cancelled.");
    return;
  }

  try {
    const res = await fetch("/api/config/power", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action })
    });
    const data = await res.json();
    alert(data.message || `System ${action} triggered.`);
  } catch (err) {
    alert("Error executing command: " + err);
  }
}

// --- Settings & Password Change ---

async function handleChangePassword(e) {
  e.preventDefault();
  const curr = document.getElementById("pwd-current").value;
  const newP = document.getElementById("pwd-new").value;
  const confirmP = document.getElementById("pwd-confirm").value;
  const statusEl = document.getElementById("pwd-status-msg");
  statusEl.textContent = "";

  if (newP !== confirmP) {
    statusEl.textContent = "New passwords do not match!";
    statusEl.style.color = "var(--danger)";
    return;
  }

  try {
    const res = await fetch("/api/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: curr, new_password: newP })
    });
    const data = await res.json();
    if (data.success) {
      statusEl.textContent = "Password changed successfully!";
      statusEl.style.color = "var(--success)";
      document.getElementById("pwd-current").value = "";
      document.getElementById("pwd-new").value = "";
      document.getElementById("pwd-confirm").value = "";
    } else {
      statusEl.textContent = data.error || "Password update failed.";
      statusEl.style.color = "var(--danger)";
    }
  } catch (err) {
    statusEl.textContent = "Error: " + err;
    statusEl.style.color = "var(--danger)";
  }
}

// --- App Initialization ---

function initApp() {
  setupTabs();
  initMetricsWebSocket();

  // Search listeners
  const servSearch = document.getElementById("services-search-input");
  if (servSearch) servSearch.addEventListener("input", renderServices);
  const servFilter = document.getElementById("services-status-filter");
  if (servFilter) servFilter.addEventListener("change", renderServices);

  const procSearch = document.getElementById("proc-search-input");
  if (procSearch) procSearch.addEventListener("input", renderProcesses);
  const procSort = document.getElementById("proc-sort-select");
  if (procSort) procSort.addEventListener("change", fetchProcesses);

  // Forms
  document.getElementById("form-hostname")?.addEventListener("submit", saveHostname);
  document.getElementById("form-timezone")?.addEventListener("submit", saveTimezone);
  document.getElementById("form-add-rule")?.addEventListener("submit", addFirewallRule);
  document.getElementById("form-change-password")?.addEventListener("submit", handleChangePassword);
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("login-form").addEventListener("submit", handleLoginSubmit);
  checkAuthStatus();
});

// Global functions for inline onclick handlers
window.controlService = controlService;
window.viewServiceLogs = viewServiceLogs;
window.refreshCurrentLogs = refreshCurrentLogs;
window.copyLogsToClipboard = copyLogsToClipboard;
window.closeLogModal = closeLogModal;
window.killProcess = killProcess;
window.deleteFirewallRule = deleteFirewallRule;
window.toggleFirewall = toggleFirewall;
window.executePower = executePower;
window.handleLogout = handleLogout;
window.fetchServices = fetchServices;
window.fetchProcesses = fetchProcesses;
