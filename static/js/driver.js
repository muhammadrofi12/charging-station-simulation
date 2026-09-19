const STATION_CODE = "CS-SDR-01";
let USER_ID = 1;
const TOTAL_PHONE_BATTERY_MAH = 5000;

let currentUser = null;
let userVehicles = [];
let userCards = [];
let stationConnectors = [];

let selectedVehicle = null;
let selectedConnector = null;
let pendingNozzleConnector = null;
let isPlugged = false;
let isSimulatedMode = false;
let currentStep = 1;
let targetMode = "FULL";
let paymentMethod = "WALLET";
let currentEstimate = null;
let activeSessionId = null;
let ws = null;
let adbBatteryState = null;

// =============================================================
// UNIVERSAL CUSTOM DIALOG SYSTEM (MODAL ALERT & CONFIRM)
// =============================================================
function showAppAlert(message, options = {}) {
  const {
    title = "Pemberitahuan",
    subtitle = "",
    type = "info", // 'info' | 'warning' | 'error' | 'success'
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

// Auth Tab Switcher
function switchAuthTab(tab) {
  const tabLogin = document.getElementById("tabAuthLogin");
  const tabReg = document.getElementById("tabAuthRegister");
  const fLogin = document.getElementById("formLogin");
  const fReg = document.getElementById("formRegister");
  if (tabLogin && tabReg && fLogin && fReg) {
    tabLogin.className = `tab-btn ${tab === 'login' ? 'active' : ''}`;
    tabReg.className = `tab-btn ${tab === 'register' ? 'active' : ''}`;
    fLogin.style.display = tab === 'login' ? 'block' : 'none';
    fReg.style.display = tab === 'register' ? 'block' : 'none';
  }
}

function quickFillAccount(username, password) {
  const uInput = document.getElementById("loginUsername");
  const pInput = document.getElementById("loginPassword");
  if (uInput && pInput) {
    uInput.value = username;
    pInput.value = password;
  }
}

async function handleLoginSubmit(e) {
  e.preventDefault();
  const u = document.getElementById("loginUsername").value.trim();
  const p = document.getElementById("loginPassword").value;
  const btn = document.getElementById("btnLoginSubmit");
  if (btn) {
    btn.innerText = "Memverifikasi...";
    btn.disabled = true;
  }

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: u, password: p })
    });
    const data = await res.json();
    if (!res.ok) {
      await showAppAlert(data.detail || "Username atau password salah!", { title: "Gagal Masuk", type: "error" });
      if (btn) {
        btn.innerText = "Masuk ke Akun ➜";
        btn.disabled = false;
      }
      return;
    }

    localStorage.setItem("voltx_user", JSON.stringify(data));
    if (btn) {
      btn.innerText = "Masuk ke Akun ➜";
      btn.disabled = false;
    }
    await initDriverApp();
  } catch (err) {
    await showAppAlert("Gagal koneksi ke server SPKLU: " + err, { title: "Koneksi Bermasalah", type: "error" });
    if (btn) {
      btn.innerText = "Masuk ke Akun ➜";
      btn.disabled = false;
    }
  }
}

async function handleRegisterSubmit(e) {
  e.preventDefault();
  const fullName = document.getElementById("regFullName").value.trim();
  const username = document.getElementById("regUsername").value.trim();
  const phone = document.getElementById("regPhone").value.trim();
  const password = document.getElementById("regPassword").value;
  const btn = document.getElementById("btnRegSubmit");
  if (btn) {
    btn.innerText = "Mendaftarkan...";
    btn.disabled = true;
  }

  try {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_name: fullName, username: username, phone: phone, password: password })
    });
    const data = await res.json();
    if (!res.ok) {
      await showAppAlert(data.detail || "Registrasi gagal!", { title: "Pendaftaran Gagal", type: "error" });
      if (btn) {
        btn.innerText = "Daftar & Dapatkan Saldo Rp 150.000 ➜";
        btn.disabled = false;
      }
      return;
    }

    await showAppAlert(`Selamat datang, ${data.full_name}!\nSaldo awal akun Anda: Rp ${data.wallet_balance.toLocaleString('id-ID')}`, { title: "Pendaftaran Berhasil", type: "success" });
    localStorage.setItem("voltx_user", JSON.stringify(data));
    if (btn) {
      btn.innerText = "Daftar & Dapatkan Saldo Rp 150.000 ➜";
      btn.disabled = false;
    }
    await initDriverApp();
  } catch (err) {
    await showAppAlert("Gagal registrasi: " + err, { title: "Error Registrasi", type: "error" });
    if (btn) {
      btn.innerText = "Daftar & Dapatkan Saldo Rp 150.000 ➜";
      btn.disabled = false;
    }
  }
}

async function logoutUser() {
  if (activeSessionId) {
    const ok = await showAppConfirm("Anda sedang memiliki sesi pengisian aktif!\nJika Anda keluar, pengisian tetap berjalan di stasiun. Yakin ingin keluar akun?", { title: "Sesi Pengisian Aktif", type: "warning", confirmText: "Ya, Keluar", cancelText: "Batal" });
    if (!ok) return;
  }

  closeReceiptModal();
  if (selectedConnector && selectedConnector.locked_by_user_id === USER_ID) {
    releaseNozzleClaim(selectedConnector.id);
  }

  localStorage.removeItem("voltx_user");
  currentUser = null;
  activeSessionId = null;
  selectedConnector = null;
  isPlugged = false;

  const headerName = document.getElementById("headerDriverName");
  if (headerName) {
    headerName.innerText = "-";
    headerName.removeAttribute("title");
  }
  const userBalText = document.getElementById("userBalanceText");
  if (userBalText) userBalText.innerText = "0";

  // Clean DOM view states
  document.getElementById("activeChargingView").style.display = "none";
  document.getElementById("step2View").style.display = "none";
  document.getElementById("step3View").style.display = "none";
  document.getElementById("step1View").style.display = "block";
  document.getElementById("wizardStepHeader").style.display = "flex";

  document.getElementById("authView").style.display = "block";
  document.getElementById("driverAppView").style.display = "none";
}

// Check if user has active session
async function checkUserActiveSession(userId) {
  try {
    const res = await fetch(`/api/station/user-active-session/${userId}`);
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.error("Gagal periksa sesi aktif user:", err);
  }
  return { has_active_session: false };
}

function restoreActiveSessionView(sessionData) {
  activeSessionId = sessionData.session_id;
  selectedConnector = stationConnectors.find(c => c.id === sessionData.connector_id) || {
    id: sessionData.connector_id,
    name: sessionData.connector_name,
    max_power_kw: sessionData.current_power_kw || 22.0
  };

  // Hide wizard and steps
  document.getElementById("step1View").style.display = "none";
  document.getElementById("step2View").style.display = "none";
  document.getElementById("step3View").style.display = "none";
  document.getElementById("wizardStepHeader").style.display = "none";

  // Show active view
  document.getElementById("activeChargingView").style.display = "block";

  const carLabel = document.getElementById("activeChargingCarLabel");
  if (carLabel && selectedVehicle) {
    carLabel.innerText = `${selectedVehicle.brand} ${selectedVehicle.model} (${selectedVehicle.license_plate})`;
  }

  // Populate live stats
  document.getElementById("driverLiveSoc").innerText = `${sessionData.current_soc.toFixed(1)}%`;
  const kw = sessionData.current_power_kw ? sessionData.current_power_kw.toFixed(1) : (sessionData.current_power_w ? (sessionData.current_power_w / 1000).toFixed(1) : "0.0");
  const wattElem = document.getElementById("driverLiveWatt") || document.getElementById("driverLiveKw");
  if (wattElem) wattElem.innerText = `${kw} kW`;

  const detailKw = document.getElementById("driverLiveKwDetail");
  if (detailKw) detailKw.innerText = `${kw} kW`;

  const mahElem = document.getElementById("driverLiveMah") || document.getElementById("driverLiveKwh");
  if (mahElem) mahElem.innerText = `${(sessionData.energy_delivered_kwh || 0).toFixed(2)} kWh`;

  document.getElementById("driverLiveCost").innerText = `Rp ${Math.round(sessionData.current_cost || 0).toLocaleString('id-ID')}`;
  document.getElementById("driverLiveRemaining").innerText = `Rp ${Math.round(sessionData.remaining_deposit || 0).toLocaleString('id-ID')}`;
  document.getElementById("driverLiveDeposit").innerText = `Rp ${Math.round(sessionData.deposit_paid || 0).toLocaleString('id-ID')}`;

  // Layman cards
  const kmElem = document.getElementById("driverLiveKm");
  if (kmElem) kmElem.innerText = `+${sessionData.km_added || 0} KM`;
  const speedElem = document.getElementById("driverLiveSpeed");
  if (speedElem) speedElem.innerText = `+${(sessionData.charging_speed_km_per_min || 0).toFixed(1)} km/m`;
  const savingsElem = document.getElementById("driverLiveSavings");
  if (savingsElem) savingsElem.innerText = `Rp ${Math.round(sessionData.money_saved_petrol || 0).toLocaleString('id-ID')}`;
  const etaElem = document.getElementById("driverLiveEta");
  if (etaElem) etaElem.innerText = `${sessionData.eta_minutes || 0} Mnt`;

  const taperBanner = document.getElementById("driverTaperingBanner");
  if (taperBanner) {
    taperBanner.style.display = sessionData.is_tapering ? "block" : "none";
  }
}

// -------------------------------------------------------------
// QR SCANNER & NOZZLE EXCLUSIVITY
// -------------------------------------------------------------
let html5QrScanner = null;
let isQrScannerOpen = false;

