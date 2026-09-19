import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
TOOLS_DIR = BASE_DIR / "tools"
CONFIG_FILE = BASE_DIR / "usb_ports_config.json"

# Database configuration
DATABASE_URL = os.environ.get("DATABASE_URL")
DB_PATH = BASE_DIR / "charging_station.db"

# Server configuration
PORT = int(os.environ.get("PORT", 8000))
STATION_CODE = os.environ.get("STATION_CODE", "CS-SDR-01")

# Hardware & ADB configuration
DISABLE_ADB = os.environ.get("DISABLE_ADB", "false").lower() == "true"
CLOUD_MODE = (
    os.environ.get("CLOUD_MODE", "false").lower() == "true"
    or bool(os.environ.get("RENDER"))
)
