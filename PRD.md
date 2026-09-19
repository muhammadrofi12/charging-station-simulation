# Product Requirements Document (PRD): Simulasi EV Charging Station

> **Sistem Simulasi Stasiun Pengisian Kendaraan Listrik (EVCS)**
> Menggunakan **Laptop sebagai Mesin Station (Kios/Totem SPKLU)** dan **HP/Browser sebagai Aplikasi Driver Pengemudi** untuk mengontrol pengisian **Mobil Listrik (Real EV / Fleet Simulation)**.
> Dibangun dengan ekosistem **Python (FastAPI, WebSockets, SQLite)**.

---

## 1. Referensi Alur Asli (Whiteboard)

![Whiteboard Flow](docs/whiteboard_flow.png)

### Rekap Poin Utama Sistem:
- **Pricing**: Harga resmi berbasis energi riil yang tersalurkan (**Rp / kWh**, sesuai standar regulasi SPKLU).
- **Billing System**: Sistem deposit di depan & menggunakan akun pengguna dengan auto-refund seketika.
- **Mode Charging**:
  - **AC (Normal Charge)**: Type 2 (22 kW / 7 kW).
  - **DC (Fast & Ultra-Fast Charge)**: CHAdeMO (50 kW) & CCS2 (150 kW).
- **Vehicle Awareness**: Charging station mengenali model dan kapasitas baterai mobil listrik (EV) pengguna (misal: Hyundai Ioniq 5 72.6 kWh, Wuling Binguo EV 31.9 kWh, BYD Seal 82.5 kWh).

---

## 2. Alur Kerja Pengguna (User Flow 1 s/d 10)

| Langkah | Aksi Pengguna (Driver App) | Respons Sistem & Tampilan Layar Kiosk |
| :---: | :--- | :--- |
| **1** | Buka sistem di HP (`http://[IP-LAPTOP]:8000/driver`) | Server FastAPI menyajikan antarmuka mobile web modern & responsif. |
| **2** | Masuk Home Page | Menampilkan profil user, info Mobil Listrik (EV), dan kartu Saldo Deposit. |
| **3** | Pilih menu *Mulai Cas EV* | Masuk ke alur inisiasi pengisian. |
| **4** | Pilih lokasi stasiun | Pilihan stasiun SPKLU (misal: *SPKLU Sudirman Central Hub*). |
| **5** | Scan QR Nozzle SPKLU | Kamera HP memindai QR Code dinamis nozzle di layar Kiosk. |
| **6** | Colokkan nozzle ke mobil | Klik *"⚡ Colok Simulasi"* atau sambungkan nozzle. Layar Kiosk berubah status menjadi **🔌 KABEL TERCOLOK**. |
| **7** | Sistem deteksi baterai | Sistem membaca status SoC (%) dan total kapasitas baterai mobil listrik (kWh). |
| **8** | Pilih target pengisian | Pilihan: **Charge Full (100%)**, **Target SoC Kustom (80%)**, atau **Input kWh Manual**. |
| **9** | Pilih metode pembayaran | Pembayaran deposit awal (Saldo Akun / QRIS Dinamis / Tap E-Money). Nozzle terkunci hingga deposit sukses. |
| **10**| Sistem memulai charge | Aliran daya aktif! Daya kW, tegangan Volt, arus Ampere, estimasi penambahan jarak (KM), dan penghematan biaya vs BBM bergerak sinkron. |
| **+** | **Berhenti & Auto-Refund** | Klik **"Stop Charging"** atau cabut kabel. Aliran listrik mati, nozzle kembali standby, biaya riil dihitung, dan **sisa saldo deposit otomatis di-refund seketika**! |

---

## 2.1 Detail Sistem Pembayaran (Deposit Saldo, QRIS, E-Money)

Sistem mengakomodasi 3 opsi pembayaran:

### 1. Deposit Saldo (In-App Prepaid Wallet)
- **Fungsi**: Dompet digital utama di aplikasi pengguna.
- **Top-Up**: Pengguna dapat mengisi saldo kapan saja via simulasi transfer/QRIS (pilihan Rp 50.000, Rp 100.000, Rp 200.000).
- **Alur Cas**: Saat mulai mengecas, saldo di-*HOLD* sejumlah estimasi. Saat cas selesai/berhenti di tengah jalan, sisa saldo yang tidak terpakai langsung di-*UNHOLD* seketika ke akun pengguna.

