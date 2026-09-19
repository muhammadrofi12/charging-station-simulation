# ⚡ Panduan Pengguna (User Guide): Simulasi EV Charging Station (VOLTX SPKLU)

Selamat datang di **VOLTX EV Charging Station Simulator**. Sistem ini mensimulasikan operasional Stasiun Pengisian Kendaraan Listrik Umum (SPKLU) modern secara *end-to-end*, menghubungkan **Monitor Totem Mesin Kiosk SPKLU** dan **Aplikasi Mobile Driver** dengan telemetri telekomunikasi berstandar industri (**ISO 15118 & IEC 61851**).

Sistem kini telah ditingkatkan dengan **Simulasi Mobil Listrik Nyata (Real EV)**, **Inisialisasi & Verifikasi Otomatis (Smart Auto-Detection)**, dan **Penerjemahan Data Listrik ke Bahasa Awam (*Layman-friendly Telemetry*)** yang mudah dipahami oleh stakeholder dan pengguna non-teknis.

---

## 📌 1. Gambaran Perangkat & Arsitektur Sistem

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           ARSITEKTUR SIMULASI SPKLU                              │
├─────────────────────────────────────────┬────────────────────────────────────────┤
│     🖥️ TOTEM KIOSK DISPLAY (PUBLIK)     │     📱 APLIKASI MOBILE DRIVER (EV)      │
│  - Monitoring 3 Nozzle (AC, DC, CCS2)   │  - Auto-Detect Armada Mobil Listrik    │
│  - Live Telemetri Daya (kW, V, A)       │  - Inisialisasi & Verifikasi ISO 15118 │
│  - QR Code Nozzle & Station             │  - Pemilihan Target Cas (80% / 100%)   │
│  - Simulasi Sambung Nozzle 1-Klik       │  - Metrik Awam (+KM, Hemat vs Bensin) │
│  - Tombol Emergency Stop                │  - Pembayaran Wallet, QRIS, & E-Money  │
└─────────────────────────────────────────┴────────────────────────────────────────┘
                                      ▲
                                      │ WebSocket Telemetry (1 Hz) & REST API
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         ⚡ BACKEND VOLTX CORE ENGINE                             │
│  - FastAPI + Python Asynchronous Core   - SQLite Database & Auto-Migration      │
│  - ISO 15118 Handshake Protocol State   - Smart EV Fleet Pool Auto-Detect       │
│  - CC-CV Tapering Curve Simulation      - Layman Fuel Savings Calculator        │
│  - Dual Mode: Cloud VPS (Demo Instan) & Hardware USB Mode (ADB Real-time)       │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Representasi Satuan Industri Nyata
Berbeda dengan pengujian awal berbasis mAh/Watt, sistem kini telah mengadopsi standar industri komersial SPKLU:
- **KiloWatt (kW):** Satuan daya pengisian listrik aktif (Nozzle 1 AC 22 kW, Nozzle 2 DC 50 kW, Nozzle 3 CCS2 Ultra-Fast 150 kW).
- **KiloWatt-hour (kWh):** Satuan kapasitas baterai dan energi listrik riil yang disalurkan ke kendaraan (berkisar 30 kWh s/d 85 kWh).
- **Tarif Resmi Riil per kWh:** Disesuaikan dengan regulasi tarif SPKLU di Indonesia:
  - **Nozzle 1 (AC Normal 22 kW):** Rp 2.466 / kWh
  - **Nozzle 2 (DC Fast 50 kW):** Rp 3.000 / kWh
  - **Nozzle 3 (DC Ultra-Fast 150 kW):** Rp 3.500 / kWh

### 1.2 Armada Mobil Listrik (Real EV Fleet Pool)
Sistem memiliki database armada kendaraan listrik populer di Indonesia yang otomatis diidentifikasi saat nozzle tersambung (*Plug & Charge*):