async function openQrScannerModal() {
  const modal = document.getElementById("qrScannerModal");
  if (!modal) return;
  modal.classList.add("open");
  isQrScannerOpen = true;

  const loadingElem = document.getElementById("qrCameraLoading");
  if (loadingElem) {
    loadingElem.style.display = "block";
    loadingElem.innerText = "Menginisialisasi kamera...";
  }
  const statusMsg = document.getElementById("qrScanStatusMsg");
  if (statusMsg) statusMsg.innerText = "Menginisialisasi kamera HP...";

  if (typeof Html5Qrcode !== "undefined") {
    try {
      if (!html5QrScanner) {
        html5QrScanner = new Html5Qrcode("qrCameraReader");
      }
      await html5QrScanner.start(
        { facingMode: "environment" },
        {
          fps: 10,
          qrbox: (viewfinderWidth, viewfinderHeight) => {
            const minEdge = Math.min(viewfinderWidth, viewfinderHeight);
            const qrboxSize = Math.floor(minEdge * 0.72);
            return { width: Math.max(160, qrboxSize), height: Math.max(160, qrboxSize) };
          }
        },
        (decodedText) => {
          handleQrCodeScanSuccess(decodedText);
        },
        () => {} // frame error ignore
      );
      if (loadingElem) loadingElem.style.display = "none";
      if (statusMsg) statusMsg.innerText = "Arahkan kamera ke QR Code Nozzle di Kiosk SPKLU";
    } catch (err) {
      console.warn("Kamera tidak dapat diakses atau diblokir:", err);
      if (loadingElem) {
        loadingElem.style.display = "block";
        loadingElem.innerHTML = "📷 Kamera tidak aktif / izin belum diberikan.<br><span style='font-size:0.75rem; color:#94A3B8;'>Pastikan Anda memberikan izin akses kamera pada browser Anda.</span>";
      }
      if (statusMsg) statusMsg.innerText = "Izin kamera diperlukan untuk memindai QR Code";
    }
  } else {
    if (loadingElem) {
      loadingElem.style.display = "block";
      loadingElem.innerHTML = "Scanner QR tidak dapat dimuat.";
    }
  }
}

async function closeQrScannerModal() {
  const modal = document.getElementById("qrScannerModal");
  if (modal) modal.classList.remove("open");
  isQrScannerOpen = false;

  if (html5QrScanner) {
    try {
      if (html5QrScanner.isScanning) {
        await html5QrScanner.stop();
      }
    } catch (e) {
      console.warn("Error stopping scanner:", e);
    }
  }
}

function handleQrCodeScanSuccess(decodedText) {
  if (!decodedText) return;

  // Extract nozzle number from text or URL (e.g. "/driver?nozzle=2", "http://.../driver?nozzle=1", or "2")
  let nozzleNum = null;
  const match = decodedText.match(/nozzle=(\d+)/i);
  if (match) {
    nozzleNum = parseInt(match[1]);
  } else {
    const directNum = parseInt(decodedText.trim());
    if (!isNaN(directNum) && directNum >= 1 && directNum <= 10) {
      nozzleNum = directNum;
    }
  }

  if (nozzleNum) {
    handleScannedNozzle(nozzleNum);
  } else {
    showAppAlert(`QR Code terdeteksi (${decodedText}), namun bukan format QR Nozzle SPKLU yang valid!`, {
      title: "QR Tidak Valid",
      type: "warning"
    });
  }
}

function showPendingNozzleUI(target) {
  if (!target) return;
  const pendingCard = document.getElementById("pendingNozzleCard");
  const pendingName = document.getElementById("pendingNozzleName");
  const pendingDesc = document.getElementById("pendingNozzleDesc");
  if (pendingName) {
    pendingName.innerText = `${target.name} (${target.connector_type} • Max ${Math.round(target.max_power_kw * 1000).toLocaleString('id-ID')} W)`;
  }
  if (pendingDesc) {
    pendingDesc.innerHTML = `🔌 Silakan ambil nozzle <b>${target.name}</b> dari totem SPKLU dan colokkan ke port charging mobil Anda.`;
  }
  if (pendingCard) {
    pendingCard.style.display = "block";
  }
  const heroCard = document.getElementById("scanHeroCard");
  if (heroCard) {
    heroCard.style.display = "none";
  }
}

function cancelPendingNozzle(resetSim = true) {
  pendingNozzleConnector = null;
  if (resetSim) isSimulatedMode = false;
  const pendingCard = document.getElementById("pendingNozzleCard");
  if (pendingCard) {
    pendingCard.style.display = "none";
  }
  const heroCard = document.getElementById("scanHeroCard");
  if (heroCard) {
    heroCard.style.display = "block";
  }
}

async function simulatePlugCable() {
  const target = pendingNozzleConnector || selectedConnector;
  if (!target) {
    await showAppAlert("Tidak ada nozzle yang sedang dipilih!", {
      title: "Peringatan",
      type: "warning"
    });
    return;
  }
  isSimulatedMode = true;
  await triggerSimulatedPlug(target.connector_number || target.id);
}

async function triggerSimulatedPlug(nozzleNumber) {
  await closeQrScannerModal();
  await loadStationData();

  const target = stationConnectors.find(c => c.connector_number === nozzleNumber || c.id === nozzleNumber);
  if (!target) {
    await showAppAlert(`Nozzle #${nozzleNumber} tidak ditemukan di stasiun!`, { title: "Error", type: "error" });
    return;
  }
  if (target.status === "CHARGING") {
    await showAppAlert(`Nozzle ${target.name} saat ini sedang digunakan untuk pengisian daya oleh kendaraan lain!\n\nSilakan pilih nozzle lain yang berstatus Standby.`, {
      title: "Nozzle Sedang Digunakan",
      type: "warning"
    });
    return;
  }
  if (target.locked_by_user_id && target.locked_by_user_id !== USER_ID) {
    await showAppAlert(`Nozzle ${target.name} saat ini sedang diklaim / terkunci oleh pengemudi lain!\n\nSilakan pilih nozzle lain yang sedang Standby.`, {
      title: "Nozzle Terkunci",
      type: "warning"
    });
    return;
  }

  // Cek apakah akun ini sudah mengunci nozzle LAIN
  const myLocked = stationConnectors.find(c => c.locked_by_user_id === USER_ID && c.id !== target.id);
  if (myLocked) {
    await showAppAlert(`Akun Anda saat ini sedang memilih ${myLocked.name}!\n\nBatalkan pilihan ${myLocked.name} terlebih dahulu jika ingin memilih nozzle lain.`, {
      title: "Nozzle Lain Sedang Dipilih",
      type: "warning"
    });
    return;
  }

  // Jika nozzle ini SUDAH terkunci ke akun ini dan sudah CONNECTED, langsung lanjutkan ke Step 2
  if (target.locked_by_user_id === USER_ID && target.status === "CONNECTED") {
    selectedConnector = target;
    isPlugged = true;
    goToStep(2);
    return;
  }

  selectedConnector = target;
  openHandshakeModal(target);

  try {
    const res = await fetch(`/api/station/connector/${target.id}/plug`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: USER_ID })
    });
    if (!res.ok) {
      const err = await res.json();
      closeHandshakeModal();
      await showAppAlert(err.detail || "Gagal inisialisasi nozzle!", { title: "Nozzle Tidak Tersedia", type: "error" });
      await loadStationData();
      return;
    }
  } catch (err) {
    closeHandshakeModal();
    await showAppAlert("Gagal memulai verifikasi kendaraan: " + err, { title: "Koneksi Error", type: "error" });
    await loadStationData();
  }
}

let handshakeSafetyTimer = null;

function openHandshakeModal(connector) {
  const modal = document.getElementById("handshakeModal");
  if (!modal) return;

  for (let i = 1; i <= 4; i++) {
    const s = document.getElementById(`hsStep${i}`);
    if (s) s.className = "handshake-step-item";
  }
  const s1 = document.getElementById("hsStep1");
  if (s1) s1.className = "handshake-step-item active";

  const sub = document.getElementById("handshakeSubtitle");
  if (sub) sub.innerText = `Menghubungkan ${connector.name}...`;

  const msg = document.getElementById("handshakeFooterMsg");
  if (msg) msg.innerText = "⏳ Mengunci konektor nozzle secara mekanikal ke port mobil...";

  modal.classList.add("open");

  // Fallback safety timer: jika websocket telat/missed event, otomatis tutup dan lanjut dalam 7 detik
  if (handshakeSafetyTimer) clearTimeout(handshakeSafetyTimer);
  handshakeSafetyTimer = setTimeout(async () => {
    if (modal.classList.contains("open")) {
      console.warn("Handshake safety timeout reached, closing modal & advancing...");
      await finishHandshakeManually();
    }
  }, 7000);
}

function closeHandshakeModal() {
  if (handshakeSafetyTimer) {
    clearTimeout(handshakeSafetyTimer);
    handshakeSafetyTimer = null;
  }
  const modal = document.getElementById("handshakeModal");
  if (modal) modal.classList.remove("open");
}

async function finishHandshakeManually() {
  closeHandshakeModal();
  const target = selectedConnector || pendingNozzleConnector;
  if (target) {
    selectedConnector = target;
    if (pendingNozzleConnector) cancelPendingNozzle();
    const claimed = await claimNozzle(target.id, true);
    if (claimed) {
      goToStep(2);
    }
  } else {
    loadStationData();
  }
}

async function handleScannedNozzle(nozzleNumber) {
  if (window.location.search) {
    window.history.replaceState({}, document.title, window.location.pathname);
  }
  await triggerSimulatedPlug(nozzleNumber);
}

// Nozzle Claim & Exclusivity Helpers
async function claimNozzle(connectorId, isFromQr = false) {
  if (!connectorId || !USER_ID) return false;

  const myLocked = stationConnectors.find(c => c.locked_by_user_id === USER_ID && c.id !== connectorId);
  if (myLocked) {
    await showAppAlert(`Akun Anda saat ini sudah mengklaim ${myLocked.name}!\n\nBatalkan pilihan ${myLocked.name} terlebih dahulu jika ingin mengklaim nozzle lain.`, {
      title: "Nozzle Lain Sedang Diklaim",
      type: "warning"
    });
    return false;
  }

  try {
    const res = await fetch(`/api/station/connector/${connectorId}/claim`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: USER_ID })
    });
    const data = await res.json();
    if (!res.ok) {
      await showAppAlert(data.detail || "Gagal mengklaim nozzle!", {
        title: "Klaim Gagal",
        type: "error"
      });
      return false;
    }
    const updated = stationConnectors.find(c => c.id === connectorId);
    if (updated) {
      updated.locked_by_user_id = USER_ID;
      selectedConnector = updated;
    }
    isPlugged = true;
    return true;
  } catch (err) {
    await showAppAlert("Koneksi gagal saat mengklaim nozzle: " + err, {
      title: "Koneksi Bermasalah",
      type: "error"
    });
    return false;
  }
}

