import os
import sys
import re
import time
import subprocess
import threading
import signal

# Ensure UTF-8 output on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
CLOUDFLARED_EXE = os.path.join(TOOLS_DIR, "cloudflared.exe")
DOWNLOAD_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"

def ensure_cloudflared():
    """Ensure cloudflared.exe exists, download if missing."""
    if os.path.isfile(CLOUDFLARED_EXE):
        return CLOUDFLARED_EXE
    
    os.makedirs(TOOLS_DIR, exist_ok=True)
    print("[-] cloudflared.exe belum ditemukan. Mengunduh secara otomatis dari Cloudflare...")
    try:
        import urllib.request
        def reporthook(blocknum, blocksize, totalsize):
            percent = blocknum * blocksize * 100 / totalsize
            sys.stdout.write(f"\r    Mengunduh: {percent:.1f}% ({blocknum * blocksize // (1024*1024)} MB)")
            sys.stdout.flush()
        urllib.request.urlretrieve(DOWNLOAD_URL, CLOUDFLARED_EXE, reporthook)
        print("\n[✓] Berhasil mengunduh cloudflared.exe!")
        return CLOUDFLARED_EXE
    except Exception as e:
        print(f"\n[!] Gagal mengunduh cloudflared: {e}")
        print(f"    Silakan unduh manual dari: {DOWNLOAD_URL}")
        print(f"    Dan letakkan di: {CLOUDFLARED_EXE}")
        sys.exit(1)

def print_qr_banner(tunnel_url, port=8000):
    driver_url = f"{tunnel_url}/driver"
    kiosk_url = f"{tunnel_url}/kiosk"
    local_kiosk = f"http://localhost:{port}/kiosk"

    print("\n" + "=" * 70)
    print("      ⚡ VOLTX EV CHARGING STATION (CLOUDFLARE PUBLIC TUNNEL) ⚡")
    print("=" * 70)
    print(f" [💻] LAPTOP KIOSK (LOKAL)   : {local_kiosk}")
    print(f" [🌐] LAPTOP KIOSK (PUBLIK)  : {kiosk_url}")
    print(f" [📱] SMARTPHONE DRIVER APP  : {driver_url}")
    print("=" * 70)
    print("📲 SCAN QR CODE INI MENGGUNAKAN HP ANDA / PENGUJI / DOSEN:")
    print("   (Bisa dibuka dari mana saja: Paket Data Seluler 4G/5G atau Wi-Fi)\n")

    try:
        import qrcode
        import io
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=2,
        )
        qr.add_data(driver_url)
        qr.make(fit=True)
        f = io.StringIO()
        qr.print_ascii(out=f, invert=True)
        print(f.getvalue())
    except Exception:
        print(f"    Buka browser di HP dan ketik link: {driver_url}\n")

    print("-" * 70)
    print(" [✓] WebSockets (WSS)  : AKTIF (Sinkronisasi Real-Time Dua Arah)")
    print(" [✓] Hardware USB & ADB: AKTIF (Deteksi colokan HP laptop tetap berfungsi)")
    print(" [✓] Biaya Hosting     : GRATIS ($0 / Tanpa Kartu Kredit)")
    print("-" * 70)
    print(" Tekan Ctrl + C untuk menghentikan server dan menutup tunnel.")
    print("=" * 70 + "\n")

def main():
    port = 8000
    cloudflared_path = ensure_cloudflared()

    print("[*] Memulai server FastAPI (VOLTX SPKLU)...")
    # Start uvicorn server in subprocess
    uvicorn_cmd = [
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "127.0.0.1",
        "--port", str(port),
        "--log-level", "warning"
    ]
    
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    server_proc = subprocess.Popen(
        uvicorn_cmd,
        cwd=BASE_DIR,
        creationflags=creationflags
    )

    time.sleep(1.5)  # Wait for uvicorn to bind port

    log_file_path = os.path.join(TOOLS_DIR, "tunnel.log")
    if os.path.exists(log_file_path):
        try:
            os.remove(log_file_path)
        except Exception:
            pass

    print("[*] Menghubungkan ke Cloudflare Edge Network...")
    tunnel_cmd = [
        cloudflared_path, "tunnel",
        "--url", f"http://127.0.0.1:{port}",
        "--logfile", log_file_path
    ]

    tunnel_proc = subprocess.Popen(
        tunnel_cmd,
        cwd=BASE_DIR,
        creationflags=creationflags
    )

    tunnel_url = None
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    # Tail log_file_path until public URL is detected
    def monitor_tunnel():
        nonlocal tunnel_url
        while not tunnel_url and tunnel_proc.poll() is None:
            if os.path.exists(log_file_path):
                try:
                    with open(log_file_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                        match = url_pattern.search(content)
                        if match:
                            tunnel_url = match.group(0)
                            print_qr_banner(tunnel_url, port)
                            break
                except Exception:
                    pass
            time.sleep(0.5)

    t = threading.Thread(target=monitor_tunnel, daemon=True)
    t.start()

    def shutdown(sig=None, frame=None):
        print("\n[*] Menutup Cloudflare Tunnel dan Server...")
        try:
            tunnel_proc.terminate()
            tunnel_proc.wait(timeout=2)
        except Exception:
            pass
        try:
            server_proc.terminate()
            server_proc.wait(timeout=2)
        except Exception:
            pass
        print("[✓] Server dan Tunnel berhasil dihentikan dengan aman.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            time.sleep(1)
            if server_proc.poll() is not None:
                print("[!] Server FastAPI terhenti.")
                shutdown()
            if tunnel_proc.poll() is not None:
                print("[!] Cloudflare Tunnel terhenti.")
                shutdown()
    except KeyboardInterrupt:
        shutdown()

if __name__ == "__main__":
    main()