| Model Kendaraan Listrik | Kapasitas Baterai | Arsitektur Tegangan | Max Daya DC | Efisiensi Konsumsi |
| :--- | :---: | :---: | :---: | :---: |
| **Hyundai Ioniq 5 Long Range** | 72.6 kWh | 800 V | 220 kW | 6.8 km/kWh |
| **Wuling Binguo EV Max** | 37.9 kWh | 400 V | 50 kW | 7.8 km/kWh |
| **BYD Seal Performance** | 82.5 kWh | 800 V | 150 kW | 6.4 km/kWh |
| **Tesla Model 3 Long Range** | 78.1 kWh | 400 V | 170 kW | 7.2 km/kWh |
| **Chery Omoda E5** | 61.1 kWh | 400 V | 80 kW | 6.6 km/kWh |

---

## 🚀 2. Cara Menjalankan & Mengakses Aplikasi

### Opsi A: Akses Live Server (Siap Demo Kapan Saja)
Aplikasi telah di-deploy dan aktif 24 jam di cloud server dengan enkripsi SSL HTTPS resmi:
- **Layar Kiosk Totem SPKLU:** [https://staging.forumapi.my.id/kiosk](https://staging.forumapi.my.id/kiosk)
- **Aplikasi Mobile Driver:** [https://staging.forumapi.my.id/driver](https://staging.forumapi.my.id/driver)

### Opsi B: Menjalankan di Server Lokal (Localhost)
1. **Pastikan Prasyarat Terpenuhi:** Python 3.10+ sudah terinstal.
2. **Jalankan Aplikasi:**
   ```bash
   python run.py
   ```
3. **Buka di Browser:**
   - **Layar Kiosk:** `http://localhost:8000/kiosk`
   - **Aplikasi Driver:** `http://localhost:8000/driver`

---

## 🖥️ 3. Antarmuka Layar Kiosk Laptop (Totem SPKLU Standby)

Layar Kiosk bertindak sebagai monitor display publik pada totem mesin pengisian:

### Komponen Utama Layar Kiosk:
1. **Portal QR Driver (Sisi Kiri):** Pengemudi dapat memindai QR Code stasiun langsung menggunakan kamera smartphone untuk membuka aplikasi web driver.
2. **Status 3 Nozzle Pengisian (Sisi Kanan):**
   - **Nozzle 1 — AC Normal (Type 2):** Max 22 kW | Tarif Rp 2.466 / kWh.
   - **Nozzle 2 — DC Fast (CHAdeMO):** Max 50 kW | Tarif Rp 3.000 / kWh.
   - **Nozzle 3 — DC Ultra-Fast (CCS2):** Max 150 kW | Tarif Rp 3.500 / kWh.
3. **QR Code per Nozzle:** Memungkinkan pengemudi memindai nozzle tertentu (`/driver?nozzle=X`) untuk langsung mengklaim port tujuan.
4. **Tombol Cepat "🔌 Simulasi Sambungkan Nozzle":** Memungkinkan presenter melakukan pengujian langsung dari layar Kiosk tanpa perlu membuka kamera HP.
5. **Indikator Status Nozzle:**
   - 🟢 **STANDBY:** Nozzle tersedia dan siap digunakan.
   - 🔒 **DIKLAIM DRIVER:** Driver sedang melakukan konfigurasi target cas / pembayaran.
   - ⚡ **CHARGING:** Arus listrik aktif mengalir ke kendaraan.

---

## 📱 4. Alur Lengkap Aplikasi Driver (Step-by-Step Flow)

---

### Langkah 1: Masuk Akun, Sambungkan Nozzle & Verifikasi Kendaraan

#### 1.1 Masuk Akun Pengemudi
Driver dapat login menggunakan akun terdaftar atau menggunakan tombol cepat **1-Klik Akun Demo**:
- 👤 **Budi Santoso (`driver1` / `password123`)** — Saldo Dompet: Rp 150.000
- 👤 **Siti Rahma (`driver2` / `password123`)** — Saldo Dompet: Rp 200.000

#### 1.2 Pemilihan Nozzle (Kamera Scan QR / 1-Klik Simulasi)
Pengemudi memiliki 2 cara mudah untuk memilih nozzle pengisian:
1. **Scan QR Kamera:** Klik tombol **"📷 Scan QR Nozzle SPKLU"** dan arahkan kamera HP ke QR Code nozzle pada layar Kiosk.
2. **Tombol 1-Klik Cepat (Mode Presentasi):** Pilih salah satu nozzle demo yang tersedia (*Nozzle 1 AC 22kW, Nozzle 2 DC 50kW, atau Nozzle 3 CCS2 150kW*).

#### 1.3 Inisialisasi & Verifikasi Kendaraan (Standar ISO 15118)
Saat nozzle terhubung, sistem menampilkan jendela modal **Inisialisasi & Verifikasi Kendaraan** dengan animasi berurutan:

```
┌──────────────────────────────────────────────────────────────┐
│             🛡️ INISIALISASI & VERIFIKASI KENDARAAN           │
│         Standar Komunikasi EV ISO 15118 & IEC 61851          │
├──────────────────────────────────────────────────────────────┤
│  [🔒]  1. Penguncian Konektor (Safety Interlock)             │
│        Mengunci konektor nozzle secara mekanikal ke port...  │
│                                                              │
│  [📡]  2. Sinkronisasi Data BMS (Battery Management)         │
│        Membaca voltase, suhu, dan kesehatan baterai...       │
│                                                              │
│  [🚗]  3. Verifikasi Identitas & Tipe Kendaraan              │
│        Terverifikasi: Hyundai Ioniq 5 (B 1888 ION)           │
│                                                              │
│  [⚡]  4. Uji Isolasi & Keamanan Listrik                     │
│        Pemeriksaan tegangan tinggi (800V) & kesiapan relay.. │
├──────────────────────────────────────────────────────────────┤
│  ⏳ Menginisialisasi sistem komunikasi keselamatan...        │
│  [⚡ Lewati / Langsung ke Target Cas ➜]                       │
└──────────────────────────────────────────────────────────────┘
```

- Sistem otomatis mengacak dan memverifikasi kendaraan dari pool armada (*Auto-Detect*).
- Setelah verifikasi selesai (~4.5 detik atau dapat dilewati via tombol *Lewati*), nozzle otomatis terkunci dan aplikasi melanjutkan ke **Langkah 2**.

---

### Langkah 2: Memilih Target Cas & Kalkulasi Estimasi Transparan

Pada tahapan ini, spesifikasi mobil listrik yang terverifikasi ditampilkan secara detail:
- **Model Kendaraan:** Misal *Hyundai Ioniq 5 Long Range*
- **Spesifikasi:** Plat Nomor, Kapasitas Baterai (72.6 kWh), Arsitektur Tegangan (800V), dan Level Baterai Awal (misal: 28%).

#### Pilihan Mode Target Pengisian:
1. **Cas 80% (Awet):** Rekomendasi pabrikan EV untuk menjaga keawetan dan suhu kimia sel baterai harian (*Battery Health Protection*).
2. **Cas 100% (Penuh):** Mengisi baterai hingga kapasitas maksimal untuk persiapan perjalanan jarak jauh (*Long Road Trip*).
3. **Input Manual (kWh):** Pengemudi bebas menentukan jumlah kWh yang diinginkan (misal: +10 kWh, +20 kWh, +30 kWh).

#### Ringkasan Kalkulasi Nilai Tambah (Customer Value):
- **Energi Dibutuhkan:** Misal `+37.8 kWh`
- **Jarak Tempuh Tambahan:** Misal **`+257 KM`**
- **Tarif Listrik SPKLU:** Rp 2.466 / kWh
- **Komparasi Hemat Bensin:** **`Hemat Rp 200.500 vs Pertamax (Hemat 68%)`**
- **Estimasi Durasi Pengisian:** 12 Menit (DC Fast) atau 45 Menit (AC Normal)
- **Total Deposit Di-Hold:** Rp 93.215

Klik tombol **Lanjut ke Pembayaran ➜**.

---

### Langkah 3: Konfirmasi Metode Pembayaran & Mulai Pengisian

Sistem VOLTX SPKLU mendukung 3 opsi pembayaran modern:

1. **Saldo Akun (Wallet):** Pemotongan saldo dompet virtual pengguna secara instan.
2. **QRIS Dinamis:** Menghasilkan QR Code QRIS resmi dengan nominal deposit yang sesuai untuk dipindai melalui mobile banking atau e-wallet (GoPay, OVO, Dana).
3. **Simulasi Tap Kartu E-Money / RFID (BCA Flazz / Mandiri e-money):**
   - Klik tombol **"💳 TAP KARTU & CAS SEKARANG"**.
   - Muncul modal reader contactless NFC.
   - Klik kartu **BCA Flazz (BCA - 6656)**.
   - Sistem memverifikasi saldo kartu dalam 2 detik dan langsung memulai pengisian daya secara otomatis.

> [!NOTE]
> Nilai deposit di-hold sementara di awal. Biaya yang ditagihkan murni dihitung berdasarkan total kWh riil yang berhasil disalurkan ke baterai kendaraan. Sisa deposit dikembalikan 100% saat pengisian selesai.

---

### Langkah 4: Pengisian Aktif & Live Telemetri Bahasa Awam

Selama arus listrik mengalir, kedua layar (**Smartphone Driver** dan **Totem Kiosk Mesin**) menampilkan data pemantauan *real-time* via WebSockets:

```
┌──────────────────────────────────────────────────────────────┐
│               ⚡ PENGISIAN SEDANG BERLANGSUNG                │
│             Hyundai Ioniq 5 Long Range (B 1888 ION)          │
├──────────────────────────────────────────────────────────────┤
│                         ╭──────────╮                         │
│                         │  48.5 %  │                         │
│                         │ 142.6 kW │                         │
│                         ╰──────────╯                         │
│                                                              │
│  💡 WAWASAN PENGISIAN RAMAH PENGGUNA (LAYMAN METRICS):       │
│  ┌─────────────────────────────┬──────────────────────────┐  │
│  │ 🚗 Jarak Tempuh Tambahan    │ ⚡ Kecepatan Pengisian    │  │
│  │ +139 KM                     │ +15.5 km/menit           │  │
│  ├─────────────────────────────┼──────────────────────────┤  │
│  │ 💰 Hemat vs Bensin Pertamax │ ⏱️ Sisa Waktu (ETA)      │  │
│  │ Hemat Rp 108.400 (62%)      │ 8 Menit                  │  │
│  └─────────────────────────────┴──────────────────────────┘  │
│                                                              │
│  📊 DATA LISTRIK TEKNIK (ENGINEERING TELEMETRY):             │
│  • Energi Terisi : 20.48 kWh   • Tegangan/Arus : 780V / 183A │
│  • Biaya Berjalan: Rp 50.504   • Sisa Deposit  : Rp 42.711   │
├──────────────────────────────────────────────────────────────┤
│      🛑 SELESAIKAN & CABUT KABEL (STOP & REFUND)             │
└──────────────────────────────────────────────────────────────┘
```

#### Fitur Edukasi Battery Health Protection (Tapering Curve):
Ketika daya baterai mencapai **SoC ≥ 80%**, kurva pengisian melambat secara otomatis dan sistem memunculkan banner edukasi:
> 💡 **Battery Health Protection:** Daya cas melambat otomatis di atas 80% untuk menjaga suhu sel kimia baterai mobil tetap awet.

#### Mekanisme Penghentian Pengisian:
- **Otomatis:** Arus listrik mati seketika saat target baterai (80% atau 100%) tercapai.
- **Manual:** Pengemudi dapat menekan tombol merah **🛑 SELESAIKAN & CABUT KABEL (STOP & REFUND)** kapan pun.

---

### Langkah 5: Struk Digital Transparan & Auto-Refund Seketika

Begitu pengisian selesai, sistem langsung menerbitkan struk pelunasan digital:

- **ID Transaksi:** `#EV-260913-B4C12D`
- **Model Kendaraan:** **Hyundai Ioniq 5 Long Range**
- **Total Energi Listrik:** **22.50 kWh**
- **Jarak Tempuh Tambahan:** **`+153 KM`**
- **Komparasi Hemat Bensin:** **`Hemat Rp 119.500 vs Pertamax (Hemat 61%)`**
- **Biaya Aktual Terpakai:** Rp 55.485
- **Deposit Dibayar Awal:** Rp 93.215
- **Sisa Saldo Di-Refund:** **Rp 37.730 (100% Otomatis Masuk Kembali ke Akun)**

Klik tombol **Selesai & Cabut Nozzle**. Port pengisian kembali ke status `STANDBY` dan siap melayani pengguna berikutnya.

---

## 🎛️ 5. Mode Presentasi Stakeholder (Desktop Mockup View)

Saat membuka halaman Driver di monitor laptop desktop (`/driver`), sistem secara cerdas menampilkan antarmuka presenter:
1. **Mockup Smartphone Interaktif:** Menampilkan aplikasi mobile driver dalam bingkai fisik smartphone yang rapi tanpa scrollbar.
2. **Peralihan Akun Cepat:** Beralih antara akun Budi Santoso dan Siti Rahma dalam 1 klik.
3. **Tombol Reset Stasiun (1-Klik):** Menyetel ulang seluruh konektor stasiun ke kondisi awal bersih seketika jika ingin mengulang skenario demo dari awal.

---

## ❓ 6. Pertanyaan Umum & Pemecahan Masalah (FAQ)

| Pertanyaan / Isu | Penjelasan | Solusi |
| :--- | :--- | :--- |
| **Bagaimana cara mendemokan sistem tanpa kabel USB atau mobil fisik?** | Sistem dirancang dengan mode simulasi cloud mandiri. | Gunakan tombol **1-Klik Simulasi Nozzle** di halaman Driver atau tombol **Simulasi Sambungkan Nozzle** di totem Kiosk. Handshake ISO 15118 dan auto-detect mobil akan berjalan otomatis. |
| **Mengapa ada metrik "Hemat vs Bensin"?** | Edukasi transisi energi untuk non-teknis. | Dihitung dari standar mobil bensin (1 Liter Pertamax Rp 13.700 = 12 KM). Dibandingkan biaya listrik per kWh, pengguna EV menghemat ~60% biaya operasional. |
| **Mengapa kecepatan cas melambat saat baterai 80% ke atas?** | Standar proteksi kimia sel baterai lithium (CC-CV curve). | Pengisian beralih dari *Constant Current* (arus deras) ke *Constant Voltage* (arus lambat) demi mencegah *overheating* dan menjaga degradasi sel baterai. |
| **Bagaimana jika driver ingin berhenti lebih awal sebelum target selesai?** | Fitur proteksi deposit fleksibel. | Cukup tekan tombol merah **🛑 Selesaikan & Cabut Kabel**. Sisa saldo deposit yang belum terpakai akan otomatis dikembalikan detik itu juga. |
| **Bagaimana cara mereset sistem jika terjadi salah klik saat demo?** | Sesi aktif tersimpan di database stasiun. | Klik tombol **🔄 Reset Sesi Stasiun** di layar Driver atau tombol **🛑 Emergency Stop** di layar Kiosk. Seluruh konektor seketika kembali ke status awal. |
