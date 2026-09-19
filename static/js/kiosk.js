const STATION_CODE = "CS-SDR-01";
let stationConnectors = [];
let activeSessions = {};
let ws = null;

// =============================================================
// UNIVERSAL CUSTOM DIALOG SYSTEM (MODAL ALERT & CONFIRM)
// =============================================================
function showAppAlert(message, options = {}) {
  const {
    title = "Pemberitahuan",
    subtitle = "",
    type = "info",
    confirmText = "Mengerti",
    icon = null
  } = (typeof options === "string") ? { title: options } : options;

  return new Promise((resolve) => {
    const overlay = document.getElementById("appDialogOverlay");
    const box = document.getElementById("appDialogBox");
    const titleEl = document.getElementById("appDialogTitle");
    const subtitleEl = document.getElementById("appDialogSubtitle");
    const msgEl = document.getElementById("appDialogMessage");
    const iconEl = document.getElementById("appDialogIcon");
    const confirmBtn = document.getElementById("appDialogConfirmBtn");
    const cancelBtn = document.getElementById("appDialogCancelBtn");

    if (!overlay || !box) {
      alert(message);
      resolve(true);
      return;
    }

    titleEl.innerText = title;
    msgEl.innerText = message;
    if (subtitle) {
      subtitleEl.innerText = subtitle;
      subtitleEl.style.display = "block";
    } else {
      subtitleEl.style.display = "none";
    }

    box.className = `app-dialog-box ${type}`;
    let defaultIcon = "⚡";
    if (type === "warning") defaultIcon = "⚠️";
    else if (type === "error") defaultIcon = "❌";
    else if (type === "success") defaultIcon = "✅";
    else if (type === "info") defaultIcon = "ℹ️";

    iconEl.innerText = icon || defaultIcon;
    confirmBtn.innerText = confirmText;
    confirmBtn.className = (type === "error") ? "btn btn-danger" : "btn btn-primary";
    if (cancelBtn) cancelBtn.style.display = "none";

    const onConfirm = () => {
      confirmBtn.removeEventListener("click", onConfirm);
      overlay.classList.remove("open");
      resolve(true);
    };

    confirmBtn.addEventListener("click", onConfirm);
    overlay.classList.add("open");
  });
}

function showAppConfirm(message, options = {}) {
  const {
    title = "Konfirmasi Tindakan",
    subtitle = "",
    type = "warning",
    confirmText = "Ya, Lanjutkan",
    cancelText = "Batal",
    icon = null
  } = (typeof options === "string") ? { title: options } : options;

  return new Promise((resolve) => {
    const overlay = document.getElementById("appDialogOverlay");
    const box = document.getElementById("appDialogBox");
    const titleEl = document.getElementById("appDialogTitle");
    const subtitleEl = document.getElementById("appDialogSubtitle");
    const msgEl = document.getElementById("appDialogMessage");
    const iconEl = document.getElementById("appDialogIcon");
    const confirmBtn = document.getElementById("appDialogConfirmBtn");
    const cancelBtn = document.getElementById("appDialogCancelBtn");

    if (!overlay || !box) {
      resolve(confirm(message));
      return;
    }

    titleEl.innerText = title;
    msgEl.innerText = message;
    if (subtitle) {
      subtitleEl.innerText = subtitle;
      subtitleEl.style.display = "block";
    } else {
      subtitleEl.style.display = "none";
    }

    box.className = `app-dialog-box ${type}`;
    let defaultIcon = "⚠️";
    if (type === "error") defaultIcon = "🛑";
    else if (type === "info") defaultIcon = "ℹ️";

    iconEl.innerText = icon || defaultIcon;
    confirmBtn.innerText = confirmText;
    confirmBtn.className = (type === "error" || type === "warning") ? "btn btn-danger" : "btn btn-primary";
    
    if (cancelBtn) {
      cancelBtn.innerText = cancelText;
      cancelBtn.style.display = "block";
    }

    const cleanup = () => {
      confirmBtn.removeEventListener("click", onConfirm);
      if (cancelBtn) cancelBtn.removeEventListener("click", onCancel);
      overlay.classList.remove("open");
    };

    const onConfirm = () => { cleanup(); resolve(true); };
    const onCancel = () => { cleanup(); resolve(false); };

    confirmBtn.addEventListener("click", onConfirm);
    if (cancelBtn) cancelBtn.addEventListener("click", onCancel);
    overlay.classList.add("open");
  });
}