### 2. Pembayaran Langsung via QRIS Dinamis (Pay-per-Charge)
- **Fungsi**: Untuk pengguna yang ingin langsung bayar per sesi tanpa harus top-up saldo dompet terlebih dahulu.
- **Alur Cas**: Sistem memunculkan kode QRIS dengan nominal pas sesuai target kWh yang dipilih. Pengguna memindai QRIS via aplikasi bank/e-wallet. Begitu status `PAID`, charger otomatis menyala.
- **Mekanisme Refund**: Jika berhenti lebih awal, sisa dana yang belum terpakai otomatis dikembalikan ke **Saldo Akun Aplikasi** pengguna (karena transaksi QRIS perbankan tidak mendukung instan parsial refund ke rekening pengirim).

### 3. E-Money / Kartu RFID (Tap-and-Charge)
- **Fungsi**: Membuka kunci dan membayar dengan kartu fisik (Flazz, Mandiri E-Money, Brizzi, atau kartu RFID SPKLU).
- **Alur Interaksi Pembayaran**:
  1. Pengguna menentukan target/nominal pengisian di aplikasi atau kios (misal Rp 50.000).
  2. Pengguna memilih metode pembayaran: **"E-Money / Kartu Fisik"**.
  3. Sistem memunculkan prompt/dialog: *"Silakan Tap Kartu E-Money Anda pada Sensor Mesin Charger"*.
  4. Pengguna men-tap kartu pada sensor mesin (di laptop ada tombol/modal simulasi tap kartu).
  5. **Verifikasi Saldo Real-Time**:
     - **Jika Saldo Cukup**: Saldo kartu/akun berhasil dipotong/di-hold Rp 50.000, terdengar bunyi *beep* sukses, status menjadi **PAID**, dan mesin charger langsung mulai mengalirkan daya listrik.
     - **Jika Saldo Tidak Cukup**: Pembayaran **GAGAL**, muncul notifikasi merah *"Saldo E-Money Tidak Cukup (Sisa Rp 20.000, Butuh Rp 50.000)"*, mesin tetap terkunci, dan pengguna diarahkan untuk **memilih metode pembayaran lain** (seperti QRIS atau Saldo Dompet) atau menyesuaikan nominal target cas.

---

## 3. Spesifikasi Teknis Perangkat & Arsitektur

![Spesifikasi Teknis Perangkat & Arsitektur SPKLU](static/img/system_architecture.png)

---

## 4. Logika Perhitungan & Rumus Matematika

### A. Estimasi Pengisian
$$\text{Energi Dibutuhkan (kWh)} = \text{Kapasitas Baterai (kWh)} \times \frac{\text{Target SoC} - \text{Current SoC}}{100}$$
$$\text{Estimasi Biaya (Rp)} = \text{Energi Dibutuhkan (kWh)} \times \text{Tarif per kWh}$$
$$\text{Estimasi Durasi (Menit)} = \frac{\text{Energi Dibutuhkan (kWh)}}{\text{Daya Charger (kW)} \times 0.90} \times 60$$

### B. Rumus Penghentian di Tengah Jalan & Auto-Refund
$$\text{Biaya Terpakai (Rp)} = \text{Total kWh Riil Masuk} \times \text{Tarif per kWh}$$
$$\text{Nominal Refund (Rp)} = \text{Saldo Deposit Awal} - \text{Biaya Terpakai}$$

---

## 5. Struktur Direktori Proyek

```
charging-station/
├── PRD.md                       # Dokumen spesifikasi kebutuhan produk ini
├── docs/
│   └── whiteboard_flow.png      # Foto diagram alur papan tulis
├── app/
│   ├── __init__.py
│   ├── main.py                  # Server FastAPI & WebSocket
│   ├── database.py              # SQLite Database
│   ├── models.py                # Database Models (User, Station, Session, Wallet)
│   ├── schemas.py               # Pydantic Models
│   ├── services/
│   │   ├── charging_engine.py   # Simulasi aliran daya Watt (W) & kenaikan baterai (mAh)
│   │   ├── billing_service.py   # Logika deposit, kalkulasi riil, dan refund
│   │   └── station_manager.py   # Status mesin stasiun
│   └── routers/
│       ├── api_auth.py          # Autentikasi & Saldo Dompet
│       ├── api_station.py       # Data stasiun & status konektor
│       └── ws_charging.py       # Live telemetry sync via WebSocket
├── static/
│   ├── css/
│   │   └── style.css            # Desain UI EV Neon Dark Theme
│   └── js/
│       ├── kiosk.js             # Logic layar Laptop
│       └── driver.js            # Logic web app HP
├── templates/
│   ├── kiosk.html               # UI Layar Laptop (Totem SPKLU)
│   └── driver.html              # UI Layar HP (Mobile Driver)
├── requirements.txt             # Dependensi Python
└── run.py                       # Launcher server dengan cetak IP & QR link HP
```
