import unittest
import asyncio
from app.database import SessionLocal
from app import models
from app.services.port_mapper import PortMapper
from app.services.adb_battery import ADBBatteryMonitor

class TestPortMapper(unittest.TestCase):
    def test_extract_port_key(self):
        self.assertEqual(PortMapper.extract_port_key("Port_#0002.Hub_#0001"), "Port_#0002")
        self.assertEqual(PortMapper.extract_port_key("Port_#0003.Hub_#0002"), "Port_#0003")
        self.assertEqual(PortMapper.extract_port_key("Port_#0004"), "Port_#0004")
        self.assertEqual(PortMapper.extract_port_key(""), "")
        self.assertEqual(PortMapper.extract_port_key(None), "")

    def test_default_connector_mapping(self):
        # Port 2 -> Connector 1 (AC)
        self.assertEqual(PortMapper.get_connector_id_for_port("Port_#0002.Hub_#0001"), 1)
        # Port 3 -> Connector 2 (DC)
        self.assertEqual(PortMapper.get_connector_id_for_port("Port_#0003.Hub_#0001"), 2)
        # Port 4 -> Connector 3 (CCS)
        self.assertEqual(PortMapper.get_connector_id_for_port("Port_#0004.Hub_#0001"), 3)

    def test_dynamic_fallback_mapping(self):
        # Even if unconfigured port, extracts trailing port number within 1..3
        self.assertEqual(PortMapper.get_connector_id_for_port("Port_#0001.Hub_#0009"), 1)

    def test_set_and_get_mapping(self):
        PortMapper.set_port_mapping("Port_#0008", 2, "Test Custom Port 8")
        self.assertEqual(PortMapper.get_connector_id_for_port("Port_#0008.Hub_#0001"), 2)
        mappings = PortMapper.get_all_mappings()
        self.assertIn("Port_#0008", mappings)
        self.assertEqual(mappings["Port_#0008"]["connector_id"], 2)

    def test_concurrent_multi_port_connection(self):
        """Verify that 2 devices plugged into Port 2 and Port 3 concurrently lock BOTH Nozzle 1 & Nozzle 2!"""
        db = SessionLocal()
        try:
            # Set all connectors to AVAILABLE
            db.query(models.Connector).update({"status": "AVAILABLE", "current_session_id": None})
            db.commit()

            # Simulate 2 devices detected concurrently:
            # Device 1 in Port 2 (Nozzle 1) and Device 2 in Port 3 (Nozzle 2)
            simulated_devices = {
                "serial_phone_1": {
                    "serial": "serial_phone_1",
                    "port": "Port_#0002.Hub_#0001",
                    "port_key": "Port_#0002",
                    "connector_id": 1,
                    "level": 80
                },
                "serial_phone_2": {
                    "serial": "serial_phone_2",
                    "port": "Port_#0003.Hub_#0001",
                    "port_key": "Port_#0003",
                    "connector_id": 2,
                    "level": 65
                }
            }

            asyncio.run(ADBBatteryMonitor._sync_connectors_with_devices(simulated_devices))
            db.expire_all()

            # Verify BOTH Connector 1 and Connector 2 are CONNECTED at the same time!
            c1 = db.query(models.Connector).filter(models.Connector.id == 1).first()
            c2 = db.query(models.Connector).filter(models.Connector.id == 2).first()
            c3 = db.query(models.Connector).filter(models.Connector.id == 3).first()

            self.assertIsNotNone(c1)
            self.assertIsNotNone(c2)
            self.assertEqual(c1.status, "CONNECTED")
            self.assertEqual(c2.status, "CONNECTED")
            # Connector 3 was not plugged, so it remains AVAILABLE
            self.assertEqual(c3.status, "AVAILABLE")

        finally:
            db.close()

    def test_independent_unplug_keeps_other_connected(self):
        """Verify that unplugging Device 2 leaves Device 1 still CONNECTED!"""
        db = SessionLocal()
        try:
            # Start with both 1 and 2 CONNECTED
            c1 = db.query(models.Connector).filter(models.Connector.id == 1).first()
            c2 = db.query(models.Connector).filter(models.Connector.id == 2).first()
            c1.status = "CONNECTED"
            c2.status = "CONNECTED"
            db.commit()

            # Now Device 2 is unplugged, only Device 1 remains:
            remaining_devices = {
                "serial_phone_1": {
                    "serial": "serial_phone_1",
                    "port": "Port_#0002.Hub_#0001",
                    "port_key": "Port_#0002",
                    "connector_id": 1,
                    "level": 82
                }
            }

            asyncio.run(ADBBatteryMonitor._sync_connectors_with_devices(remaining_devices))

            db.refresh(c1)
            db.refresh(c2)

            # Connector 1 remains CONNECTED!
            self.assertEqual(c1.status, "CONNECTED")
            # Connector 2 was unplugged, so it reverted to AVAILABLE!
            self.assertEqual(c2.status, "AVAILABLE")

        finally:
            db.close()

    def test_dev_remap_active_port(self):
        """Verify dev_remap_active_port updates PortMapper and responds with SUCCESS."""
        from app.routers import api_station
        req = api_station.DevRemapPortRequest(connector_id=3, port_key="Port_#0002")
        db = SessionLocal()
        try:
            res = asyncio.run(api_station.dev_remap_active_port(req, db))
            self.assertEqual(res["status"], "SUCCESS")
            self.assertEqual(res["connector_id"], 3)
            # Verify PortMapper now resolves Port_#0002 to connector 3
            self.assertEqual(PortMapper.get_connector_id_for_port("Port_#0002"), 3)

            # Revert back to connector 1 for clean state
            req_revert = api_station.DevRemapPortRequest(connector_id=1, port_key="Port_#0002")
            res_revert = asyncio.run(api_station.dev_remap_active_port(req_revert, db))
            self.assertEqual(res_revert["status"], "SUCCESS")
            self.assertEqual(PortMapper.get_connector_id_for_port("Port_#0002"), 1)
        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()