// Clock
setInterval(() => {
  const now = new Date();
  document.getElementById("liveClock").innerText = now.toLocaleTimeString("id-ID") + " WIB";
}, 1000);

// Generate QR Code for HP Driver
function initQrCode() {
  const driverUrl = window.location.origin + "/driver";
  document.getElementById("kioskUrlText").innerText = driverUrl;
  const qrContainer = document.getElementById("kioskQrCode");
  if (typeof QRCode !== "undefined") {
    qrContainer.innerHTML = "";
    new QRCode(qrContainer, {
      text: driverUrl,
      width: 160,
      height: 160,
      colorDark: "#0B0F19",
      colorLight: "#FFFFFF",
      correctLevel: QRCode.CorrectLevel.M
    });
  } else {
    qrContainer.innerHTML = `<div style="padding:10px; color:#333; font-size:0.8rem; font-weight:600;">Scan URL:<br>${driverUrl}</div>`;
  }
}


// Fetch Station, Connectors & Active Sessions
async function loadStationData() {
  try {
    const res = await fetch(`/api/station/${STATION_CODE}`);
    const data = await res.json();
    stationConnectors = data.connectors || [];
    renderConnectors(data.connectors);

    // Fetch all active sessions to display live telemetry cards per nozzle
    const sessRes = await fetch(`/api/station/${STATION_CODE}/active-sessions`);
    if (sessRes.ok) {
      const sessions = await sessRes.json();
      activeSessions = {};
      sessions.forEach(s => {
        activeSessions[s.session_id] = s;
      });
      renderActiveSessions();
    }
  } catch (err) {
    console.error("Gagal load station:", err);
  }
}