async function releaseNozzleClaim(connectorId) {
  if (!connectorId || !USER_ID) return;
  try {
    await fetch(`/api/station/connector/${connectorId}/release`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: USER_ID })
    });
    const updated = stationConnectors.find(c => c.id === connectorId);
    if (updated && updated.locked_by_user_id === USER_ID) {
      updated.locked_by_user_id = null;
    }
  } catch (err) {
    console.warn("Gagal melepas nozzle claim:", err);
  }
}

function resumeActiveClaim() {
  const myLocked = stationConnectors.find(c => c.locked_by_user_id === USER_ID);
  if (myLocked) {
    selectedConnector = myLocked;
    isPlugged = true;
    goToStep(2);
  }
}

async function cancelActiveClaim() {
  const myLocked = stationConnectors.find(c => c.locked_by_user_id === USER_ID);
  if (myLocked) {
    const ok = await showAppConfirm(`Batalkan pilihan ${myLocked.name} agar akun Anda dapat memilih nozzle lain?`, {
      title: "Batalkan Pilihan Nozzle",
      confirmText: "Ya, Batalkan",
      cancelText: "Kembali",
      type: "warning"
    });
    if (ok) {
      await releaseNozzleClaim(myLocked.id);
      await loadStationData();
    }
  }
}

// Initial Load
async function initDriverApp() {
  const storedUser = localStorage.getItem("voltx_user");
  if (!storedUser) {
    document.getElementById("authView").style.display = "block";
    document.getElementById("driverAppView").style.display = "none";
    return;
  }

  try {
    currentUser = JSON.parse(storedUser);
    USER_ID = currentUser.id;
  } catch (e) {
    localStorage.removeItem("voltx_user");
    document.getElementById("authView").style.display = "block";
    document.getElementById("driverAppView").style.display = "none";
    return;
  }

  document.getElementById("authView").style.display = "none";
  document.getElementById("driverAppView").style.display = "flex";

  // Pre-fill header immediately from storedUser
  const headerName = document.getElementById("headerDriverName");
  if (headerName && currentUser && currentUser.full_name) {
    headerName.innerText = currentUser.full_name;
    headerName.title = currentUser.full_name;
  }
  const headerRole = document.getElementById("headerRoleBadge");
  if (headerRole && currentUser) {
    headerRole.innerText = currentUser.role || "DRIVER";
    headerRole.className = currentUser.role === "OPERATOR" ? "status-pill busy" : "status-pill online";
  }
  const userBalText = document.getElementById("userBalanceText");
  if (userBalText && currentUser && currentUser.wallet_balance !== undefined) {
    userBalText.innerText = currentUser.wallet_balance.toLocaleString("id-ID");
  }

  await loadUserData();
  await loadStationData();
  setupWebSocket();
  fetchAdbBatteryInitial();
  loadDevPortStatus();

  // CHECK ACTIVE CHARGING SESSION (FOR STATE RECOVERY ON REFRESH)
  const active = await checkUserActiveSession(USER_ID);
  if (active && active.has_active_session) {
    restoreActiveSessionView(active);
  } else {
    document.getElementById("wizardStepHeader").style.display = "flex";

    // Cek apakah driver datang dari scan QR Nozzle khusus (?nozzle=1, ?nozzle=2, ?nozzle=3)
    const urlParams = new URLSearchParams(window.location.search);
    const nozzleNum = urlParams.get("nozzle");
    if (nozzleNum) {
      await handleScannedNozzle(parseInt(nozzleNum));
      return;
    }

    // Cek apakah akun ini sudah mengunci salah satu nozzle (misal dari device lain atau sebelum refresh)
    const myClaimed = stationConnectors.find(c => c.locked_by_user_id === USER_ID && c.status === "CONNECTED");
    if (myClaimed) {
      selectedConnector = myClaimed;
      isPlugged = true;
      goToStep(2);
      return;
    }

    goToStep(1);
  }
}

// Wizard Step Navigation
function goToStep(step) {
  currentStep = step;

  if (step >= 2) {
    cancelPendingNozzle(false);
  }

  // If returning to step 1 without active charging, release nozzle claim & lock
  if (step === 1 && !activeSessionId) {
    if (selectedConnector && selectedConnector.locked_by_user_id === USER_ID) {
      releaseNozzleClaim(selectedConnector.id);
    }
    if (isPlugged) {
      isPlugged = false;
      autoHandleUsbUnplugged();
    }
    isSimulatedMode = false;
    selectedConnector = null;
  }

  // Connected device status card only displays once connected (Step 2 & 3)
  const deviceCard = document.getElementById("connectedDeviceCard");
  if (deviceCard) {
    deviceCard.style.display = step >= 2 ? "block" : "none";
  }

  // Views
  document.getElementById("step1View").style.display = step === 1 ? "block" : "none";
  document.getElementById("step2View").style.display = step === 2 ? "block" : "none";
  document.getElementById("step3View").style.display = step === 3 ? "block" : "none";
  document.getElementById("activeChargingView").style.display = "none";

  // Step Tabs Highlighting
  document.getElementById("stepTab1").className = `step-pill ${step >= 1 ? 'active' : ''}`;
  document.getElementById("stepTab2").className = `step-pill ${step >= 2 ? 'active' : ''}`;
  document.getElementById("stepTab3").className = `step-pill ${step >= 3 ? 'active' : ''}`;

  document.getElementById("stepLine1").className = `step-line ${step >= 2 ? 'active' : ''}`;
  document.getElementById("stepLine2").className = `step-line ${step >= 3 ? 'active' : ''}`;

  if (step === 2) {
    if (selectedConnector) {
      document.getElementById("step2NozzleName").innerText = `${selectedConnector.name} (Max ${Math.round(selectedConnector.max_power_kw * 1000).toLocaleString('id-ID')} W)`;
    }
    updateCarDisplay();
    updateEstimate();
  }

  if (step === 3) {
    const updateDepositText = () => {
      const cost = (currentEstimate && currentEstimate.estimated_cost > 0) ? currentEstimate.estimated_cost : 25000;
      const payElem = document.getElementById("payDepositAmountText");
      if (payElem) payElem.innerText = `Rp ${Math.round(cost).toLocaleString('id-ID')}`;
    };
    if (!currentEstimate || currentEstimate.estimated_cost <= 0) {
      updateEstimate().then(updateDepositText);
    } else {
      updateDepositText();
    }
    setPaymentMethod(paymentMethod);
  }
}

async function loadUserData() {
  try {
    const [userRes, vehiclesRes, cardsRes] = await Promise.all([
      fetch(`/api/auth/user/${USER_ID}`),
      fetch(`/api/auth/vehicles/${USER_ID}`),
      fetch(`/api/auth/cards/${USER_ID}`)
    ]);

    currentUser = await userRes.json();
    userVehicles = await vehiclesRes.json();
    userCards = await cardsRes.json();

    const userBalEl = document.getElementById("userBalanceText");
    if (userBalEl && currentUser.wallet_balance !== undefined) {
      userBalEl.innerText = currentUser.wallet_balance.toLocaleString("id-ID");
    }
    const walletBalEl = document.getElementById("walletBalDesc");
    if (walletBalEl && currentUser.wallet_balance !== undefined) {
      walletBalEl.innerText = currentUser.wallet_balance.toLocaleString("id-ID");
    }

    const driverNameEl = document.getElementById("driverName");
    if (driverNameEl && currentUser.full_name) {
      driverNameEl.innerText = currentUser.full_name;
    }

    const headerName = document.getElementById("headerDriverName");
    if (headerName && currentUser.full_name) {
      headerName.innerText = currentUser.full_name;
      headerName.title = currentUser.full_name;
    }
    const headerRole = document.getElementById("headerRoleBadge");
    if (headerRole) {
      headerRole.innerText = currentUser.role || "DRIVER";
      headerRole.className = currentUser.role === "OPERATOR" ? "status-pill busy" : "status-pill online";
    }

    // Auto-select Real EV or user's active vehicle (ignore legacy Smartphone)
    const evs = (userVehicles || []).filter(v => v.brand !== "Smartphone");
    selectedVehicle = evs.length > 0 ? evs[0] : (userVehicles && userVehicles[0] ? userVehicles[0] : null);
    if (selectedVehicle) {
      updateCarDisplay();
    }

    renderEmoneyCards();
  } catch (err) {
    console.error("Gagal load data user:", err);
  }
}

