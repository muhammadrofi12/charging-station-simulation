import unittest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app import models
from app.services.billing_service import BillingService

class TestBillingAndRefund(unittest.TestCase):
    def setUp(self):
        # In-memory SQLite for testing
        self.engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = TestingSessionLocal()

        # Create test User
        self.user = models.User(username="testdriver", full_name="Tester", wallet_balance=100000.0)
        self.db.add(self.user)

        # Create test Vehicle (Ioniq 5, 72.6 kWh, 30% SoC)
        self.vehicle = models.Vehicle(
            user_id=1,
            brand="Hyundai",
            model="Ioniq 5",
            battery_capacity_kwh=72.6,
            max_ac_kw=11.0,
            max_dc_kw=220.0,
            current_soc=30.0
        )
        self.db.add(self.vehicle)

        # Create Station & Connectors
        self.station = models.Station(code="TEST-STATION", name="Test Hub", location="Jakarta")
        self.db.add(self.station)
        self.db.commit()

        self.conn_ac = models.Connector(
            station_id=self.station.id,
            connector_number=1,
            name="AC 7.4 kW",
            type_category="AC",
            connector_type="Type 2",
            max_power_kw=7.4,
            tariff_per_kwh=2466.0,
            status="AVAILABLE"
        )
        self.conn_dc = models.Connector(
            station_id=self.station.id,
            connector_number=2,
            name="DC 50 kW",
            type_category="DC",
            connector_type="CCS2",
            max_power_kw=50.0,
            tariff_per_kwh=3000.0,
            status="AVAILABLE"
        )
        self.db.add_all([self.conn_ac, self.conn_dc])

        # Create RFID Cards
        self.card_sufficient = models.RFIDCard(
            user_id=self.user.id,
            card_uid="CARD-OK-100",
            card_name="Kartu Cukup",
            balance=100000.0
        )
        self.card_low = models.RFIDCard(
            user_id=self.user.id,
            card_uid="CARD-LOW-20",
            card_name="Kartu Minim",
            balance=20000.0
        )
        self.db.add_all([self.card_sufficient, self.card_low])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_estimate_calculation(self):
        # Target FULL from 30% to 100% on 72.6 kWh car:
        # Needed: 72.6 * 0.70 = 50.82 kWh
        # Tariff: 3000 -> Cost = 50.82 * 3000 = ~152460
        est = BillingService.calculate_estimate(
            vehicle=self.vehicle,
            connector=self.conn_dc,
            target_type="FULL"
        )
        self.assertEqual(est.current_soc, 30.0)
        self.assertEqual(est.target_soc, 100.0)
        self.assertAlmostEqual(est.energy_needed_kwh, 50.82, places=1)
        self.assertAlmostEqual(est.estimated_cost, 152460.0, places=0)

    def test_manual_kwh_estimate(self):
        est = BillingService.calculate_estimate(
            vehicle=self.vehicle,
            connector=self.conn_ac,
            target_type="MANUAL_KWH",
            manual_kwh=10.0
        )
        self.assertEqual(est.energy_needed_kwh, 10.0)
        self.assertAlmostEqual(est.estimated_cost, 24660.0, places=0)

    def test_emoney_payment_sufficient(self):
        # Deposit Rp 50.000 from card with Rp 100.000
        BillingService.process_payment(
            db=self.db,
            user=self.user,
            deposit_amount=50000.0,
            payment_method="EMONEY",
            card_uid="CARD-OK-100"
        )
        self.assertEqual(self.card_sufficient.balance, 50000.0)

    def test_emoney_payment_insufficient_raises_error(self):
        # Deposit Rp 50.000 from card with only Rp 20.000
        with self.assertRaises(Exception):
            BillingService.process_payment(
                db=self.db,
                user=self.user,
                deposit_amount=50000.0,
                payment_method="EMONEY",
                card_uid="CARD-LOW-20"
            )

    def test_refund_on_mid_session_stop(self):
        # Deposit Rp 100.000 paid via WALLET
        initial_balance = self.user.wallet_balance  # 100.000
        BillingService.process_payment(
            db=self.db,
            user=self.user,
            deposit_amount=100000.0,
            payment_method="WALLET"
        )
        self.assertEqual(self.user.wallet_balance, 0.0)

        # Create session where only 10 kWh was delivered at Rp 3.000/kWh (Actual cost = Rp 30.000)
        session = models.ChargingSession(
            session_code="TEST-SESS-01",
            user_id=self.user.id,
            station_id=self.station.id,
            connector_id=self.conn_dc.id,
            vehicle_id=self.vehicle.id,
            start_soc=30.0,
            target_soc=100.0,
            current_soc=43.8,
            target_type="FULL",
            target_kwh=50.82,
            energy_delivered_kwh=10.0,
            deposit_paid=100000.0,
            payment_method="WALLET",
            status="CHARGING"
        )
        self.db.add(session)
        self.db.commit()

        # Settle and refund
        actual_cost, refund = BillingService.settle_and_refund(self.db, session)

        # Expected:
        # Actual cost = 10 * 3000 = 30.000
        # Refund = 100.000 - 30.000 = 70.000
        self.assertEqual(actual_cost, 30000.0)
        self.assertEqual(refund, 70000.0)
        self.assertEqual(self.user.wallet_balance, 70000.0)

    def test_wuling_binguo_battery_estimation_and_settlement(self):
        # Create Wuling Binguo EV: 31.9 kWh battery, current SoC 40%
        binguo_vehicle = models.Vehicle(
            user_id=self.user.id,
            brand="Wuling",
            model="Binguo EV",
            battery_capacity_kwh=31.9,
            max_ac_kw=7.0,
            max_dc_kw=50.0,
            current_soc=40.0
        )
        self.db.add(binguo_vehicle)
        self.db.commit()

        # Estimate full charge (from 40% to 100% = 60% of 31.9 kWh = 19.14 kWh)
        estimate = BillingService.calculate_estimate(
            vehicle=binguo_vehicle,
            connector=self.conn_ac,
            target_type="FULL"
        )
        self.assertEqual(estimate.current_soc, 40.0)
        self.assertEqual(estimate.target_soc, 100.0)
        self.assertAlmostEqual(estimate.energy_needed_kwh, 19.14, places=2)
        # Estimated cost: 19.14 * 2466 = 47199.24 -> 47199.0
        self.assertAlmostEqual(estimate.estimated_cost, 47199.0, places=0)

        # Deposit paid Rp 47.200
        self.user.wallet_balance = 100000.0
        BillingService.process_payment(
            db=self.db,
            user=self.user,
            deposit_amount=estimate.estimated_cost,
            payment_method="WALLET"
        )
        self.assertEqual(self.user.wallet_balance, 100000.0 - estimate.estimated_cost)

        # Delivered energy: 10.0 kWh at Rp 2.466 = Rp 24.660
        session = models.ChargingSession(
            session_code="BINGUO-SESS-01",
            user_id=self.user.id,
            station_id=self.station.id,
            connector_id=self.conn_ac.id,
            vehicle_id=binguo_vehicle.id,
            start_soc=40.0,
            target_soc=100.0,
            current_soc=71.3,
            target_type="FULL",
            target_kwh=19.14,
            energy_delivered_kwh=10.0,
            deposit_paid=estimate.estimated_cost,
            payment_method="WALLET",
            status="CHARGING"
        )
        self.db.add(session)
        self.db.commit()

        actual_cost, refund = BillingService.settle_and_refund(self.db, session)
        self.assertEqual(actual_cost, 24660.0)
        self.assertEqual(refund, estimate.estimated_cost - 24660.0)
        self.assertEqual(self.user.wallet_balance, 100000.0 - 24660.0)

    def test_byd_seal_custom_soc_estimate(self):
        # BYD Seal: 82.5 kWh battery, current SoC 20%
        seal_vehicle = models.Vehicle(
            user_id=self.user.id,
            brand="BYD",
            model="Seal Performance",
            battery_capacity_kwh=82.5,
            max_ac_kw=11.0,
            max_dc_kw=150.0,
            current_soc=20.0
        )
        self.db.add(seal_vehicle)
        self.db.commit()

        # Request custom target 80% SoC (Battery preservation mode)
        # Needed: 60% of 82.5 = 49.5 kWh
        est = BillingService.calculate_estimate(
            vehicle=seal_vehicle,
            connector=self.conn_dc,
            target_type="CUSTOM_SOC",
            custom_target_soc=80.0
        )
        self.assertEqual(est.current_soc, 20.0)
        self.assertEqual(est.target_soc, 80.0)
        self.assertAlmostEqual(est.energy_needed_kwh, 49.5, places=1)
        # Cost: 49.5 * 3000 = 148500
        self.assertAlmostEqual(est.estimated_cost, 148500.0, places=0)

    def test_legacy_manual_mah_compatibility_fallback(self):
        # Even if legacy client passes manual_mah, it should fall back cleanly
        est = BillingService.calculate_estimate(
            vehicle=self.vehicle,
            connector=self.conn_ac,
            target_type="MANUAL_MAH",
            manual_mah=25000.0
        )
        self.assertGreater(est.energy_needed_kwh, 0.0)
        self.assertGreater(est.estimated_cost, 0.0)

if __name__ == "__main__":
    unittest.main()