function renderConnectors(connectors) {
  const container = document.getElementById("connectorsContainer");
  container.innerHTML = "";

  connectors.forEach(c => {
    const isCharging = c.status === "CHARGING";
    const isConnected = c.status === "CONNECTED";
    const isClaimed = !!c.locked_by_user_id;

    let statusBadge = `<span class="status-pill online">STANDBY</span>`;
    let cardClass = "nozzle-card";

    if (isCharging) {
      statusBadge = `<span class="status-pill busy">⚡ CHARGING</span>`;
      cardClass += " active-charging";
    } else if (isClaimed) {
      statusBadge = `<span class="status-pill warning" style="background:rgba(239,68,68,0.2); color:#F87171; border:1px solid #EF4444;">🔒 DIKLAIM DRIVER</span>`;
      cardClass += " claimed";
    } else if (isConnected) {
      statusBadge = `<span class="status-pill warning" style="background:rgba(16,185,129,0.2); color:#34D399; border:1px solid #10B981;">🔌 KABEL TERCOLOK</span>`;
      cardClass += " connected";
    }

    const typeBadge = c.type_category === "DC" 
      ? `<span style="background:rgba(0,240,255,0.2); color:#00F0FF; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.75rem;">DC FAST</span>`
      : `<span style="background:rgba(168,85,247,0.2); color:#A855F7; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.75rem;">AC NORMAL</span>`;

    const qrId = `nozzleQr-${c.id}`;

    let qrSection = "";
    if (isCharging) {
      qrSection = `
        <div style="margin-top:14px; padding:12px; background:rgba(0,240,255,0.05); border:1px solid rgba(0,240,255,0.2); border-radius:12px; text-align:center;">
          <div style="font-size:0.82rem; font-weight:700; color:#00F0FF;">⚡ Pengisian Berlangsung</div>
          <div style="font-size:0.72rem; color:#94A3B8; margin-top:2px;">Nozzle ini sedang aktif digunakan</div>
        </div>
      `;
    } else if (isClaimed) {
      qrSection = `
        <div style="margin-top:14px; padding:12px; background:rgba(245,158,11,0.08); border:1px solid rgba(245,158,11,0.3); border-radius:12px; text-align:center;">
          <div style="font-size:0.82rem; font-weight:700; color:#F59E0B;">🔒 Terkunci oleh Pengguna Lain</div>
          <div style="font-size:0.72rem; color:#94A3B8; margin-top:2px;">Driver sedang menyiapkan target pengisian</div>
        </div>
      `;
    } else {
      qrSection = `
        <div style="margin-top:14px; padding-top:12px; border-top:1px dashed #1E293B; text-align:center;">
          <div style="font-size:0.75rem; color:${isConnected ? '#34D399' : '#94A3B8'}; font-weight:700; margin-bottom:8px;">
            ${isConnected ? "📲 Scan QR untuk Klaim & Cas" : "📲 Scan QR Nozzle Ini"}
          </div>
          <div style="display:inline-block; background:#fff; padding:6px; border-radius:10px; box-shadow:0 4px 12px rgba(0,0,0,0.5);">
            <div id="${qrId}"></div>
          </div>
          <div style="font-size:0.68rem; color:#38BDF8; margin-top:6px; font-family:monospace; font-weight:600;">
            /driver?nozzle=${c.connector_number}
          </div>
        </div>
      `;
    }

    const html = `
      <div class="${cardClass}" id="nozzleCard-${c.id}">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
          <div style="font-size:1.4rem;">${c.type_category === 'DC' ? '⚡' : '🔌'}</div>
          <div>${statusBadge}</div>
        </div>
        <div style="font-weight:700; font-size:1rem; margin-bottom:4px; color:#fff;">${c.name}</div>
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">
          ${typeBadge}
          <span style="font-size:0.8rem; color:#94A3B8;">${c.connector_type} • Max ${Math.round(c.max_power_kw * 1000).toLocaleString('id-ID')} W</span>
        </div>
        <div style="font-size:0.85rem; color:#38BDF8; font-weight:600; border-top:1px solid #1E293B; padding-top:10px;">
          Tarif: Rp ${c.tariff_per_kwh.toLocaleString("id-ID")} / kWh
        </div>
        ${qrSection}
      </div>
    `;
    container.innerHTML += html;
  });

  // Render QR Codes into the newly injected elements
  connectors.forEach(c => {
    if (c.status !== "CHARGING" && !c.locked_by_user_id) {
      const qrElem = document.getElementById(`nozzleQr-${c.id}`);
      if (qrElem && typeof QRCode !== "undefined") {
        qrElem.innerHTML = "";
        const nozzleUrl = `${window.location.origin}/driver?nozzle=${c.connector_number}`;
        new QRCode(qrElem, {
          text: nozzleUrl,
          width: 90,
          height: 90,
          colorDark: "#0B0F19",
          colorLight: "#FFFFFF",
          correctLevel: QRCode.CorrectLevel.M
        });
      }
    }
  });
}

async function triggerKioskSimulatePlug(connectorId) {
  try {
    const res = await fetch(`/api/station/connector/${connectorId}/plug`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: 1 })
    });
    if (!res.ok) {
      const err = await res.json();
      await showAppAlert(err.detail || "Gagal inisialisasi nozzle!", { title: "Error Nozzle", type: "error" });
    } else {
      await showAppAlert(`Nozzle terhubung ke kendaraan!\nInisialisasi standar ISO 15118 & verifikasi kendaraan sedang berlangsung... Buka aplikasi Driver untuk mengatur pengisian.`, {
        title: "Inisialisasi Dimulai",
        type: "success"
      });
    }
  } catch (err) {
    await showAppAlert("Gagal inisialisasi nozzle: " + err, { title: "Koneksi Error", type: "error" });
  }
}