function updateCarDisplay() {
  if (!selectedVehicle) return;
  const soc = selectedVehicle.current_soc || 28.0;
  const cap = selectedVehicle.battery_capacity_kwh || 72.6;
  const efficiency = selectedVehicle.efficiency_km_kwh || 6.8;
  const arch = selectedVehicle.architecture_voltage || 400.0;
  const currentKwh = ((soc / 100) * cap).toFixed(1);
  const remainingKwh = Math.max(0, cap - ((soc / 100) * cap)).toFixed(1);

  const carNameElem = document.getElementById("driverCarName");
  if (carNameElem) carNameElem.innerText = `${selectedVehicle.brand} ${selectedVehicle.model}`;

  const carSpecsElem = document.getElementById("driverCarSpecs");
  if (carSpecsElem) carSpecsElem.innerText = `Plat: ${selectedVehicle.license_plate} • Baterai: ${cap} kWh • Arsitektur ${Math.round(arch)}V`;

  const statusElem = document.getElementById("carBatteryStatus");
  if (statusElem) {
    statusElem.innerText = `${soc.toFixed(1)}% (${currentKwh} / ${cap} kWh)`;
  }

  const barElem = document.getElementById("carBatteryBar");
  if (barElem) {
    barElem.style.width = `${soc}%`;
  }

  const inputElem = document.getElementById("inputManualKwh");
  const hintElem = document.getElementById("maxManualKwhHint");
  if (inputElem) {
    inputElem.max = Math.ceil(remainingKwh);
    // Only set default if field is completely empty and user is not actively typing in it
    if (document.activeElement !== inputElem && !inputElem.value) {
      inputElem.value = Math.min(20, Math.ceil(remainingKwh));
    }
  }
  if (hintElem) {
    hintElem.innerText = `Max: ${remainingKwh} kWh`;
  }

  const targetDesc = document.getElementById("targetModeSummary");
  if (targetDesc) {
    if (targetMode === 'FULL_80') {
      const neededKwh = Math.max(0, (0.80 - (soc / 100)) * cap).toFixed(1);
      targetDesc.innerText = `🎯 Cas hingga batas 80% (+${neededKwh} kWh). Rekomendasi pabrikan EV untuk menjaga keawetan sel baterai.`;
    } else if (targetMode === 'FULL_100') {
      targetDesc.innerText = `🎯 Cas hingga 100% penuh (+${remainingKwh} kWh). Cocok untuk persiapan perjalanan jarak jauh.`;
    } else {
      const raw = inputElem ? inputElem.value.trim() : "";
      if (raw === "") {
        targetDesc.innerText = "🎯 Masukkan jumlah energi yang diinginkan (kWh)...";
      } else {
        const val = parseFloat(raw) || 0;
        const targetSoc = Math.min(100, Math.round(soc + (val / cap * 100)));
        targetDesc.innerText = `🎯 Target manual: +${val} kWh (Baterai akan terisi menjadi ~${targetSoc}%)`;
      }
    }
  }

  if (currentStep === 2) updateEstimate();
}

function resetEstimateDisplay() {
  const estEnergy = document.getElementById("estEnergy");
  if (estEnergy) estEnergy.innerText = "0 kWh";
  const estKm = document.getElementById("estKm");
  if (estKm) estKm.innerText = "+0 KM";
  const estDuration = document.getElementById("estDuration");
  if (estDuration) estDuration.innerText = "0 Menit";
  const estDeposit = document.getElementById("estTotalDeposit");
  if (estDeposit) estDeposit.innerText = "Rp 0";
  const qrisText = document.getElementById("qrisAmountText");
  if (qrisText) qrisText.innerText = "Rp 0";
}

function onManualKwhChanged() {
  const inputElem = document.getElementById("inputManualKwh");
  if (!inputElem) return;
  const raw = inputElem.value.trim();
  const targetDesc = document.getElementById("targetModeSummary");
  const cap = selectedVehicle?.battery_capacity_kwh || 72.6;
  const soc = selectedVehicle?.current_soc || 28.0;
  const remainingKwh = Math.max(0, cap - ((soc / 100) * cap));

  if (raw === "") {
    if (targetDesc) {
      targetDesc.innerText = "🎯 Masukkan jumlah energi kWh yang diinginkan...";
    }
    resetEstimateDisplay();
    return;
  }

  let val = parseFloat(raw);
  if (isNaN(val) || val <= 0) {
    if (targetDesc) {
      targetDesc.innerText = "🎯 Masukkan angka kWh di atas 0";
    }
    resetEstimateDisplay();
    return;
  }

  if (val > remainingKwh) {
    val = parseFloat(remainingKwh.toFixed(1));
    inputElem.value = val;
  }

  const targetSoc = Math.min(100, Math.round(soc + (val / cap * 100)));
  if (targetDesc) {
    targetDesc.innerText = `🎯 Target manual: +${val} kWh (Baterai akan terisi menjadi ~${targetSoc}%)`;
  }

  updateEstimate();
}

function onManualKwhBlur() {
  const inputElem = document.getElementById("inputManualKwh");
  if (!inputElem) return;
  const raw = inputElem.value.trim();
  if (raw === "" || parseFloat(raw) <= 0) {
    const cap = selectedVehicle?.battery_capacity_kwh || 72.6;
    const soc = selectedVehicle?.current_soc || 28.0;
    const remainingKwh = Math.max(0, cap - ((soc / 100) * cap));
    inputElem.value = Math.min(20, Math.ceil(remainingKwh));
    onManualKwhChanged();
  }
}

function quickSetKwh(amount) {
  const inputElem = document.getElementById("inputManualKwh");
  if (inputElem) {
    const cap = selectedVehicle?.battery_capacity_kwh || 72.6;
    const soc = selectedVehicle?.current_soc || 28.0;
    const remainingKwh = Math.max(0, cap - ((soc / 100) * cap));
    inputElem.value = Math.min(amount, Math.ceil(remainingKwh));
    onManualKwhChanged();
  }
}

function renderEmoneyCards() {
  const select = document.getElementById("emoneyCardSelect");
  const modalSelect = document.getElementById("modalEmoneyCardSelect");
  if (select) select.innerHTML = "";
  if (modalSelect) modalSelect.innerHTML = "";

  userCards.forEach(card => {
    const opt = document.createElement("option");
    opt.value = card.card_uid;
    opt.innerText = `${card.card_name} (${card.card_uid}) - Saldo: Rp ${card.balance.toLocaleString('id-ID')}`;
    if (select) select.appendChild(opt);

    if (modalSelect) {
      const optModal = document.createElement("option");
      optModal.value = card.card_uid;
      optModal.innerText = `${card.card_name} - Saldo: Rp ${card.balance.toLocaleString('id-ID')}`;
      modalSelect.appendChild(optModal);
    }
  });
}

// Station & Connectors
async function loadStationData() {
  try {
    const res = await fetch(`/api/station/${STATION_CODE}`);
    const data = await res.json();
    stationConnectors = data.connectors;

    if (currentStep >= 2 && selectedConnector) {
      const updated = stationConnectors.find(c => c.id === selectedConnector.id);
      if (updated) selectedConnector = updated;
    }
    updateNozzlePickersUI();
  } catch (err) {
    console.error("Gagal load station:", err);
  }
}

function updateNozzlePickersUI() {
  if (!stationConnectors || stationConnectors.length === 0) return;

  const myLockedConnector = stationConnectors.find(c => c.locked_by_user_id === USER_ID);
  const banner = document.getElementById("activeClaimBanner");
  const bannerText = document.getElementById("activeClaimBannerText");

  if (banner) {
    if (myLockedConnector && myLockedConnector.status !== "CHARGING" && currentStep === 1) {
      banner.style.display = "block";
      if (bannerText) {
        bannerText.innerHTML = `Akun Anda saat ini sedang memilih <b>${myLockedConnector.name}</b>. Selesaikan konfigurasi atau batalkan jika ingin berpindah ke nozzle lain.`;
      }
    } else {
      banner.style.display = "none";
    }
  }

  stationConnectors.forEach(c => {
    const btn = document.getElementById(`btnDemoNozzle${c.connector_number}`);
    const badge = document.getElementById(`badgeNozzleStatus${c.connector_number}`);
    const modalBtn = document.getElementById(`btnQrScanModalNozzle${c.connector_number}`);
    if (!btn) return;

    const isCharging = c.status === "CHARGING";
    const isLockedByOther = !!(c.locked_by_user_id && c.locked_by_user_id !== USER_ID);
    const isLockedByMe = (c.locked_by_user_id === USER_ID);

    if (isCharging) {
      btn.disabled = true;
      btn.style.opacity = "0.45";
      btn.style.cursor = "not-allowed";
      btn.style.borderColor = "rgba(239, 68, 68, 0.4)";
      btn.style.background = "rgba(239, 68, 68, 0.08)";
      if (badge) {
        badge.innerHTML = `<span class="status-pill busy" style="font-size:0.65rem; padding: 2px 7px;">⚡ SEDANG MENGISI</span>`;
      }
      if (modalBtn) {
        modalBtn.disabled = true;
        modalBtn.style.opacity = "0.45";
        modalBtn.style.borderColor = "rgba(239, 68, 68, 0.5)";
        modalBtn.style.cursor = "not-allowed";
        modalBtn.title = "Nozzle sedang aktif mengisi kendaraan lain";
      }
    } else if (isLockedByOther) {
      btn.disabled = true;
      btn.style.opacity = "0.55";
      btn.style.cursor = "not-allowed";
      btn.style.borderColor = "rgba(245, 158, 11, 0.4)";
      btn.style.background = "rgba(245, 158, 11, 0.08)";
      if (badge) {
        badge.innerHTML = `<span class="status-pill warning" style="font-size:0.65rem; padding: 2px 7px;">🔒 TERKUNCI</span>`;
      }
      if (modalBtn) {
        modalBtn.disabled = true;
        modalBtn.style.opacity = "0.5";
        modalBtn.style.borderColor = "rgba(245, 158, 11, 0.5)";
        modalBtn.style.cursor = "not-allowed";
        modalBtn.title = "Nozzle sedang diklaim oleh pengguna lain";
      }
    } else if (myLockedConnector && !isLockedByMe) {
      // Akun ini SUDAH memilih nozzle lain, kunci nozzle ini agar tidak bisa dipilih!
      btn.disabled = true;
      btn.style.opacity = "0.4";
      btn.style.cursor = "not-allowed";
      btn.style.borderColor = "rgba(148, 163, 184, 0.2)";
      btn.style.background = "rgba(15, 23, 42, 0.4)";
      if (badge) {
        badge.innerHTML = `<span class="status-pill" style="font-size:0.65rem; padding: 2px 7px; background: rgba(148, 163, 184, 0.15); color: #94A3B8;">🔒 ANDA MEMILIH ${myLockedConnector.name.split(':')[0]}</span>`;
      }
      if (modalBtn) {
        modalBtn.disabled = true;
        modalBtn.style.opacity = "0.4";
        modalBtn.style.borderColor = "rgba(148, 163, 184, 0.3)";
        modalBtn.style.cursor = "not-allowed";
        modalBtn.title = `Akun Anda sedang aktif di ${myLockedConnector.name}`;
      }
    } else if (isLockedByMe) {
      // Nozzle ini adalah nozzle yang sedang dipilih oleh akun ini
      btn.disabled = false;
      btn.style.opacity = "1";
      btn.style.cursor = "pointer";
      btn.style.borderColor = "rgba(0, 240, 255, 0.6)";
      btn.style.background = "rgba(0, 240, 255, 0.08)";
      if (badge) {
        badge.innerHTML = `<span class="status-pill success" style="font-size:0.65rem; padding: 2px 7px; background: rgba(0, 240, 255, 0.15); color: #00F0FF; border: 1px solid rgba(0,240,255,0.4);">👉 SEDANG ANDA PILIH</span>`;
      }
      if (modalBtn) {
        modalBtn.disabled = false;
        modalBtn.style.opacity = "1";
        modalBtn.style.borderColor = "#00F0FF";
        modalBtn.style.cursor = "pointer";
        modalBtn.title = "Lanjutkan konfigurasi nozzle ini";
      }
    } else {
      btn.disabled = false;
      btn.style.opacity = "1";
      btn.style.cursor = "pointer";
      btn.style.borderColor = "";
      btn.style.background = "";
      const rateColors = { 1: "#C084FC", 2: "#38BDF8", 3: "#4ADE80" };
      const color = rateColors[c.connector_number] || "#38BDF8";
      if (badge) {
        badge.innerHTML = `<span style="color: ${color}; font-weight: 800; font-size: 0.78rem;">Rp ${c.tariff_per_kwh.toLocaleString("id-ID")}/kWh</span>`;
      }
      if (modalBtn) {
        modalBtn.disabled = false;
        modalBtn.style.opacity = "1";
        modalBtn.style.borderColor = "";
        modalBtn.style.cursor = "pointer";
        modalBtn.title = "";
      }
    }
  });
}

