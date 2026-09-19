import socket
import sys
import qrcode
import io

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def print_banner(ip, port):
    driver_url = f"http://{ip}:{port}/driver"
    kiosk_url = f"http://localhost:{port}/kiosk"

    print("=" * 65)
    print("      ⚡ EV CHARGING STATION SIMULATOR (PYTHON / FASTAPI) ⚡")
    print("=" * 65)
    print(f"[*] LAPTOP (Station Kiosk Screen) : {kiosk_url}")
    print(f"[*] HP / SMARTPHONE (Driver App)  : {driver_url}")
    print("=" * 65)
    print("📲 SCAN QR CODE INI MENGGUNAKAN HP ANDA (Pastikan satu Wi-Fi):")
    print()

    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=2,
        )
        qr.add_data(driver_url)
        qr.make(fit=True)
        
        # Print ascii qr to terminal
        f = io.StringIO()
        qr.print_ascii(out=f, invert=True)
        print(f.getvalue())
    except Exception as e:
        print(f"    (Buka browser HP dan ketik: {driver_url})")

    print("-" * 65)
    print("Tekan Ctrl + C untuk menghentikan server.")
    print("=" * 65)

if __name__ == "__main__":
    import os
    import uvicorn
    local_ip = get_local_ip()
    port = int(os.environ.get("PORT", 8000))
    print_banner(local_ip, port)
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)