// WebSocket Setup
function setupWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/station/${STATION_CODE}`;
  
  ws = new WebSocket(wsUrl);

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    handleWsEvent(data);
  };

  ws.onclose = () => {
    setTimeout(setupWebSocket, 2000);
  };
}

function renderActiveSessions() {
  const container = document.getElementById("activeSessionsContainer");
  if (!container) return;

  const sessionIds = Object.keys(activeSessions);
  if (sessionIds.length === 0) {
    container.innerHTML = "";
    return;
  }

  let html = "";
  sessionIds.forEach(id => {
    const s = activeSessions[id];
    const conn = stationConnectors.find(c => c.id === s.connector_id);
    const num = conn ? conn.connector_number : (s.connector_number || 1);
    const nozzleName = conn ? conn.name : (s.connector_name || `Nozzle ${num}`);
    const rateColors = { 1: "#C084FC", 2: "#38BDF8", 3: "#4ADE80" };
    const nozzleColor = rateColors[num] || "#38BDF8";
    const nozzleIcon = (conn && conn.type_category === "DC") ? "⚡" : "🔌";
    const nozzleBg = (num === 1) ? "rgba(192, 132, 252, 0.15)" : (num === 2) ? "rgba(56, 189, 248, 0.15)" : "rgba(74, 222, 128, 0.15)";

    const kw = s.current_power_kw ? Number(s.current_power_kw).toFixed(1) : (s.current_power_w ? (s.current_power_w / 1000).toFixed(1) : "0.0");
    const soc = s.current_soc !== undefined ? Number(s.current_soc).toFixed(1) : "0.0";
    const kwh = s.energy_delivered_kwh !== undefined ? Number(s.energy_delivered_kwh).toFixed(2) : "0.00";
    const km = s.km_added !== undefined ? Number(s.km_added).toFixed(1) : "0.0";
    const speed = s.charging_speed_km_per_min !== undefined ? Number(s.charging_speed_km_per_min).toFixed(1) : "0.0";
    const savings = Math.round(s.money_saved_petrol || 0).toLocaleString("id-ID");
    const cost = Math.round(s.current_cost || 0).toLocaleString("id-ID");
    const volt = Math.round(s.voltage_v || s.voltage || 400);
    const amps = (s.current_a || s.current_amps || 0).toFixed(1);

    html += `
      <div class="card" id="sessionCard-${s.session_id}" style="background: #0E1626; border: 2px solid ${nozzleColor}; box-shadow: 0 0 35px rgba(0, 240, 255, 0.15); margin-bottom: 0;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 10px;">
          <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
            <span class="status-pill busy" style="font-weight: 800; font-size: 0.78rem; padding: 4px 10px;">⚡ CHARGING IN PROGRESS</span>
            <span class="status-pill" style="background: ${nozzleBg}; color: ${nozzleColor}; border: 1px solid ${nozzleColor}; font-weight: 800; font-size: 0.8rem; padding: 4px 12px; border-radius: 9999px;">
              ${nozzleIcon} ${nozzleName}
            </span>
            <span class="status-pill online" style="background: rgba(56, 189, 248, 0.18); color: #38BDF8; border-color: #0284C7; font-size: 0.78rem; padding: 4px 10px;">
              🚗 <span id="sessionCar-${s.session_id}">${s.car_model || 'Real EV'}</span>
            </span>
            <span id="sessionCode-${s.session_id}" style="font-size: 0.85rem; color: #94A3B8; font-family: monospace; font-weight: 600;">
              #${s.session_code || ''}
            </span>
          </div>
          <button class="btn btn-danger" onclick="emergencyStopKiosk(${s.session_id}, '${nozzleName}')" style="padding: 8px 16px; font-size: 0.85rem; font-weight: 700;">
            🛑 Emergency Stop
          </button>
        </div>

        <div class="kiosk-telemetry-grid">
          <div class="telemetry-dial" style="border-color: ${nozzleColor};">
            <div class="dial-value" id="sessionWatt-${s.session_id}">${kw}</div>
            <div class="dial-unit">kW DAYA</div>
          </div>

          <div>
            <div style="margin-bottom: 16px;">
              <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 6px;">
                <span style="color: var(--text-muted);">Baterai Mobil Listrik (BMS ISO 15118)</span>
                <span id="sessionSocVal-${s.session_id}" style="font-weight: 800; color: ${nozzleColor};">${soc}%</span>
              </div>
              <div style="height: 12px; background: var(--bg-input); border-radius: 9999px; overflow: hidden;">
                <div id="sessionSocBar-${s.session_id}" style="height: 100%; width: ${Math.min(100, Math.max(0, s.current_soc || 0))}%; background: linear-gradient(90deg, #00F0FF, #10B981); transition: width 0.5s ease;"></div>
              </div>
            </div>

            <div class="stat-grid" style="grid-template-columns: repeat(3, 1fr);">
              <div class="stat-item">
                <div class="label">Energi Terisi</div>
                <div class="val" id="sessionKwh-${s.session_id}" style="color: #fff;">${kwh} kWh</div>
              </div>
              <div class="stat-item">
                <div class="label">Jarak Tempuh</div>
                <div class="val" style="color: #4ADE80;" id="sessionKm-${s.session_id}">+${km} KM</div>
              </div>
              <div class="stat-item">
                <div class="label">Kecepatan Cas</div>
                <div class="val" style="color: var(--cyan-neon);" id="sessionSpeed-${s.session_id}">+${speed} km/m</div>
              </div>
              <div class="stat-item">
                <div class="label">Komparasi Hemat Bensin</div>
                <div class="val" style="color: #FBBF24;" id="sessionSavings-${s.session_id}">Hemat Rp ${savings}</div>
              </div>
              <div class="stat-item">
                <div class="label">Biaya SPKLU</div>
                <div class="val" style="color: #38BDF8;" id="sessionCost-${s.session_id}">Rp ${cost}</div>
              </div>
              <div class="stat-item">
                <div class="label">Tegangan / Arus</div>
                <div class="val" id="sessionVoltAmp-${s.session_id}">${volt} V / ${amps} A</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}