// -------------------------------------------------------------
// SENSOR OTOMATIS BATERAI HP ASLI (VIA ADB MONITOR)
// -------------------------------------------------------------
async function fetchAdbBatteryInitial() {
  try {
    const res = await fetch("/api/station/adb-battery");
    const data = await res.json();
    if (data && data.connected) {
      handleAdbBatteryUpdate(data);
    } else {
      handleAdbBatteryDisconnected();
    }
  } catch (err) {
    console.log("Initial ADB fetch skipped:", err);
    handleAdbBatteryDisconnected();
  }
}

function handleAdbBatteryDisconnected() {
  if (isSimulatedMode) {
    return;
  }
  adbBatteryState = { connected: false };
  isPlugged = false;

  const badge = document.getElementById("usbDetectBadge");
  if (badge) {
    badge.className = "status-pill warning";
    badge.innerHTML = "📱 Kabel USB Belum Tercolok (Standby)";
  }

  const phoneBatteryElem = document.getElementById("phoneStatusBarBattery");
  if (phoneBatteryElem) {
    const soc = selectedVehicle ? selectedVehicle.current_soc : 45;
    phoneBatteryElem.innerText = `🔋 ${soc}%`;
  }

  const desktopAdbBadge = document.getElementById("desktopAdbStatus");
  if (desktopAdbBadge) {
    desktopAdbBadge.className = "status-pill warning";
    desktopAdbBadge.innerText = "📱 Status Kabel: Belum Tercolok";
  }

  const carBatteryStatus = document.getElementById("carBatteryStatus");
  if (carBatteryStatus) {
    const soc = selectedVehicle ? selectedVehicle.current_soc : 45;
    carBatteryStatus.innerText = `${soc}% (Standby / Belum Colok)`;
  }

  // If user had moved to Step 2 or 3 without starting charging, return to Step 1 and ask to plug again
  if ((currentStep === 2 || currentStep === 3) && !activeSessionId) {
    if (selectedConnector) {
      pendingNozzleConnector = selectedConnector;
    }
    selectedConnector = null;
    goToStep(1);
    if (pendingNozzleConnector) {
      showPendingNozzleUI(pendingNozzleConnector);
    }
  }

  loadStationData();
}

