import asyncio
import shutil
import subprocess
from typing import Optional, Dict, Any, List
from .charging_engine import ChargingEngine
from .port_mapper import PortMapper
from .billing_service import BillingService
from .station_manager import StationManager
from ..core.config import DISABLE_ADB, CLOUD_MODE

class ADBBatteryMonitor:
    """
    Monitors physical smartphone battery via ADB shell commands.
    Supports multiple concurrent Android devices connected to physical USB ports.
    """
    
    _is_running: bool = False
    _poll_interval: float = 1.5  # seconds
    _active_devices: Dict[str, Dict[str, Any]] = {}  # serial -> device_info

    @classmethod
    def parse_battery_dump(cls, output: str) -> Dict[str, Any]:
        """Parse raw text output of 'adb -s <serial> shell dumpsys battery'"""
        result = {
            "connected": True,
            "ac_powered": False,
            "usb_powered": False,
            "wireless_powered": False,
            "dock_powered": False,
            "level": 0,
            "scale": 100,
            "status": 0,       # 1=Unknown, 2=Charging, 3=Discharging, 4=Not charging, 5=Full
            "health": 2,       # 2=Good
            "voltage": 0,
            "temperature": 0,  # e.g. 377 -> 37.7°C
            "technology": "",
            "present": True,
            "is_charging": False
        }

        for line in output.splitlines():
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip().lower()
                value = value.strip()

                if key == "level":
                    try:
                        result["level"] = int(value)
                    except ValueError:
                        pass
                elif key == "scale":
                    try:
                        result["scale"] = int(value)
                    except ValueError:
                        pass
                elif key == "status":
                    try:
                        result["status"] = int(value)
                    except ValueError:
                        pass
                elif key == "health":
                    try:
                        result["health"] = int(value)
                    except ValueError:
                        pass
                elif key == "voltage":
                    try:
                        result["voltage"] = int(value)
                    except ValueError:
                        pass
                elif key == "temperature":
                    try:
                        result["temperature"] = int(value)
                    except ValueError:
                        pass
                elif key == "technology":
                    result["technology"] = value
                elif key == "ac powered":
                    result["ac_powered"] = (value.lower() == "true")
                elif key == "usb powered":
                    result["usb_powered"] = (value.lower() == "true")
                elif key == "wireless powered":
                    result["wireless_powered"] = (value.lower() == "true")
                elif key == "present":
                    result["present"] = (value.lower() == "true")

        result["is_charging"] = (result["status"] == 2) or result["usb_powered"] or result["ac_powered"]
        return result

    @classmethod
    def is_adb_available(cls) -> bool:
        if CLOUD_MODE or DISABLE_ADB:
            return False
        which = shutil.which("adb")
        if which:
            return True
        import os
        candidates = [
            r"C:\platform-tools\adb.exe",
            os.path.expanduser(r"~\AppData\Local\Android\Sdk\platform-tools\adb.exe")
        ]
        return any(os.path.isfile(c) for c in candidates)

    @classmethod
    def get_adb_binary(cls) -> str:
        which = shutil.which("adb")
        if which:
            return which
        import os
        candidates = [
            r"C:\platform-tools\adb.exe",
            os.path.expanduser(r"~\AppData\Local\Android\Sdk\platform-tools\adb.exe")
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return "adb"

    @classmethod
    def scan_all_adb_devices(cls) -> Dict[str, Dict[str, Any]]:
        """
        Scans all connected devices via 'adb devices' and queries battery stats
        concurrently per device with 'adb -s <serial> shell dumpsys battery'.
        Returns: Dict[serial, device_info]
        """
        adb_bin = cls.get_adb_binary()
        creationflags = 0
        try:
            creationflags = subprocess.CREATE_NO_WINDOW
        except AttributeError:
            pass

        try:
            dev_res = subprocess.run(
                [adb_bin, "devices"],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=creationflags
            )
            if dev_res.returncode != 0:
                return {}

            lines = dev_res.stdout.splitlines()
            serials_found = []
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 2 and not line.startswith("List of"):
                    serial = parts[0]
                    status = parts[1]
                    serials_found.append((serial, status))

            if not serials_found:
                return {}

            results: Dict[str, Dict[str, Any]] = {}

            for serial, status in serials_found:
                port_info = PortMapper.get_device_port_by_serial(serial)
                port_key = PortMapper.extract_port_key(port_info)
                connector_id = PortMapper.get_connector_id_for_port(port_info)

                if "unauthorized" in status.lower():
                    results[serial] = {
                        "connected": True,
                        "unauthorized": True,
                        "serial": serial,
                        "level": 50,
                        "usb_powered": True,
                        "is_charging": True,
                        "port": port_info,
                        "port_key": port_key,
                        "connector_id": connector_id
                    }
                    continue

                battery_res = subprocess.run(
                    [adb_bin, "-s", serial, "shell", "dumpsys", "battery"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    creationflags=creationflags
                )

                if battery_res.returncode == 0 and battery_res.stdout and "level:" in battery_res.stdout:
                    device_data = cls.parse_battery_dump(battery_res.stdout)
                else:
                    device_data = {
                        "connected": True,
                        "ac_powered": False,
                        "usb_powered": True,
                        "level": 50,
                        "scale": 100,
                        "status": 2,
                        "health": 2,
                        "voltage": 4000,
                        "temperature": 320,
                        "technology": "Li-poly",
                        "present": True,
                        "is_charging": True
                    }

                device_data["serial"] = serial
                device_data["port"] = port_info
                device_data["port_key"] = port_key
                device_data["connector_id"] = connector_id

                results[serial] = device_data

            return results
        except Exception:
            return {}

    @classmethod
    async def _sync_connectors_with_devices(cls, current_devices: Dict[str, Dict[str, Any]], force_all_unplugged: bool = False):
        """
        Synchronizes DB connector statuses with physically connected devices:
        - Sets newly plugged connectors to 'CONNECTED'.
        - Sets unplugged connectors back to 'AVAILABLE'.
        """
        from ..database import SessionLocal
        from .. import models

        db = SessionLocal()
        try:
            active_connector_ids = {
                d["connector_id"] for d in current_devices.values() if d.get("connector_id")
            }
            active_connector_ids.update(StationManager.simulated_plugged_ids)

            # 1. Connectors physically plugged: set to CONNECTED if AVAILABLE
            for serial, device in current_devices.items():
                cid = device.get("connector_id")
                if not cid:
                    continue

                connector = db.query(models.Connector).filter(models.Connector.id == cid).first()
                if not connector:
                    continue

                if connector.status == "AVAILABLE":
                    connector.status = "CONNECTED"
                    db.commit()

                    port_key = device.get("port_key") or "Port USB"
                    await ChargingEngine.broadcast({
                        "event": "PORT_NOZZLE_CONNECTED",
                        "serial": serial,
                        "port": device.get("port"),
                        "port_key": port_key,
                        "connector_id": connector.id,
                        "connector_name": connector.name,
                        "type_category": connector.type_category,
                        "battery_level": device.get("level", 0),
                        "message": f"⚡ Kabel USB terdeteksi dicolok ke {port_key}! {connector.name} otomatis terkunci."
                    })

            # 2. Check connectors marked CONNECTED whose physical cable is unplugged
            stale_query = db.query(models.Connector).filter(models.Connector.status == "CONNECTED")
            if active_connector_ids:
                stale_query = stale_query.filter(~models.Connector.id.in_(active_connector_ids))
            stale_connected = stale_query.all()

            for sc in stale_connected:
                sc.status = "AVAILABLE"
                sc.current_session_id = None
                sc.locked_by_user_id = None
                db.commit()

                await ChargingEngine.broadcast({
                    "event": "NOZZLE_UNPLUGGED",
                    "station_id": sc.station_id,
                    "connector_id": sc.id,
                    "connector_name": sc.name,
                    "status": "AVAILABLE",
                    "message": f"🔌 Kabel USB dicabut dari {sc.name}. Nozzle kembali standby."
                })

            # 3. Check active sessions marked CHARGING whose physical cable was unplugged
            active_sessions_query = db.query(models.ChargingSession).filter(models.ChargingSession.status == "CHARGING")
            if active_connector_ids:
                active_sessions_query = active_sessions_query.filter(~models.ChargingSession.connector_id.in_(active_connector_ids))
            unplugged_charging_sessions = active_sessions_query.all()

            for s in unplugged_charging_sessions:
                ChargingEngine.request_stop(s.id)

                conn = db.query(models.Connector).filter(models.Connector.id == s.connector_id).first()
                if conn:
                    conn.status = "AVAILABLE"
                    conn.current_session_id = None
                    conn.locked_by_user_id = None

                s.status = "COMPLETED"
                s.stop_reason = "CABLE_UNPLUGGED"
                actual_cost, refund_amount = BillingService.settle_and_refund(db, s)
                db.commit()

                await ChargingEngine.broadcast({
                    "event": "SESSION_COMPLETED",
                    "station_id": s.station_id,
                    "connector_id": s.connector_id,
                    "session_id": s.id,
                    "session_code": s.session_code,
                    "stop_reason": "CABLE_UNPLUGGED",
                    "final_soc": s.current_soc,
                    "total_energy_kwh": s.energy_delivered_kwh,
                    "total_energy_mah": round((s.energy_delivered_kwh / 0.02) * 5000.0, 0),
                    "deposit_paid": s.deposit_paid,
                    "actual_cost": actual_cost,
                    "refund_amount": refund_amount,
                    "payment_method": s.payment_method,
                    "message": "🔌 Kabel USB dicabut saat pengisian! Sesi otomatis diselesaikan dan sisa deposit dikembalikan."
                })
                if conn:
                    await ChargingEngine.broadcast({
                        "event": "NOZZLE_UNPLUGGED",
                        "station_id": conn.station_id,
                        "connector_id": conn.id,
                        "connector_name": conn.name,
                        "status": "AVAILABLE",
                        "message": f"🔌 Kabel USB dicabut dari {conn.name}. Nozzle kembali standby."
                    })

            # 4. Check orphaned connectors marked CHARGING without cable
            stale_charging_conns = db.query(models.Connector).filter(models.Connector.status == "CHARGING")
            if active_connector_ids:
                stale_charging_conns = stale_charging_conns.filter(~models.Connector.id.in_(active_connector_ids))
            for sc in stale_charging_conns.all():
                sc.status = "AVAILABLE"
                sc.current_session_id = None
                sc.locked_by_user_id = None
                db.commit()
                await ChargingEngine.broadcast({
                    "event": "NOZZLE_UNPLUGGED",
                    "station_id": sc.station_id,
                    "connector_id": sc.id,
                    "connector_name": sc.name,
                    "status": "AVAILABLE",
                    "message": f"🔌 Kabel USB dicabut dari {sc.name}. Nozzle kembali standby."
                })

        finally:
            db.close()

    @classmethod
    async def _handle_hardware_disconnected(cls):
        """Helper for clean disconnection handling when all devices are unplugged."""
        await cls._sync_connectors_with_devices({}, force_all_unplugged=True)
        await ChargingEngine.broadcast({
            "event": "ADB_BATTERY_DISCONNECTED",
            "connected": False,
            "device_count": 0,
            "devices": [],
            "message": "🔌 Semua kabel USB dicabut / tidak terhubung. Seluruh nozzle kembali standby."
        })

    @classmethod
    async def start_monitoring(cls):
        """Background coroutine that polls ADB battery info and broadcasts via WebSocket."""
        if not cls.is_adb_available():
            return

        if cls._is_running:
            return
        cls._is_running = True
        loop = asyncio.get_running_loop()

        while cls._is_running:
            try:
                current_devices = await loop.run_in_executor(None, cls.scan_all_adb_devices)
                had_devices = len(cls._active_devices) > 0
                has_devices = len(current_devices) > 0

                await cls._sync_connectors_with_devices(current_devices)
                cls._active_devices = current_devices

                if has_devices:
                    primary_device = next(iter(current_devices.values()))
                    await ChargingEngine.broadcast({
                        "event": "ADB_BATTERY_UPDATE",
                        "connected": True,
                        "device_count": len(current_devices),
                        "devices": list(current_devices.values()),
                        "level": primary_device.get("level", 0),
                        "usb_powered": primary_device.get("usb_powered", False),
                        "ac_powered": primary_device.get("ac_powered", False),
                        "status": primary_device.get("status", 0),
                        "voltage": primary_device.get("voltage", 0),
                        "temperature": primary_device.get("temperature", 0),
                        "technology": primary_device.get("technology", ""),
                        "is_charging": primary_device.get("is_charging", False),
                        "port": primary_device.get("port"),
                        "connector_id": primary_device.get("connector_id")
                    })
                else:
                    if had_devices:
                        await ChargingEngine.broadcast({
                            "event": "ADB_BATTERY_DISCONNECTED",
                            "connected": False,
                            "device_count": 0,
                            "devices": [],
                            "message": "🔌 Semua kabel USB dicabut / tidak terhubung. Seluruh nozzle kembali standby."
                        })
            except Exception:
                pass

            await asyncio.sleep(cls._poll_interval)

    @classmethod
    def get_last_state(cls) -> Optional[Dict[str, Any]]:
        """Returns primary device state or disconnected payload."""
        if not cls._active_devices:
            return {"connected": False, "device_count": 0, "devices": []}
        primary = next(iter(cls._active_devices.values()))
        primary["device_count"] = len(cls._active_devices)
        primary["devices"] = list(cls._active_devices.values())
        return primary

    @classmethod
    def get_all_active_devices(cls) -> List[Dict[str, Any]]:
        return list(cls._active_devices.values())

    @classmethod
    def get_current_port_info(cls) -> Dict[str, Any]:
        """Returns active port info of primary device and total count."""
        if not cls._active_devices:
            return {"serial": None, "port": None, "connector_id": None, "total_connected": 0}
        primary = next(iter(cls._active_devices.values()))
        return {
            "serial": primary.get("serial"),
            "port": primary.get("port"),
            "connector_id": primary.get("connector_id"),
            "total_connected": len(cls._active_devices)
        }

    @classmethod
    def stop(cls) -> None:
        cls._is_running = False
