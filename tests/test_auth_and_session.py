import unittest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.database import Base
from app import models, schemas
from app.routers import api_auth, api_station

class TestAuthAndSessionIsolation(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = TestingSessionLocal()

        # Seed test user 1 (Budi)
        self.user1 = models.User(
            username="driver1",
            full_name="Budi Santoso",
            phone="081298765432",
            password_hash="password123",
            role="DRIVER",
            wallet_balance=150000.0
        )
        # Seed test user 2 (Siti)
        self.user2 = models.User(
            username="driver2",
            full_name="Siti Rahma",
            phone="081311223344",
            password_hash="password123",
            role="DRIVER",
            wallet_balance=200000.0
        )
        self.db.add_all([self.user1, self.user2])
        self.db.commit()

        # Seed Station & 3 Connectors (AC, DC, CCS)
        self.station = models.Station(
            code="CS-SDR-01",
            name="SPKLU Sudirman",
            location="SCBD Jakarta",
            status="AVAILABLE"
        )
        self.db.add(self.station)
        self.db.commit()

        self.c1 = models.Connector(
            station_id=self.station.id,
            connector_number=1,
            name="Nozzle 1 - AC (Type 2)",
            type_category="AC",
            connector_type="Type 2",
            max_power_kw=22.0,
            tariff_per_kwh=2466.0,
            status="AVAILABLE"
        )
        self.c2 = models.Connector(
            station_id=self.station.id,
            connector_number=2,
            name="Nozzle 2 - DC (CHAdeMO)",
            type_category="DC",
            connector_type="CHAdeMO",
            max_power_kw=50.0,
            tariff_per_kwh=3000.0,
            status="AVAILABLE"
        )
        self.c3 = models.Connector(
            station_id=self.station.id,
            connector_number=3,
            name="Nozzle 3 - CCS (CCS2)",
            type_category="DC",
            connector_type="CCS2",
            max_power_kw=150.0,
            tariff_per_kwh=3500.0,
            status="AVAILABLE"
        )
        self.db.add_all([self.c1, self.c2, self.c3])
        self.db.commit()

        # Seed car vehicle for user 1 and user 2
        self.car1 = models.Vehicle(
            user_id=self.user1.id,
            brand="Hyundai",
            model="Ioniq 5 Long Range",
            license_plate="B 1234 EV",
            battery_capacity_kwh=72.6,
            current_soc=40.0,
            efficiency_km_kwh=6.8
        )
        self.car2 = models.Vehicle(
            user_id=self.user2.id,
            brand="Wuling",
            model="Binguo EV",
            license_plate="B 5678 EV",
            battery_capacity_kwh=31.9,
            current_soc=50.0,
            efficiency_km_kwh=7.5
        )
        self.db.add_all([self.car1, self.car2])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_login_success(self):
        req = schemas.LoginRequest(username="driver1", password="password123")
        user = api_auth.login(req, self.db)
        self.assertEqual(user.username, "driver1")
        self.assertEqual(user.full_name, "Budi Santoso")
        self.assertEqual(user.role, "DRIVER")

    def test_login_wrong_password(self):
        req = schemas.LoginRequest(username="driver1", password="wrongpassword")
        with self.assertRaises(HTTPException) as ctx:
            api_auth.login(req, self.db)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_register_new_driver(self):
        req = schemas.RegisterRequest(
            full_name="Ahmad Dani",
            username="driver3",
            phone="08199887766",
            password="pass1234"
        )
        user = api_auth.register(req, self.db)
        self.assertEqual(user.username, "driver3")
        self.assertEqual(user.wallet_balance, 150000.0)

    def test_register_duplicate_username(self):
        req = schemas.RegisterRequest(
            full_name="Budi Kloning",
            username="driver1",
            phone="0819999999",
            password="password123"
        )
        with self.assertRaises(HTTPException) as ctx:
            api_auth.register(req, self.db)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_user_active_session_empty_and_active(self):
        # When no active session
        empty_res = api_station.get_user_active_session(self.user1.id, self.db)
        self.assertFalse(empty_res["has_active_session"])

        # Create active session for user 1
        active_session = models.ChargingSession(
            session_code="EV-TEST-123456",
            user_id=self.user1.id,
            station_id=self.station.id,
            connector_id=self.c1.id,
            vehicle_id=self.car1.id,
            start_soc=40.0,
            target_soc=100.0,
            current_soc=45.0,
            target_type="FULL",
            target_kwh=43.56,
            energy_delivered_kwh=3.63,
            deposit_paid=50000.0,
            payment_method="WALLET",
            status="CHARGING",
            start_time=datetime.utcnow()
        )
        self.db.add(active_session)
        self.c1.status = "CHARGING"
        self.c1.current_session_id = active_session.id
        self.db.commit()

        # Query user active session again
        active_res = api_station.get_user_active_session(self.user1.id, self.db)
        self.assertTrue(active_res["has_active_session"])
        self.assertEqual(active_res["session_code"], "EV-TEST-123456")
        self.assertEqual(active_res["connector_id"], self.c1.id)
        self.assertIn("energy_delivered_kwh", active_res)
        self.assertEqual(active_res["deposit_paid"], 50000.0)

    def test_multi_session_prevention_for_same_user(self):
        # Create active session on nozzle 1 for user 1
        session1 = models.ChargingSession(
            session_code="EV-TEST-001",
            user_id=self.user1.id,
            station_id=self.station.id,
            connector_id=self.c1.id,
            vehicle_id=self.car1.id,
            start_soc=40.0,
            target_soc=100.0,
            current_soc=42.0,
            target_type="FULL",
            target_kwh=43.56,
            deposit_paid=50000.0,
            payment_method="WALLET",
            status="CHARGING",
            start_time=datetime.utcnow()
        )
        self.db.add(session1)
        self.c1.status = "CHARGING"
        self.db.commit()

        # User 1 tries to start ANOTHER charging session on Nozzle 2
        req = schemas.StartChargingRequest(
            user_id=self.user1.id,
            station_code="CS-SDR-01",
            connector_id=self.c2.id,
            vehicle_id=self.car1.id,
            target_type="FULL",
            manual_kwh=10.0,
            target_soc=100.0,
            payment_method="WALLET"
        )

        import asyncio
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(api_station.start_charging(req, self.db))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("masih memiliki sesi pengisian aktif", ctx.exception.detail)

    def test_zombie_session_auto_cleanup(self):
        # Create a zombie session where connector is AVAILABLE (e.g. server restarted or out of sync)
        init_balance = self.user1.wallet_balance
        zombie = models.ChargingSession(
            session_code="EV-ZOMBIE-001",
            user_id=self.user1.id,
            station_id=self.station.id,
            connector_id=self.c1.id,
            vehicle_id=self.car1.id,
            start_soc=40.0,
            target_soc=100.0,
            current_soc=45.0,
            target_type="FULL",
            target_kwh=43.56,
            energy_delivered_kwh=0.0,
            deposit_paid=50000.0,
            actual_cost=0.0,
            payment_method="WALLET",
            status="CHARGING",
            start_time=datetime.utcnow()
        )
        self.db.add(zombie)
        self.c1.status = "AVAILABLE"  # Connector is NOT charging!
        self.c1.current_session_id = None
        self.db.commit()

        # Query user active session
        res = api_station.get_user_active_session(self.user1.id, self.db)
        # Should automatically detect zombie and return has_active_session = False
        self.assertFalse(res["has_active_session"])

        # Sesi di DB harus menjadi COMPLETED
        updated_session = self.db.query(models.ChargingSession).filter(models.ChargingSession.id == zombie.id).first()
        self.assertEqual(updated_session.status, "COMPLETED")
        self.assertEqual(updated_session.stop_reason, "ORPHANED_CLEANUP")
        # Saldo deposit 50.000 harus di-refund ke user
        self.assertEqual(self.user1.wallet_balance, init_balance + 50000.0)

    def test_emergency_reset(self):
        import asyncio
        # Create a stuck charging session
        stuck = models.ChargingSession(
            session_code="EV-STUCK-001",
            user_id=self.user2.id,
            station_id=self.station.id,
            connector_id=self.c2.id,
            vehicle_id=self.car2.id,
            start_soc=50.0,
            target_soc=100.0,
            current_soc=55.0,
            target_type="FULL",
            target_kwh=15.95,
            deposit_paid=20000.0,
            payment_method="WALLET",
            status="CHARGING",
            start_time=datetime.utcnow()
        )
        self.db.add(stuck)
        self.c2.status = "CHARGING"
        self.c2.current_session_id = stuck.id
        self.db.commit()

        # Trigger emergency reset
        res = asyncio.run(api_station.emergency_reset(self.db))
        self.assertEqual(res["status"], "SUCCESS")

        # Verify all connectors are AVAILABLE
        c1 = self.db.query(models.Connector).filter(models.Connector.id == self.c1.id).first()
        c2 = self.db.query(models.Connector).filter(models.Connector.id == self.c2.id).first()
        self.assertEqual(c1.status, "AVAILABLE")
        self.assertEqual(c2.status, "AVAILABLE")
        self.assertIsNone(c2.current_session_id)

        # Verify stuck session is COMPLETED
        s = self.db.query(models.ChargingSession).filter(models.ChargingSession.id == stuck.id).first()
        self.assertEqual(s.status, "COMPLETED")
        self.assertEqual(s.stop_reason, "EMERGENCY_RESET")

    def test_nozzle_claim_fails_when_cable_not_plugged(self):
        import asyncio
        # c1 is AVAILABLE (not plugged)
        self.assertEqual(self.c1.status, "AVAILABLE")
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(api_station.claim_nozzle(
                self.c1.id,
                schemas.ClaimRequest(user_id=self.user1.id),
                self.db
            ))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Kabel belum dicolokkan", ctx.exception.detail)

    def test_nozzle_claim_exclusivity_between_two_users(self):
        import asyncio
        # Plug c1 so it is CONNECTED
        self.c1.status = "CONNECTED"
        self.db.commit()

        # User 1 claims c1 -> SUCESS
        res1 = asyncio.run(api_station.claim_nozzle(
            self.c1.id,
            schemas.ClaimRequest(user_id=self.user1.id),
            self.db
        ))
        self.assertEqual(res1["status"], "SUCCESS")
        self.assertEqual(self.c1.locked_by_user_id, self.user1.id)

        # User 2 tries to claim c1 -> 409 CONFLICT
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(api_station.claim_nozzle(
                self.c1.id,
                schemas.ClaimRequest(user_id=self.user2.id),
                self.db
            ))
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("sedang digunakan oleh Budi Santoso", ctx.exception.detail)

        # User 1 releases c1
        res_rel = asyncio.run(api_station.release_nozzle(
            self.c1.id,
            schemas.ClaimRequest(user_id=self.user1.id),
            self.db
        ))
        self.assertEqual(res_rel["status"], "SUCCESS")
        self.assertIsNone(self.c1.locked_by_user_id)

        # Now User 2 can claim c1
        res2 = asyncio.run(api_station.claim_nozzle(
            self.c1.id,
            schemas.ClaimRequest(user_id=self.user2.id),
            self.db
        ))
        self.assertEqual(res2["status"], "SUCCESS")
        self.assertEqual(self.c1.locked_by_user_id, self.user2.id)

    def test_user_claiming_second_nozzle_fails_when_first_active(self):
        import asyncio
        from fastapi import HTTPException
        self.c1.status = "CONNECTED"
        self.c2.status = "CONNECTED"
        self.db.commit()

        # User 1 claims c1
        asyncio.run(api_station.claim_nozzle(
            self.c1.id,
            schemas.ClaimRequest(user_id=self.user1.id),
            self.db
        ))
        self.assertEqual(self.c1.locked_by_user_id, self.user1.id)

        # User 1 claims c2 while c1 is active -> 409 CONFLICT!
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(api_station.claim_nozzle(
                self.c2.id,
                schemas.ClaimRequest(user_id=self.user1.id),
                self.db
            ))
        self.assertEqual(cm.exception.status_code, 409)

        # User 1 releases c1
        asyncio.run(api_station.release_nozzle(
            self.c1.id,
            schemas.ClaimRequest(user_id=self.user1.id),
            self.db
        ))

        # Now User 1 can claim c2
        res2 = asyncio.run(api_station.claim_nozzle(
            self.c2.id,
            schemas.ClaimRequest(user_id=self.user1.id),
            self.db
        ))
        self.assertEqual(res2["status"], "SUCCESS")
        self.assertEqual(self.c2.locked_by_user_id, self.user1.id)

    def test_unplug_resets_lock(self):
        self.c1.status = "CONNECTED"
        self.c1.locked_by_user_id = self.user1.id
        self.db.commit()

        from app.services.station_manager import StationManager
        StationManager.unplug_connector(self.db, self.c1.id)
        self.db.refresh(self.c1)
        self.assertEqual(self.c1.status, "AVAILABLE")
        self.assertIsNone(self.c1.locked_by_user_id)

    def test_plug_nozzle_exclusivity_between_two_users(self):
        import asyncio
        self.c1.status = "AVAILABLE"
        self.c1.locked_by_user_id = None
        self.db.commit()

        # User 1 plugs into c1
        res1 = asyncio.run(api_station.plug_nozzle(
            self.c1.id,
            api_station.PlugNozzleRequest(user_id=self.user1.id),
            db=self.db
        ))
        self.assertEqual(res1["status"], "HANDSHAKING")
        self.db.refresh(self.c1)
        self.assertEqual(self.c1.status, "CONNECTED")
        self.assertEqual(self.c1.locked_by_user_id, self.user1.id)

        # User 2 tries to plug into c1 while locked by User 1 -> 409
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(api_station.plug_nozzle(
                self.c1.id,
                api_station.PlugNozzleRequest(user_id=self.user2.id),
                db=self.db
            ))
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("sedang digunakan oleh Budi Santoso", ctx.exception.detail)

        # When c1 is CHARGING, User 2 also rejected -> 409
        self.c1.status = "CHARGING"
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(api_station.plug_nozzle(
                self.c1.id,
                api_station.PlugNozzleRequest(user_id=self.user2.id),
                db=self.db
            ))
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("sedang dalam proses pengisian aktif", ctx.exception.detail)

    def test_same_user_cannot_plug_second_nozzle_while_first_locked(self):
        import asyncio
        self.c1.status = "AVAILABLE"
        self.c1.locked_by_user_id = None
        self.c2.status = "AVAILABLE"
        self.c2.locked_by_user_id = None
        self.db.commit()

        # User 1 plugs c1 -> SUCCESS
        res1 = asyncio.run(api_station.plug_nozzle(
            self.c1.id,
            api_station.PlugNozzleRequest(user_id=self.user1.id),
            db=self.db
        ))
        self.assertEqual(res1["status"], "HANDSHAKING")

        # User 1 tries to plug c2 from another device while c1 is active/locked -> 409 CONFLICT!
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(api_station.plug_nozzle(
                self.c2.id,
                api_station.PlugNozzleRequest(user_id=self.user1.id),
                db=self.db
            ))
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("sedang memilih / menggunakan", ctx.exception.detail)

        # Re-requesting the SAME nozzle c1 by User 1 returns CONNECTED without error
        res_same = asyncio.run(api_station.plug_nozzle(
            self.c1.id,
            api_station.PlugNozzleRequest(user_id=self.user1.id),
            db=self.db
        ))
        self.assertEqual(res_same["status"], "CONNECTED")

    def test_get_station_active_sessions_returns_charging_nozzles(self):
        # Create 2 charging sessions concurrently on c1 and c2
        s1 = models.ChargingSession(
            session_code="EV-TEST-001",
            user_id=self.user1.id,
            station_id=self.station.id,
            connector_id=self.c1.id,
            vehicle_id=self.car1.id,
            start_soc=20.0,
            target_soc=80.0,
            current_soc=45.0,
            target_type="FULL",
            target_kwh=30.0,
            deposit_paid=50000.0,
            payment_method="WALLET",
            status="CHARGING",
            start_time=datetime.utcnow()
        )
        s2 = models.ChargingSession(
            session_code="EV-TEST-002",
            user_id=self.user2.id,
            station_id=self.station.id,
            connector_id=self.c2.id,
            vehicle_id=self.car2.id,
            start_soc=30.0,
            target_soc=90.0,
            current_soc=60.0,
            target_type="FULL",
            target_kwh=40.0,
            deposit_paid=75000.0,
            payment_method="WALLET",
            status="CHARGING",
            start_time=datetime.utcnow()
        )
        self.db.add_all([s1, s2])
        self.c1.status = "CHARGING"
        self.c2.status = "CHARGING"
        self.db.commit()

        sessions = api_station.get_station_active_sessions(self.station.code, db=self.db)
        self.assertEqual(len(sessions), 2)
        sess_codes = [s["session_code"] for s in sessions]
        self.assertIn("EV-TEST-001", sess_codes)
        self.assertIn("EV-TEST-002", sess_codes)
        
        c1_item = next(s for s in sessions if s["session_code"] == "EV-TEST-001")
        self.assertEqual(c1_item["connector_id"], self.c1.id)
        self.assertEqual(c1_item["connector_name"], self.c1.name)

if __name__ == "__main__":
    unittest.main()