function handleAdbBatteryUpdate(data) {
  adbBatteryState = data;
  const level = data.level;
  const isPluggedIn = data.usb_powered || data.ac_powered || data.is_charging;

  // Update vehicle SoC from real phone battery level
  if (selectedVehicle) {
    selectedVehicle.current_soc = level;
    updateCarDisplay();

    // Sync to backend DB
    fetch(`/api/station/vehicle/${selectedVehicle.id}/soc`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ soc: level })
    }).catch(() => {});

    // If active charging session, sync live session
    if (activeSessionId) {
      fetch(`/api/station/session/${activeSessionId}/sync-battery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ soc: level })
      }).catch(() => {});
    }
  }

  const badge = document.getElementById("usbDetectBadge");
  if (badge) {
    badge.style.display = "flex";
    const tempC = data.temperature ? (data.temperature / 10).toFixed(1) : "32.0";
    const volt = data.voltage ? `${data.voltage} mV` : "";
    if (isPluggedIn) {
      badge.className = "status-pill busy";
      badge.innerHTML = `⚡ USB TERHUBUNG! Baterai HP: ${level}% • Suhu: ${tempC}°C • ${volt}`;
    } else {
      badge.className = "status-pill warning";
      badge.innerHTML = `📱 Baterai HP: ${level}% • USB Belum Tercolok`;
    }
  }

  // Sync to phone frame status bar and desktop presenter board
  const phoneBatteryElem = document.getElementById("phoneStatusBarBattery");
  if (phoneBatteryElem) {
    phoneBatteryElem.innerText = `${isPluggedIn ? '⚡' : '🔋'} ${level}%`;
  }
  const desktopAdbBadge = document.getElementById("desktopAdbStatus");
  if (desktopAdbBadge) {
    if (isPluggedIn) {
      desktopAdbBadge.className = "status-pill busy";
      desktopAdbBadge.innerText = `⚡ ADB USB Connected (${level}%)`;
    } else {
      desktopAdbBadge.className = "status-pill online";
      desktopAdbBadge.innerText = `📱 ADB Standby (${level}%)`;
    }
  }
}

async function autoHandleUsbUnplugged() {
  if (!selectedConnector) return;
  try {
    if (USER_ID && selectedConnector.locked_by_user_id === USER_ID) {
      await releaseNozzleClaim(selectedConnector.id);
    }
    await fetch(`/api/station/connector/${selectedConnector.id}/unplug`, { method: "POST" });
    isPlugged = false;
    isSimulatedMode = false;
    loadStationData();
  } catch (err) {
    console.error("Gagal auto unplug:", err);
  }
}


// Target Mode & Estimate
function selectTargetMode(mode) {
  targetMode = mode;
  if (mode === 'FULL_80' && selectedVehicle && (selectedVehicle.current_soc || 0) >= 80.0) {
    showAppAlert(`Baterai mobil Anda saat ini sudah ${(selectedVehicle.current_soc || 80).toFixed(1)}%. Mode cas otomatis dialihkan ke 100% (Penuh).`, {
      title: "Baterai Sudah di Atas 80%",
      type: "info"
    });
    targetMode = 'FULL_100';
  }

  const tab80 = document.getElementById("tabFull80");
  const tab100 = document.getElementById("tabFull100");
  const tabMan = document.getElementById("tabManualKwh");

  if (tab80) tab80.className = `tab-btn ${targetMode === 'FULL_80' ? 'active' : ''}`;
  if (tab100) tab100.className = `tab-btn ${targetMode === 'FULL_100' ? 'active' : ''}`;
  if (tabMan) tabMan.className = `tab-btn ${targetMode === 'MANUAL_KWH' ? 'active' : ''}`;

  const box = document.getElementById("manualKwhBox");
  if (box) box.style.display = targetMode === 'MANUAL_KWH' ? 'block' : 'none';

  if (targetMode === 'MANUAL_KWH') {
    const inputElem = document.getElementById("inputManualKwh");
    if (inputElem && (!inputElem.value || parseFloat(inputElem.value) <= 0)) {
      const cap = selectedVehicle?.battery_capacity_kwh || 72.6;
      const soc = selectedVehicle?.current_soc || 28.0;
      const remainingKwh = Math.max(0, cap - ((soc / 100) * cap));
      inputElem.value = Math.min(20, Math.ceil(remainingKwh));
    }
  }

  updateCarDisplay();
  updateEstimate();
}

async function updateEstimate() {
  if (!selectedVehicle || !selectedConnector) return;

  const cap = selectedVehicle.battery_capacity_kwh || 72.6;
  const efficiency = selectedVehicle.efficiency_km_kwh || 6.8;
  const tariff = selectedConnector.tariff_per_kwh || 3000.0;
  const soc = selectedVehicle.current_soc || 28.0;

  let targetSoc = 100.0;
  let targetType = "FULL";
  let manualKwh = 20.0;

  if (targetMode === "FULL_80") {
    targetSoc = soc >= 80.0 ? 100.0 : 80.0;
    targetType = "FULL";
  } else if (targetMode === "FULL_100") {
    targetSoc = 100.0;
    targetType = "FULL";
  } else {
    targetType = "MANUAL_KWH";
    const inputElem = document.getElementById("inputManualKwh");
    const rawVal = inputElem?.value?.trim();
    if (!rawVal || isNaN(parseFloat(rawVal)) || parseFloat(rawVal) <= 0) {
      resetEstimateDisplay();
      return;
    }
    manualKwh = parseFloat(rawVal);
  }

  try {
    const res = await fetch("/api/station/estimate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        vehicle_id: selectedVehicle.id,
        connector_id: selectedConnector.id,
        target_type: targetType,
        manual_kwh: manualKwh,
        custom_target_soc: targetSoc
      })
    });

    currentEstimate = await res.json();

    const neededKwh = currentEstimate.energy_needed_kwh.toFixed(1);
    const addedKm = Math.round(currentEstimate.energy_needed_kwh * efficiency);
    const petrolLiters = (addedKm / 12.0);
    const petrolCost = Math.round(petrolLiters * 13700);
    const savings = Math.max(0, petrolCost - currentEstimate.estimated_cost);

    document.getElementById("estEnergy").innerText = `${neededKwh} kWh`;
    const estKmElem = document.getElementById("estKm");
    if (estKmElem) estKmElem.innerText = `+${addedKm} KM Jangkauan`;
    document.getElementById("estTariff").innerText = `Rp ${currentEstimate.tariff_per_kwh.toLocaleString('id-ID')} / kWh`;
    const estSavElem = document.getElementById("estSavings");
    if (estSavElem) estSavElem.innerText = `Hemat Rp ${savings.toLocaleString('id-ID')} vs Pertamax (Hemat 60%)`;
    document.getElementById("estDuration").innerText = `${currentEstimate.estimated_duration_minutes} Menit`;
    document.getElementById("estTotalDeposit").innerText = `Rp ${currentEstimate.estimated_cost.toLocaleString('id-ID')}`;
    document.getElementById("qrisAmountText").innerText = `Rp ${currentEstimate.estimated_cost.toLocaleString('id-ID')}`;
  } catch (err) {
    console.error("Gagal kalkulasi estimasi:", err);
  }
}

// Payment Method Selection
function setPaymentMethod(method) {
  paymentMethod = method;
  document.getElementById("payTabWallet").className = `tab-btn ${method === 'WALLET' ? 'active' : ''}`;
  document.getElementById("payTabQris").className = `tab-btn ${method === 'QRIS' ? 'active' : ''}`;
  document.getElementById("payTabEmoney").className = `tab-btn ${method === 'EMONEY' ? 'active' : ''}`;

  document.getElementById("payContentWallet").style.display = method === 'WALLET' ? 'block' : 'none';
  document.getElementById("payContentQris").style.display = method === 'QRIS' ? 'block' : 'none';
  document.getElementById("payContentEmoney").style.display = method === 'EMONEY' ? 'block' : 'none';

  const btnStart = document.getElementById("btnStartCharging");
  if (btnStart) {
    if (method === "EMONEY") {
      btnStart.innerHTML = "💳 TAP KARTU & CAS SEKARANG";
    } else {
      btnStart.innerHTML = "⚡ MULAI CAS SEKARANG";
    }
  }

  if (method === 'QRIS' && currentEstimate) {
    renderQrisCode(currentEstimate.estimated_cost);
  }
}

function renderQrisCode(amount) {
  const container = document.getElementById("driverQrisCode");
  container.innerHTML = "";
  if (typeof QRCode !== "undefined") {
    new QRCode(container, {
      text: `00020101021226600016ID.CO.VOLTX.WWW0118936009110000000001520458125303360540${amount}5802ID5914VOLTX CHARGING6007JAKARTA`,
      width: 140,
      height: 140,
      colorDark: "#0B0F19",
      colorLight: "#FFFFFF",
      correctLevel: QRCode.CorrectLevel.M
    });
  } else {
    container.innerHTML = `<div style="padding:16px; color:#080C14; font-weight:800; font-size:1rem;">QRIS SIMULASI<br>Rp ${amount.toLocaleString('id-ID')}</div>`;
  }
}

// -------------------------------------------------------------
// E-MONEY RFID MODAL & TAP SIMULATION (DRIVER DEMO)
// -------------------------------------------------------------
let emoneyTapTimeout = null;

async function openEmoneyTapModal() {
  if (!currentEstimate || currentEstimate.estimated_cost <= 0) {
    await updateEstimate();
  }
  if (!currentEstimate || currentEstimate.estimated_cost <= 0) {
    currentEstimate = {
      estimated_cost: 25000,
      energy_needed_kwh: 10.0,
      tariff_per_kwh: (selectedConnector && selectedConnector.tariff_per_kwh) || 2466
    };
  }

  if (emoneyTapTimeout) {
    clearTimeout(emoneyTapTimeout);
    emoneyTapTimeout = null;
  }

  // Reset to initial tap prompt
  const promptSec = document.getElementById("emoneyTapPromptSection");
  const detectedSec = document.getElementById("emoneyCardDetectedSection");
  if (promptSec) promptSec.style.display = "block";
  if (detectedSec) detectedSec.style.display = "none";

  const modal = document.getElementById("emoneyTapModal");
  if (modal) modal.classList.add("open");
}

function closeEmoneyTapModal() {
  if (emoneyTapTimeout) {
    clearTimeout(emoneyTapTimeout);
    emoneyTapTimeout = null;
  }
  const modal = document.getElementById("emoneyTapModal");
  if (modal) modal.classList.remove("open");
}

async function triggerEmoneyCardTap() {
  const promptSec = document.getElementById("emoneyTapPromptSection");
  const detectedSec = document.getElementById("emoneyCardDetectedSection");
  if (promptSec) promptSec.style.display = "none";
  if (detectedSec) detectedSec.style.display = "block";

  // Reference card matching user screenshot
  const demoCardUid = "BCA-6656";
  const demoCardHolder = "BCA Flazz (Demo #6656)";
  const demoCardBalance = 149790;
  const demoCardType = "BCA FLAZZ";

  const cardUidText = document.getElementById("emoneyCardUidText");
  const cardHolder = document.getElementById("emoneyCardHolderText");
  const cardBalance = document.getElementById("emoneyCardBalanceText");
  const cardBadge = document.getElementById("emoneyCardTypeBadge");

  if (cardUidText) cardUidText.innerText = "BCA - 6656";
  if (cardHolder) cardHolder.innerText = demoCardHolder;
  if (cardBalance) cardBalance.innerText = `Rp ${demoCardBalance.toLocaleString('id-ID')}`;
  if (cardBadge) cardBadge.innerText = demoCardType;

  // After 2-second delay: show transaction success alert and proceed automatically to charging!
  emoneyTapTimeout = setTimeout(async () => {
    closeEmoneyTapModal();

    await showAppAlert(
      `Transaksi Berhasil!\n\nPembayaran E-Money telah diverifikasi dengan kartu ${demoCardType} (${demoCardUid}).\nSistem otomatis melanjutkan ke pengisian daya...`,
      {
        title: "Transaksi Berhasil",
        subtitle: `💳 ${demoCardType} - ${demoCardUid}`,
        type: "success",
        confirmText: "Lanjutkan"
      }
    );

    await executeStartCharging(demoCardUid);
  }, 2000);
}

// START CHARGING
async function startChargingProcess() {
  if (!currentEstimate || currentEstimate.estimated_cost <= 0) {
    await updateEstimate();
  }
  if (!currentEstimate || currentEstimate.estimated_cost <= 0) {
    currentEstimate = {
      estimated_cost: 25000,
      energy_needed_kwh: 10.0,
      tariff_per_kwh: (selectedConnector && selectedConnector.tariff_per_kwh) || 2466
    };
  }

  if (paymentMethod === "EMONEY") {
    await openEmoneyTapModal();
    return;
  }

  await executeStartCharging(null);
}

async function executeStartCharging(cardUid) {
  let manualKwh = 15.0;
  let targetSoc = 100.0;
  let targetType = "FULL";

  if (targetMode === "FULL_80") {
    targetType = "FULL";
    targetSoc = 80.0;
  } else if (targetMode === "FULL_100") {
    targetType = "FULL";
    targetSoc = 100.0;
  } else {
    targetType = "MANUAL_KWH";
    const input = document.getElementById("inputManualKwh");
    const raw = input ? input.value.trim() : "";
    manualKwh = parseFloat(raw) || 0;
    if (manualKwh <= 0) {
      await showAppAlert("Silakan masukkan jumlah energi kWh pengisian yang valid terlebih dahulu.", {
        title: "Input kWh Belum Valid",
        type: "warning"
      });
      return;
    }
  }

  const payload = {
    user_id: USER_ID,
    station_code: STATION_CODE,
    connector_id: selectedConnector.id,
    vehicle_id: selectedVehicle.id,
    target_type: targetType,
    manual_kwh: manualKwh,
    target_soc: targetSoc,
    payment_method: paymentMethod,
    card_uid: cardUid
  };

  try {
    const res = await fetch("/api/station/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const result = await res.json();

    if (!res.ok) {
      await showAppAlert(result.detail || "Terjadi kesalahan sistem saat memulai pengisian.", {
        title: "Gagal Memulai Pengisian",
        type: "error"
      });
      return;
    }

    activeSessionId = result.session_id;

    // Switch to active charging screen
    document.getElementById("step1View").style.display = "none";
    document.getElementById("step2View").style.display = "none";
    document.getElementById("step3View").style.display = "none";
    document.getElementById("wizardStepHeader").style.display = "none";
    document.getElementById("activeChargingView").style.display = "block";

    const carLabel = document.getElementById("activeChargingCarLabel");
    if (carLabel && selectedVehicle) {
      carLabel.innerText = `${selectedVehicle.brand} ${selectedVehicle.model} (${selectedVehicle.license_plate})`;
    }

    document.getElementById("driverLiveDeposit").innerText = `Rp ${result.deposit_paid.toLocaleString('id-ID')}`;

    await loadUserData();
  } catch (err) {
    await showAppAlert("Terjadi kesalahan saat memulai pengisian: " + err, {
      title: "Kesalahan Sistem",
      type: "error"
    });
  }
}

// STOP CHARGING & REFUND
async function stopChargingProcess() {
  if (!activeSessionId) return;

  const ok = await showAppConfirm("Hentikan pengisian sekarang?\nSisa saldo deposit yang tidak terpakai akan otomatis dikembalikan ke akun Anda.", {
    title: "Konfirmasi Stop Pengisian",
    type: "warning",
    confirmText: "Ya, Hentikan",
    cancelText: "Batal"
  });
  if (!ok) return;

  try {
    const res = await fetch("/api/station/stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: activeSessionId,
        user_id: USER_ID
      })
    });

    const data = await res.json();
    activeSessionId = null;

    // Show Receipt Modal with Real EV Layman Metrics
    document.getElementById("receiptSessionCode").innerText = `#CS-${Date.now().toString().slice(-6)}`;
    const carElem = document.getElementById("receiptCar");
    if (carElem) carElem.innerText = `${data.car_model || (selectedVehicle ? (selectedVehicle.brand + ' ' + selectedVehicle.model) : 'Real EV')}`;
    const receiptElem = document.getElementById("receiptKwh") || document.getElementById("receiptMah");
    if (receiptElem) receiptElem.innerText = `${(data.total_energy_kwh || 0).toFixed(2)} kWh`;
    const rcptKm = document.getElementById("receiptKm");
    if (rcptKm) rcptKm.innerText = `+${data.km_added || 0} KM`;
    const rcptSav = document.getElementById("receiptSavings");
    if (rcptSav) rcptSav.innerText = `Hemat Rp ${(data.money_saved_petrol || 0).toLocaleString('id-ID')} (${data.savings_percentage || 60}%)`;
    document.getElementById("receiptActualCost").innerText = `Rp ${Math.round(data.actual_cost || 0).toLocaleString('id-ID')}`;
    document.getElementById("receiptDepositPaid").innerText = document.getElementById("driverLiveDeposit").innerText;
    document.getElementById("receiptRefundAmount").innerText = `Rp ${Math.round(data.refund_amount || 0).toLocaleString('id-ID')}`;

    document.getElementById("receiptModal").classList.add("open");

    // Reset view
    document.getElementById("wizardStepHeader").style.display = "flex";
    goToStep(1);

    await loadUserData();
    await loadStationData();
  } catch (err) {
    await showAppAlert("Gagal menghentikan pengisian: " + err, {
      title: "Gagal Stop",
      type: "error"
    });
  }
}

