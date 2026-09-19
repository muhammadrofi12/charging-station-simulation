#!/usr/bin/env python3
"""
VOLTX SPKLU - Interactive USB Port Calibration Tool
Memudahkan pemetaan port fisik USB laptop ke Nozzle SPKLU (1, 2, atau 3)
saat menjalankan simulator di komputer / laptop baru.
"""

import os
import sys
import json
import argparse
from typing import Dict, Any

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.services.port_mapper import PortMapper
from app.services.adb_battery import ADBBatteryMonitor

NOZZLE_NAMES = {
    1: "Nozzle 1 - AC Normal (Type 2, Max 22.000 W)",
    2: "Nozzle 2 - DC Fast (CHAdeMO, Max 50.000 W)",
    3: "Nozzle 3 - DC Ultra-Fast (CCS2, Max 150.000 W)"
}

def print_header():
    print("=" * 64)
    print("⚡ VOLTX SPKLU - KALIBRASI PORT USB HARDWARE")
    print("   Simulator Pengisian Kendaraan Listrik (EVCS)")
    print("=" * 64)

def list_current_mappings():
    mappings = PortMapper.get_all_mappings()
    print("\n📋 Daftar Pemetaan Port USB Saat Ini (usb_ports_config.json):")
    if not mappings:
        print("   (Belum ada konfigurasi port)")
        return
    for port_key, info in mappings.items():
        cid = info.get("connector_id") if isinstance(info, dict) else info
        label = info.get("label", "") if isinstance(info, dict) else ""
        nozzle_name = NOZZLE_NAMES.get(cid, f"Nozzle {cid}")
        print(f"   • {port_key:<14} ➔ {nozzle_name} | Label: {label}")
    print()

def main():
    parser = argparse.ArgumentParser(description="Kalibrasi Port USB Hardware untuk Simulator VOLTX SPKLU")
    parser.add_argument("--list", action="store_true", help="Tampilkan konfigurasi mapping port saat ini")
    parser.add_argument("--nozzle", type=int, choices=[1, 2, 3], help="Petakan port perangkat yang terhubung langsung ke Nozzle (1/2/3)")
    args = parser.parse_args()

    print_header()

    if args.list:
        list_current_mappings()
        return

    adb_bin = ADBBatteryMonitor.get_adb_binary()
    print(f"\n[1/3] Memeriksa Android Debug Bridge (ADB)...")
    print(f"      Lokasi ADB: {adb_bin}")

    print(f"\n[2/3] Memindai perangkat HP Android yang tercolok...")
    devices = ADBBatteryMonitor.scan_all_adb_devices()

    if not devices:
        print("      ⚠️ Tidak ada perangkat Android yang terdeteksi via ADB!")
        print("      Langkah Solusi:")
        print("      1. Pastikan kabel data USB sudah dicolokkan ke laptop dan HP.")
        print("      2. Pastikan 'USB Debugging' sudah aktif di Opsi Pengembang HP.")
        print("      3. Pastikan dialog izin RSA di layar HP sudah disetujui ('Selalu izinkan').")
        print("      4. Coba ketik 'adb devices' di terminal untuk memastikan statusnya 'device'.\n")
        list_current_mappings()
        sys.exit(1)

    print(f"      [✓] Terdeteksi {len(devices)} perangkat fisik:")
    for serial, data in devices.items():
        port_raw = data.get("port") or "Unknown"
        port_key = data.get("port_key") or port_raw
        current_cid = data.get("connector_id")
        mapped_to = NOZZLE_NAMES.get(current_cid, "Belum dipetakan (Unmapped)")
        print(f"      • Serial   : {serial}")
        print(f"        Port USB : {port_raw} (Key: {port_key})")
        print(f"        Status   : {mapped_to}")

    # Process calibration for the first device
    primary_serial = list(devices.keys())[0]
    dev = devices[primary_serial]
    port_raw = dev.get("port")
    port_key = dev.get("port_key") or PortMapper.extract_port_key(port_raw)

    if not port_key or port_key == "Unknown":
        print("\n⚠️ Tidak dapat membaca identitas LocationInformation port fisik Windows.")
        print("   (Mungkin sistem operasi bukan Windows atau izin registry dibatasi).")
        port_key = "Port_#0002"
        print(f"   Menggunakan default fallback: {port_key}")

    print(f"\n[3/3] Menyetel Pemetaan Port untuk '{port_key}':")
    for cid, name in NOZZLE_NAMES.items():
        print(f"      [{cid}] {name}")

    chosen_cid = args.nozzle
    if not chosen_cid:
        while True:
            try:
                user_input = input(f"\nPilih nomor nozzle untuk port ini (1/2/3) [default: 1]: ").strip()
                if not user_input:
                    chosen_cid = 1
                    break
                chosen_cid = int(user_input)
                if chosen_cid in (1, 2, 3):
                    break
                print("Pilihan tidak valid, silakan masukkan 1, 2, atau 3.")
            except (KeyboardInterrupt, EOFError):
                print("\nBatal.")
                sys.exit(0)
            except ValueError:
                print("Harap masukkan angka 1, 2, atau 3.")

    label = f"Port USB Laptop -> Nozzle {chosen_cid}"
    PortMapper.set_port_mapping(port_key, chosen_cid, label)

    print(f"\n" + "=" * 64)
    print(f"✅ SUKSES! Port '{port_key}' berhasil dipetakan ke Nozzle {chosen_cid}!")
    print(f"   Konfigurasi disimpan permanen ke usb_ports_config.json.")
    print("=" * 64)

    list_current_mappings()
    print("🚀 Anda sekarang dapat menjalankan simulator:")
    print("   python run.py\n")

if __name__ == "__main__":
    main()