function updateSessionCard(sessionId) {
  const s = activeSessions[sessionId];
  if (!s) return;

  const card = document.getElementById(`sessionCard-${sessionId}`);
  if (!card) {
    renderActiveSessions();
    return;
  }

  const kw = s.current_power_kw ? Number(s.current_power_kw).toFixed(1) : (s.current_power_w ? (s.current_power_w / 1000).toFixed(1) : "0.0");
  const soc = s.current_soc !== undefined ? Number(s.current_soc).toFixed(1) : "0.0";
  const kwh = s.energy_delivered_kwh !== undefined ? Number(s.energy_delivered_kwh).toFixed(2) : "0.00";
  const km = s.km_added !== undefined ? Number(s.km_added).toFixed(1) : "0.0";
  const speed = s.charging_speed_km_per_min !== undefined ? Number(s.charging_speed_km_per_min).toFixed(1) : "0.0";
  const savings = Math.round(s.money_saved_petrol || 0).toLocaleString("id-ID");
  const cost = Math.round(s.current_cost || 0).toLocaleString("id-ID");
  const volt = Math.round(s.voltage_v || s.voltage || 400);
  const amps = (s.current_a || s.current_amps || 0).toFixed(1);

  const wattEl = document.getElementById(`sessionWatt-${sessionId}`);
  if (wattEl) wattEl.innerText = kw;

  const carEl = document.getElementById(`sessionCar-${sessionId}`);
  if (carEl && s.car_model) carEl.innerText = s.car_model;

  const socValEl = document.getElementById(`sessionSocVal-${sessionId}`);
  if (socValEl) socValEl.innerText = `${soc}%`;

  const socBarEl = document.getElementById(`sessionSocBar-${sessionId}`);
  if (socBarEl) socBarEl.style.width = `${Math.min(100, Math.max(0, s.current_soc || 0))}%`;

  const kwhEl = document.getElementById(`sessionKwh-${sessionId}`);
  if (kwhEl) kwhEl.innerText = `${kwh} kWh`;

  const kmEl = document.getElementById(`sessionKm-${sessionId}`);
  if (kmEl) kmEl.innerText = `+${km} KM`;

  const speedEl = document.getElementById(`sessionSpeed-${sessionId}`);
  if (speedEl) speedEl.innerText = `+${speed} km/m`;

  const savingsEl = document.getElementById(`sessionSavings-${sessionId}`);
  if (savingsEl) savingsEl.innerText = `Hemat Rp ${savings}`;

  const costEl = document.getElementById(`sessionCost-${sessionId}`);
  if (costEl) costEl.innerText = `Rp ${cost}`;

  const voltAmpEl = document.getElementById(`sessionVoltAmp-${sessionId}`);
  if (voltAmpEl) voltAmpEl.innerText = `${volt} V / ${amps} A`;
}