function closeReceiptModal() {
  document.getElementById("receiptModal").classList.remove("open");
}

// TOP UP SALDO
function openTopUpModal() {
  document.getElementById("topUpModal").classList.add("open");
}

function closeTopUpModal() {
  document.getElementById("topUpModal").classList.remove("open");
}

async function executeTopUp(amount) {
  try {
    const res = await fetch(`/api/auth/topup/${USER_ID}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount: amount, method: "QRIS" })
    });
    const data = await res.json();
    await showAppAlert(data.message, {
      title: "Top-Up Berhasil",
      type: "success"
    });
    closeTopUpModal();
    await loadUserData();
  } catch (err) {
    await showAppAlert("Gagal topup: " + err, {
      title: "Top-Up Gagal",
      type: "error"
    });
  }
}

// WebSocket Setup
function setupWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/station/${STATION_CODE}`;

  ws = new WebSocket(wsUrl);

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.event === "HANDSHAKE_STAGE") {
      // Isolasi multi-user: Jika event handshake milik user lain, abaikan
      if (data.user_id && data.user_id !== USER_ID) {
        return;
      }
      const hsModal = document.getElementById("handshakeModal");
      if (!hsModal || !hsModal.classList.contains("open")) {
        return;
      }

      const step = data.step || (typeof data.stage === "number" ? data.stage : 1);
      for (let i = 1; i <= 4; i++) {
        const stepEl = document.getElementById(`hsStep${i}`);
        if (!stepEl) continue;
        if (i < step) {
          stepEl.className = "handshake-step-item done";
        } else if (i === step) {
          stepEl.className = "handshake-step-item active";
        } else {
          stepEl.className = "handshake-step-item";
        }
      }
      const footerMsg = document.getElementById("handshakeFooterMsg");
      if (footerMsg && data.message) {
        footerMsg.innerText = `⏳ ${data.message}`;
      }
      if (data.vehicle) {
        selectedVehicle = data.vehicle;
        const desc3 = document.getElementById("hsDesc3");
        if (desc3) {
          desc3.innerHTML = `Terverifikasi: <b style="color:#00F0FF;">${data.vehicle.brand} ${data.vehicle.model}</b> (${data.vehicle.license_plate})`;
        }
        updateCarDisplay();
      }
    } else if (data.event === "HANDSHAKE_COMPLETE") {
      // Isolasi multi-user: Jika event milik user lain, perbarui data stasiun dan abaikan
      if (data.user_id && data.user_id !== USER_ID) {
        loadStationData();
        return;
      }
      const hsModal = document.getElementById("handshakeModal");
      if (!hsModal || !hsModal.classList.contains("open")) {
        loadStationData();
        return;
      }

      for (let i = 1; i <= 4; i++) {
        const stepEl = document.getElementById(`hsStep${i}`);
        if (stepEl) stepEl.className = "handshake-step-item done";
      }
      const footerMsg = document.getElementById("handshakeFooterMsg");
      if (footerMsg) {
        footerMsg.innerHTML = "✅ <b>Verifikasi Berhasil!</b> Parameter keselamatan kendaraan terverifikasi aman (ISO 15118).";
      }
      if (data.vehicle) {
        selectedVehicle = data.vehicle;
        updateCarDisplay();
      }
      setTimeout(async () => {
        closeHandshakeModal();
        const matched = stationConnectors.find(c => c.id === data.connector_id) || selectedConnector;
        if (matched) {
          selectedConnector = matched;
          const claimed = await claimNozzle(matched.id, true);
          if (claimed) {
            goToStep(2);
            showAppAlert(`Konektor ${matched.name} berhasil terhubung!\nKendaraan: ${selectedVehicle ? (selectedVehicle.brand + ' ' + selectedVehicle.model) : 'EV'}\nMelanjutkan ke Target Cas...`, {
              title: "Verifikasi Berhasil!",
              subtitle: `🚗 ${selectedVehicle ? selectedVehicle.model : 'Real EV'} • 🔌 ${matched.name}`,
              type: "success"
            });
          }
        }
        loadStationData();
      }, 700);
    } else if (data.event === "PORT_NOZZLE_CONNECTED") {
      // Isolasi multi-user: Jika event milik user lain, hanya perbarui status stasiun
      if (data.user_id && data.user_id !== USER_ID) {
        loadStationData();
        return;
      }

      isPlugged = true;
      const hsModal = document.getElementById("handshakeModal");
      if (hsModal && hsModal.classList.contains("open")) {
        closeHandshakeModal();
        const matched = stationConnectors.find(c => c.id === data.connector_id) || selectedConnector;
        if (matched) {
          selectedConnector = matched;
          claimNozzle(matched.id, true).then(claimed => {
            if (claimed) {
              goToStep(2);
            }
          });
        }
      }
      if (!activeSessionId) {
        const target = stationConnectors.find(c => c.id === data.connector_id);

        // CASE A: User is on Step 1 waiting for this pending nozzle!
        if (currentStep === 1 && pendingNozzleConnector) {
          if (pendingNozzleConnector.id === data.connector_id) {
            const matched = target || pendingNozzleConnector;
            cancelPendingNozzle();
            selectedConnector = matched;
            claimNozzle(matched.id, true).then(success => {
              if (success) {
                goToStep(2);
                showAppAlert(`Kabel ${matched.name} berhasil terhubung!\nMelanjutkan ke Target Cas...`, {
                  title: "Kabel Terhubung!",
                  subtitle: `🔌 ${matched.name}`,
                  type: "success"
                });
              }
            });
            loadStationData();
            return;
          } else {
            loadStationData();
            return;
          }
        }

        if (target && selectedConnector && selectedConnector.id === target.id) {
          selectedConnector = target;
        }
        const badge = document.getElementById("usbDetectBadge");
        if (badge) {
          badge.className = "status-pill busy";
          badge.innerHTML = `⚡ Terdeteksi di ${data.port_key || 'Port USB'} ➜ ${data.connector_name} Tercolok!`;
        }
      }
      loadStationData();
    } else if (data.event === "PORT_NOZZLE_RECONFIGURED") {
      updateDevPortButtons(data.connector_id);
      loadStationData();
    } else if (data.event === "ADB_BATTERY_UPDATE") {
      handleAdbBatteryUpdate(data);
    } else if (data.event === "ADB_BATTERY_DISCONNECTED") {
      handleAdbBatteryDisconnected();
    } else if (data.event === "ADB_BATTERY_UNAUTHORIZED") {
      adbBatteryState = { connected: true, unauthorized: true };
      const badge = document.getElementById("usbDetectBadge");
      if (badge) {
        badge.className = "status-pill warning";
        badge.innerHTML = "⚠️ HP tercolok tapi belum diizinkan. Cek notifikasi 'Izinkan Debugging USB' di layar HP!";
      }
      const desktopAdbBadge = document.getElementById("desktopAdbStatus");
      if (desktopAdbBadge) {
        desktopAdbBadge.className = "status-pill warning";
        desktopAdbBadge.innerText = "⚠️ HP Tercolok (Perlu Izin USB)";
      }
    } else if (data.event === "NOZZLE_PLUGGED") {
      loadStationData();
    } else if (data.event === "NOZZLE_UNPLUGGED") {
      loadStationData();
      if (!isSimulatedMode && selectedConnector && selectedConnector.id === data.connector_id) {
        handleAdbBatteryDisconnected();
      }
    } else if (data.event === "TELEMETRY_UPDATE" && activeSessionId === data.session_id) {
      document.getElementById("driverLiveSoc").innerText = `${data.current_soc.toFixed(1)}%`;
      const kw = data.current_power_kw ? data.current_power_kw.toFixed(1) : (data.current_power_w ? (data.current_power_w / 1000).toFixed(1) : "0.0");
      const wattElem = document.getElementById("driverLiveWatt") || document.getElementById("driverLiveKw");
      if (wattElem) wattElem.innerText = `${kw} kW`;

      const detailKw = document.getElementById("driverLiveKwDetail");
      if (detailKw) detailKw.innerText = `${kw} kW`;

      const volt = data.voltage_v ? Math.round(data.voltage_v) : (data.voltage || 400);
      const amps = data.current_a ? data.current_a.toFixed(1) : (data.current_amps ? data.current_amps.toFixed(1) : "0.0");
      const voltAmp = document.getElementById("driverLiveVoltAmp");
      if (voltAmp) voltAmp.innerText = `${volt} V / ${amps} A`;

      const kwh = data.energy_delivered_kwh !== undefined ? data.energy_delivered_kwh.toFixed(2) : "0.00";
      const mahElem = document.getElementById("driverLiveMah") || document.getElementById("driverLiveKwh");
      if (mahElem) mahElem.innerText = `${kwh} kWh`;

      document.getElementById("driverLiveCost").innerText = `Rp ${Math.round(data.current_cost || 0).toLocaleString('id-ID')}`;
      document.getElementById("driverLiveRemaining").innerText = `Rp ${Math.round(data.remaining_deposit || 0).toLocaleString('id-ID')}`;

      // Layman telemetry cards
      const kmElem = document.getElementById("driverLiveKm");
      if (kmElem) kmElem.innerText = `+${data.km_added || 0} KM`;

      const speedElem = document.getElementById("driverLiveSpeed");
      if (speedElem) speedElem.innerText = `+${(data.charging_speed_km_per_min || 0).toFixed(1)} km/m`;

      const savingsElem = document.getElementById("driverLiveSavings");
      if (savingsElem) savingsElem.innerText = `Rp ${Math.round(data.money_saved_petrol || 0).toLocaleString('id-ID')}`;

      const savingsSub = document.getElementById("driverLiveSavingsSub");
      if (savingsSub) savingsSub.innerText = `Hemat ${data.savings_percentage || 60}% vs Pertamax`;

      const etaElem = document.getElementById("driverLiveEta");
      if (etaElem) etaElem.innerText = `${data.eta_minutes || 0} Mnt`;

      // Battery tapering warning banner (SoC >= 80%)
      const taperBanner = document.getElementById("driverTaperingBanner");
      if (taperBanner) {
        taperBanner.style.display = data.is_tapering ? "block" : "none";
      }
    } else if (data.event === "SESSION_COMPLETED") {
      loadStationData();
      if (activeSessionId === data.session_id) {
        activeSessionId = null;
        isSimulatedMode = false;
        isPlugged = false;
        document.getElementById("receiptSessionCode").innerText = `#${data.session_code}`;
        const carElem = document.getElementById("receiptCar");
        if (carElem) carElem.innerText = `${data.car_model || (selectedVehicle ? (selectedVehicle.brand + ' ' + selectedVehicle.model) : 'Real EV')}`;
        const receiptElem = document.getElementById("receiptKwh") || document.getElementById("receiptMah");
        if (receiptElem) receiptElem.innerText = `${(data.total_energy_kwh || 0).toFixed(2)} kWh`;
        const rcptKm = document.getElementById("receiptKm");
        if (rcptKm) rcptKm.innerText = `+${data.km_added || 0} KM`;
        const rcptSav = document.getElementById("receiptSavings");
        if (rcptSav) rcptSav.innerText = `Hemat Rp ${(data.money_saved_petrol || 0).toLocaleString('id-ID')} (${data.savings_percentage || 60}%)`;
        document.getElementById("receiptActualCost").innerText = `Rp ${Math.round(data.actual_cost || 0).toLocaleString('id-ID')}`;
        document.getElementById("receiptDepositPaid").innerText = `Rp ${Math.round(data.deposit_paid || 0).toLocaleString('id-ID')}`;
        document.getElementById("receiptRefundAmount").innerText = `Rp ${Math.round(data.refund_amount || 0).toLocaleString('id-ID')}`;
        document.getElementById("receiptModal").classList.add("open");

        document.getElementById("activeChargingView").style.display = "none";
        document.getElementById("wizardStepHeader").style.display = "flex";
        goToStep(1);
        loadUserData();
      }
    } else if (data.event === "SESSION_STARTED") {
      loadStationData();
      if (selectedConnector && selectedConnector.id === data.connector_id && currentStep === 1 && activeSessionId !== data.session_id) {
        selectedConnector = null;
      }
    } else if (data.event === "NOZZLE_CLAIMED" || data.event === "NOZZLE_RELEASED") {
      loadStationData();
      if (data.event === "NOZZLE_CLAIMED" && data.locked_by_user_id !== USER_ID) {
        if (selectedConnector && selectedConnector.id === data.connector_id && currentStep === 1) {
          selectedConnector = stationConnectors.find(c => c.status === "AVAILABLE" && !c.locked_by_user_id) || null;
        }
      }
    } else if (data.event === "STATION_RESET") {
      activeSessionId = null;
      document.getElementById("activeChargingView").style.display = "none";
      document.getElementById("wizardStepHeader").style.display = "flex";
      goToStep(1);
      if (currentUser) loadUserData();
      loadStationData();
    }
  };

  ws.onclose = () => {
    setTimeout(setupWebSocket, 2000);
  };
}

