import unittest
from app.services.adb_battery import ADBBatteryMonitor

SAMPLE_DUMP = """Current Battery Service state:
  AC powered: false
  USB powered: true
  Wireless powered: false
  Dock powered: false
  Max charging current: 0
 Time when the latest updated value of the Max charging current was sent via battery changed broadcast: +16s303ms
  Max charging voltage: 0
  Charge counter: 2520000
  status: 2
  health: 2
  present: true
  level: 65
  scale: 100
  voltage: 4077
 Time when the latest updated value of the voltage was sent via battery changed broadcast: +2d17h47m4s400ms
 The last voltage value sent via the battery changed broadcast: 4074
  temperature: 377
  technology: Li-poly
  Charging state: 0
  Charging policy: 0
  Capacity level: 3
MiuiBatteryService first usage time:
  mSetBatteryUsageTimeCount=0
  mNtpTime=-1
  mParseNtpTime=
"""

class TestADBBattery(unittest.TestCase):
    def test_parse_battery_dump(self):
        result = ADBBatteryMonitor.parse_battery_dump(SAMPLE_DUMP)
        self.assertTrue(result["connected"])
        self.assertFalse(result["ac_powered"])
        self.assertTrue(result["usb_powered"])
        self.assertEqual(result["level"], 65)
        self.assertEqual(result["scale"], 100)
        self.assertEqual(result["status"], 2)
        self.assertEqual(result["voltage"], 4077)
        self.assertEqual(result["temperature"], 377)
        self.assertEqual(result["technology"], "Li-poly")
        self.assertTrue(result["is_charging"])

    def test_parse_empty_dump(self):
        result = ADBBatteryMonitor.parse_battery_dump("")
        self.assertEqual(result["level"], 0)
        self.assertFalse(result["is_charging"])

    def test_handle_hardware_disconnected(self):
        import asyncio
        from app.database import SessionLocal
        from app import models
        db = SessionLocal()
        try:
            # Set connector 1 to CONNECTED
            c = db.query(models.Connector).first()
            if c:
                c.status = "CONNECTED"
                db.commit()

            # Run disconnect handler
            asyncio.run(ADBBatteryMonitor._handle_hardware_disconnected())

            # Verify connector reset to AVAILABLE
            c = db.query(models.Connector).first()
            if c:
                self.assertEqual(c.status, "AVAILABLE")
        finally:
            db.close()

    def test_sync_connectors_with_devices_unplug(self):
        import asyncio
        from app.database import SessionLocal
        from app import models
        db = SessionLocal()
        try:
            c1 = db.query(models.Connector).filter(models.Connector.id == 1).first()
            if c1:
                c1.status = "CONNECTED"
                db.commit()

            # Call _sync_connectors_with_devices with empty dict (unplugged)
            asyncio.run(ADBBatteryMonitor._sync_connectors_with_devices({}))

            # Verify connector 1 is now AVAILABLE
            db.refresh(c1)
            self.assertEqual(c1.status, "AVAILABLE")
        finally:
            db.close()

    def test_sync_connectors_mid_charge_unplug(self):
        import asyncio
        from datetime import datetime
        from app.database import SessionLocal
        from app import models
        db = SessionLocal()
        try:
            c = db.query(models.Connector).filter(models.Connector.id == 3).first()
            u = db.query(models.User).first()
            v = db.query(models.Vehicle).first()
            if not c or not u or not v:
                return

            c.status = "CHARGING"
            c.locked_by_user_id = u.id

            import uuid
            s = models.ChargingSession(
                session_code=f"EV-TEST-{uuid.uuid4().hex[:8].upper()}",
                user_id=u.id,
                station_id=c.station_id,
                connector_id=c.id,
                vehicle_id=v.id,
                start_soc=50.0,
                target_soc=100.0,
                current_soc=55.0,
                target_type="FULL",
                target_kwh=10.0,
                deposit_paid=50000.0,
                payment_method="WALLET",
                status="CHARGING",
                start_time=datetime.utcnow()
            )
            db.add(s)
            db.commit()
            db.refresh(s)
            c.current_session_id = s.id
            db.commit()

            # Physical unplug: no active devices detected for connector 3
            asyncio.run(ADBBatteryMonitor._sync_connectors_with_devices({}))

            # Verify connector 3 is now AVAILABLE and session is COMPLETED
            db.refresh(c)
            db.refresh(s)
            self.assertEqual(c.status, "AVAILABLE")
            self.assertIsNone(c.current_session_id)
            self.assertIsNone(c.locked_by_user_id)
            self.assertEqual(s.status, "COMPLETED")
            self.assertEqual(s.stop_reason, "CABLE_UNPLUGGED")
        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()
