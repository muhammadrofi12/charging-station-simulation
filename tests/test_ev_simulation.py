import unittest
from app.services.charging_engine import ChargingEngine, EV_FLEET_POOL
from app.database import Base, SessionLocal
from app import models
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class TestRealEVSimulation(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = TestingSessionLocal()

        self.user = models.User(username="evdriver", full_name="EV Driver", wallet_balance=250000.0)
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_ev_fleet_pool_integrity(self):
        # Verify 5 cars in fleet pool
        self.assertGreaterEqual(len(EV_FLEET_POOL), 5)
        for ev in EV_FLEET_POOL:
            self.assertIn("brand", ev)
            self.assertIn("model", ev)
            self.assertIn("battery_capacity_kwh", ev)
            self.assertIn("efficiency_km_kwh", ev)
            self.assertIn("architecture_voltage", ev)
            self.assertIn("license_plate", ev)
            self.assertGreater(ev["battery_capacity_kwh"], 20.0)
            self.assertGreater(ev["efficiency_km_kwh"], 5.0)

    def test_auto_detect_ev(self):
        vehicle = ChargingEngine.auto_detect_ev(self.db, self.user.id)
        self.assertIsNotNone(vehicle)
        self.assertIn(vehicle.brand, ["Hyundai", "Wuling", "BYD", "Tesla", "Chery"])
        self.assertGreaterEqual(vehicle.battery_capacity_kwh, 31.9)
        self.assertGreater(vehicle.current_soc, 0.0)
        self.assertLessEqual(vehicle.current_soc, 100.0)
        self.assertIsNotNone(vehicle.license_plate)
        self.assertGreaterEqual(vehicle.architecture_voltage, 400.0)

    def test_calculate_layman_metrics(self):
        # 15 kWh delivered at 50 kW on Ioniq 5 (6.6 km/kWh), cost Rp 45.000, target 50 kWh
        metrics = ChargingEngine.calculate_layman_metrics(
            energy_kwh=15.0,
            power_kw=50.0,
            efficiency_km_kwh=6.6,
            actual_cost=45000.0,
            current_soc=45.0,
            target_soc=80.0,
            target_kwh=50.0
        )
        # km_added = 15.0 * 6.6 = 99.0 km
        self.assertEqual(metrics["km_added"], 99.0)
        # charging_speed_km_per_min = (50.0 * 6.6) / 60 = 5.5 km/min
        self.assertEqual(metrics["km_per_min"], 5.5)
        # petrol_liters = 99.0 / 12 = 8.25 L
        self.assertEqual(metrics["petrol_liters_equiv"], 8.25)
        # petrol_cost = 8.25 * 13700 = 113025.0
        self.assertEqual(metrics["petrol_cost_equiv"], 113025.0)
        # money_saved = 113025 - 45000 = 68025.0
        self.assertEqual(metrics["money_saved"], 68025.0)
        self.assertGreaterEqual(metrics["percent_saved"], 50.0)
        self.assertFalse(metrics["is_tapering"])

    def test_tapering_detection_above_80_soc(self):
        metrics_taper = ChargingEngine.calculate_layman_metrics(
            energy_kwh=40.0,
            power_kw=20.0,
            efficiency_km_kwh=6.6,
            actual_cost=120000.0,
            current_soc=85.0,
            target_soc=100.0,
            target_kwh=50.0
        )
        self.assertTrue(metrics_taper["is_tapering"])
        self.assertIn("Kecepatan cas melambat di atas 80%", metrics_taper["taper_explanation"])

if __name__ == "__main__":
    unittest.main()