// -------------------------------------------------------------
// OPERATIONAL CONTROLS & RESET
// -------------------------------------------------------------
async function emergencyResetStation() {
  const ok = await showAppConfirm("Reset semua sesi pengisian dan kembalikan stasiun ke kondisi awal?\nSeluruh deposit yang belum dipakai akan dikembalikan ke dompet driver.", {
    title: "Reset Operasional",
    type: "warning",
    confirmText: "Ya, Reset Stasiun",
    cancelText: "Batal"
  });
  if (!ok) return;

  try {
    const res = await fetch("/api/station/emergency-reset", { method: "POST" });
    const data = await res.json();
    activeSessionId = null;
    document.getElementById("activeChargingView").style.display = "none";
    document.getElementById("wizardStepHeader").style.display = "flex";
    goToStep(1);
    if (currentUser) {
      await loadUserData();
    }
    await loadStationData();
    await showAppAlert(data.message, {
      title: "Reset Stasiun Berhasil",
      type: "success"
    });
  } catch (err) {
    await showAppAlert("Gagal reset stasiun: " + err, {
      title: "Reset Gagal",
      type: "error"
    });
  }
}

async function switchDemoUser(username, password) {
  if (activeSessionId) {
    const ok = await showAppConfirm("Sesi aktif sedang berjalan. Yakin ingin berganti akun?\nSesi pengisian akan tetap berjalan di stasiun.", {
      title: "Konfirmasi Ganti Akun",
      type: "warning",
      confirmText: "Ya, Ganti Akun",
      cancelText: "Batal"
    });
    if (!ok) return;
  }
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username, password: password })
    });
    const data = await res.json();
    if (!res.ok) {
      await showAppAlert(data.detail || "Error login", {
        title: "Gagal Masuk",
        type: "error"
      });
      return;
    }
    localStorage.setItem("voltx_user", JSON.stringify(data));
    activeSessionId = null;
    document.getElementById("activeChargingView").style.display = "none";
    document.getElementById("wizardStepHeader").style.display = "flex";
    await initDriverApp();
  } catch (err) {
    await showAppAlert("Gagal switch akun: " + err, {
      title: "Error Switch Akun",
      type: "error"
    });
  }
}

function setDisplayMode(mode) {
  const pres = document.getElementById("presContainer");
  const btnMockup = document.getElementById("btnModeMockup");
  const btnFluid = document.getElementById("btnModeFluid");
  if (!pres) return;

  if (mode === "fluid") {
    pres.classList.add("fluid-mode");
    if (btnMockup) btnMockup.classList.remove("active");
    if (btnFluid) btnFluid.classList.add("active");
  } else {
    pres.classList.remove("fluid-mode");
    if (btnMockup) btnMockup.classList.add("active");
    if (btnFluid) btnFluid.classList.remove("active");
  }
}

function updatePhoneClock() {
  const clockElem = document.getElementById("phoneClock");
  if (clockElem) {
    const now = new Date();
    const h = String(now.getHours()).padStart(2, "0");
    const m = String(now.getMinutes()).padStart(2, "0");
    clockElem.innerText = `${h}:${m}`;
  }
}
setInterval(updatePhoneClock, 1000);
updatePhoneClock();
// -------------------------------------------------------------
// DEV TESTING: DYNAMIC USB PORT REMAPPER
// -------------------------------------------------------------
async function loadDevPortStatus() {
  try {
    const res = await fetch("/api/station/ports/config");
    if (res.ok) {
      const data = await res.json();
      const curCid = data.current_device?.connector_id || data.mappings?.["Port_#0002"]?.connector_id || 1;
      updateDevPortButtons(curCid);
    }
  } catch (e) {
    console.warn("Dev port config load error:", e);
  }
}

async function devSwitchUsbPort(connectorId) {
  try {
    const res = await fetch("/api/station/dev/remap-active-port", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ connector_id: connectorId })
    });
    const data = await res.json();
    if (!res.ok) {
      await showAppAlert(data.detail || "Gagal memetakan port USB", { title: "Error Port Mapping", type: "error" });
      return;
    }
    updateDevPortButtons(connectorId);
    await loadStationData();
    await showAppAlert(`Port hardware USB laptop berhasil dipetakan ke Nozzle ${connectorId}!\nSistem kini mengenali kabel fisik Anda sebagai Nozzle ${connectorId}.`, {
      title: "Port Berhasil Dipetakan",
      type: "success"
    });
  } catch (err) {
    await showAppAlert("Gagal koneksi ke server: " + err, { title: "Error", type: "error" });
  }
}

function updateDevPortButtons(activeId) {
  [1, 2, 3].forEach(id => {
    const btn = document.getElementById(`btnDevPort${id}`);
    if (btn) {
      if (id === activeId) {
        btn.classList.add("active");
        btn.style.borderColor = "var(--cyan-neon)";
        btn.style.background = "rgba(0, 240, 255, 0.25)";
        btn.style.color = "#00F0FF";
        btn.style.fontWeight = "700";
      } else {
        btn.classList.remove("active");
        btn.style.borderColor = "#1E293B";
        btn.style.background = "transparent";
        btn.style.color = "var(--text-muted)";
        btn.style.fontWeight = "400";
      }
    }
  });
}

window.addEventListener("DOMContentLoaded", initDriverApp);

window.addEventListener("beforeunload", () => {
  if (selectedConnector && !activeSessionId && USER_ID) {
    if (selectedConnector.locked_by_user_id === USER_ID) {
      try {
        navigator.sendBeacon(
          `/api/station/connector/${selectedConnector.id}/release`,
          new Blob([JSON.stringify({ user_id: USER_ID })], { type: "application/json" })
        );
      } catch (e) {}
    }
    if (isPlugged) {
      try {
        navigator.sendBeacon(`/api/station/connector/${selectedConnector.id}/unplug`);
      } catch (e) {}
    }
  }
});