function handleWsEvent(data) {
  if (
    data.event === "PORT_NOZZLE_CONNECTED" ||
    data.event === "HANDSHAKE_COMPLETE" ||
    data.event === "NOZZLE_PLUGGED" || 
    data.event === "NOZZLE_UNPLUGGED" || 
    data.event === "NOZZLE_CLAIMED" ||
    data.event === "NOZZLE_RELEASED" ||
    data.event === "ADB_BATTERY_DISCONNECTED" ||
    data.event === "STATION_RESET"
  ) {
    if (data.event === "STATION_RESET") {
      activeSessions = {};
      renderActiveSessions();
    }
    loadStationData();
  } else if (data.event === "SESSION_STARTED") {
    activeSessions[data.session_id] = { ...data };
    renderActiveSessions();
    loadStationData();
  } else if (data.event === "TELEMETRY_UPDATE") {
    if (!activeSessions[data.session_id]) {
      activeSessions[data.session_id] = { ...data };
      renderActiveSessions();
    } else {
      Object.assign(activeSessions[data.session_id], data);
      updateSessionCard(data.session_id);
    }
  } else if (data.event === "SESSION_COMPLETED") {
    const s = activeSessions[data.session_id];
    delete activeSessions[data.session_id];
    renderActiveSessions();
    loadStationData();
    const totalKwh = (data.total_energy_kwh || 0).toFixed(2);
    const car = data.car_model || (s ? s.car_model : 'Real EV');
    showAppAlert(`Mobil: ${car}\nEnergi Terisi: ${totalKwh} kWh (+${data.km_added || 0} KM)\nBiaya Aktual: Rp ${Math.round(data.actual_cost || 0).toLocaleString('id-ID')}\nHemat vs Bensin: Rp ${(data.money_saved_petrol || 0).toLocaleString('id-ID')} (${data.savings_percentage || 60}%)\nRefund Saldo: Rp ${Math.round(data.refund_amount || 0).toLocaleString('id-ID')}`, {
      title: "Pengisian Selesai",
      type: "success"
    });
  }
}

async function emergencyStopKiosk(sessionId, nozzleLabel = "") {
  let targetSessionId = sessionId;
  if (!targetSessionId) {
    const keys = Object.keys(activeSessions);
    if (keys.length > 0) targetSessionId = keys[0];
    else return;
  }

  const label = nozzleLabel ? ` pada ${nozzleLabel}` : "";
  const ok = await showAppConfirm(`Hentikan pengisian darurat sekarang${label}?`, {
    title: "Emergency Stop",
    type: "error",
    confirmText: "Ya, Hentikan Darurat",
    cancelText: "Batal"
  });
  if (!ok) return;

  try {
    const res = await fetch("/api/station/stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: targetSessionId, user_id: 1 })
    });
    const result = await res.json();
    await showAppAlert(result.message, {
      title: "Status Pengisian",
      type: "info"
    });
    loadStationData();
  } catch (err) {
    await showAppAlert("Gagal stop: " + err, {
      title: "Gagal Stop",
      type: "error"
    });
  }
}

// Init
initQrCode();
loadStationData();
setupWebSocket();
