import asyncio
import random
from datetime import datetime
from typing import Dict, Any, Callable, List, Optional
from ..database import SessionLocal
from .. import models
from .billing_service import BillingService
from .station_manager import StationManager

# Real Electric Vehicle Fleet Pool for Auto-Detection (ISO 15118 Plug & Charge)
EV_FLEET_POOL = [
    {
        "brand": "Hyundai",
        "model": "Ioniq 5 Long Range",
        "battery_capacity_kwh": 72.6,
        "max_ac_kw": 11.0,
        "max_dc_kw": 220.0,
        "efficiency_km_kwh": 6.6,
        "architecture_voltage": 800.0,
        "license_plate": "B 1888 ION",
        "min_start_soc": 20.0,
        "max_start_soc": 38.0,
        "description": "E-GMP 800V Ultra-Fast Architecture • Jangkauan 481 km"
    },
    {
        "brand": "Wuling",
        "model": "Binguo EV Max",
        "battery_capacity_kwh": 31.9,
        "max_ac_kw": 7.0,
        "max_dc_kw": 50.0,
        "efficiency_km_kwh": 10.4,
        "architecture_voltage": 400.0,
        "license_plate": "B 2468 WLG",
        "min_start_soc": 25.0,
        "max_start_soc": 48.0,
        "description": "City EV Ultra Hemat Energi • Jangkauan 333 km"
    },
    {
        "brand": "BYD",
        "model": "Seal Performance",
        "battery_capacity_kwh": 82.5,
        "max_ac_kw": 11.0,
        "max_dc_kw": 150.0,
        "efficiency_km_kwh": 6.9,
        "architecture_voltage": 550.0,
        "license_plate": "B 8888 BYD",
        "min_start_soc": 18.0,
        "max_start_soc": 35.0,
        "description": "Blade Battery LFP High Performance • Jangkauan 570 km"
    },
    {
        "brand": "Tesla",
        "model": "Model 3 Long Range",
        "battery_capacity_kwh": 60.0,
        "max_ac_kw": 11.0,
        "max_dc_kw": 170.0,
        "efficiency_km_kwh": 7.5,
        "architecture_voltage": 400.0,
        "license_plate": "B 1010 TS",
        "min_start_soc": 22.0,
        "max_start_soc": 42.0,
        "description": "Aerodynamic Sedan High Efficiency • Jangkauan 450 km"
    },
    {
        "brand": "Chery",
        "model": "Omoda E5",
        "battery_capacity_kwh": 61.0,
        "max_ac_kw": 9.9,
        "max_dc_kw": 80.0,
        "efficiency_km_kwh": 7.0,
        "architecture_voltage": 400.0,
        "license_plate": "B 1771 OMD",
        "min_start_soc": 24.0,
        "max_start_soc": 46.0,
        "description": "Crossover EV Modern LFP Battery • Jangkauan 430 km"
    }
]

class ChargingEngine:
    _instance = None
    _active_sessions: Dict[int, bool] = {}
    _ws_listeners: List[Callable[[Dict[str, Any]], Any]] = []
    _active_handshakes: Dict[int, bool] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ChargingEngine, cls).__new__(cls)
        return cls._instance

    @classmethod
    def register_listener(cls, callback: Callable[[Dict[str, Any]], Any]):
        if callback not in cls._ws_listeners:
            cls._ws_listeners.append(callback)

    @classmethod
    def unregister_listener(cls, callback: Callable[[Dict[str, Any]], Any]):
        if callback in cls._ws_listeners:
            cls._ws_listeners.remove(callback)

    @classmethod
    async def broadcast(cls, message: Dict[str, Any]):
        for listener in list(cls._ws_listeners):
            try:
                await listener(message)
            except Exception:
                pass

    @classmethod
    def is_session_active(cls, session_id: int) -> bool:
        return cls._active_sessions.get(session_id, False)

    @classmethod
    def request_stop(cls, session_id: int):
        if session_id in cls._active_sessions:
            cls._active_sessions[session_id] = False

    @staticmethod
    def calculate_layman_metrics(
        energy_kwh: float,
        power_kw: float,
        efficiency_km_kwh: float,
        actual_cost: float,
        current_soc: float,
        target_soc: float,
        target_kwh: float
    ) -> Dict[str, Any]:
        """
        Translates raw electrical measurements into layman terms for non-technical stakeholders.
        - km_added: Driving range gained
        - charging_speed_km_per_min: Real-time charging velocity in distance/minute
        - petrol_liters_equiv: Equivalent petrol needed for this distance (1L = 12km)
        - petrol_cost_equiv: Equivalent cost if buying Pertamax (Rp 13.700/L)
        - money_saved: Rupiah saved vs petrol
        - percent_saved: % savings vs petrol
        - eta_minutes: Estimated minutes remaining
        - is_tapering: Boolean whether CC-CV power reduction is active above 80% SoC
        """
        km_added = round(energy_kwh * efficiency_km_kwh, 1)
        km_per_min = round((power_kw * efficiency_km_kwh) / 60.0, 1) if power_kw > 0 else 0.0

        # Equivalent petrol calculation (Standard Indonesian ICE car: 1 Liter Pertamax = 12 KM)
        petrol_liters = round(km_added / 12.0, 2)
        petrol_cost = round(petrol_liters * 13700.0, 0)
        money_saved = max(0.0, petrol_cost - actual_cost)
        percent_saved = round((money_saved / petrol_cost * 100.0), 0) if petrol_cost > 0 else 60.0

        # ETA calculation
        remaining_kwh = max(0.0, target_kwh - energy_kwh)
        eta_minutes = round((remaining_kwh / max(power_kw, 1.0)) * 60.0, 0) if remaining_kwh > 0 and power_kw > 0 else 0.0

        # Tapering curve detection
        is_tapering = current_soc >= 80.0
        taper_explanation = (
            "💡 Kecepatan cas melambat di atas 80% untuk melindungi suhu sel kimia baterai mobil agar awet (Battery Health Protection)."
            if is_tapering else ""
        )

        return {
            "km_added": km_added,
            "km_per_min": km_per_min,
            "petrol_liters_equiv": petrol_liters,
            "petrol_cost_equiv": petrol_cost,
            "money_saved": money_saved,
            "percent_saved": percent_saved,
            "eta_minutes": max(0.0, eta_minutes),
            "is_tapering": is_tapering,
            "taper_explanation": taper_explanation
        }

    @classmethod
    def auto_detect_ev(cls, db, user_id: Optional[int] = None) -> models.Vehicle:
        """
        Randomly picks a realistic EV from the fleet pool and updates the user's active vehicle.
        Simulates Plug & Charge (ISO 15118) vehicle identification.
        """
        picked_spec = random.choice(EV_FLEET_POOL)
        initial_soc = round(random.uniform(picked_spec["min_start_soc"], picked_spec["max_start_soc"]), 1)

        target_user_id = user_id or 1
        vehicle = db.query(models.Vehicle).filter(models.Vehicle.user_id == target_user_id).first()

        if not vehicle:
            vehicle = models.Vehicle(user_id=target_user_id)
            db.add(vehicle)

        vehicle.brand = picked_spec["brand"]
        vehicle.model = picked_spec["model"]
        vehicle.battery_capacity_kwh = picked_spec["battery_capacity_kwh"]
        vehicle.max_ac_kw = picked_spec["max_ac_kw"]
        vehicle.max_dc_kw = picked_spec["max_dc_kw"]
        vehicle.current_soc = initial_soc
        vehicle.license_plate = picked_spec["license_plate"]
        vehicle.efficiency_km_kwh = picked_spec["efficiency_km_kwh"]
        vehicle.architecture_voltage = picked_spec["architecture_voltage"]

        db.commit()
        db.refresh(vehicle)
        return vehicle

    @classmethod
    async def run_handshake(cls, connector_id: int, user_id: Optional[int] = None):
        """
        Executes realistic SPKLU handshake protocol stages with delays and broadcasts updates.
        1. Mechanical locking (1.2s)
        2. BMS communication handshake (1.5s)
        3. Vehicle identification (1.2s)
        4. High-voltage insulation & safety test (1.2s)
        5. Ready for charge!
        """
        cls._active_handshakes[connector_id] = True
        db = SessionLocal()

        try:
            connector = db.query(models.Connector).filter(models.Connector.id == connector_id).first()
            if not connector:
                return

            # Stage 1: Mechanical Locking (Safety Interlock)
            await cls.broadcast({
                "event": "HANDSHAKE_STAGE",
                "stage": "LOCKING",
                "step": 1,
                "total_steps": 4,
                "title": "Penguncian Konektor (Safety Interlock)",
                "message": f"🔒 Mengunci konektor {connector.name} secara mekanikal ke port kendaraan...",
                "connector_id": connector_id,
                "connector_name": connector.name,
                "user_id": user_id
            })
            await asyncio.sleep(1.2)

            # Stage 2: BMS CAN-Bus Data Synchronization
            await cls.broadcast({
                "event": "HANDSHAKE_STAGE",
                "stage": "BMS_SYNC",
                "step": 2,
                "total_steps": 4,
                "title": "Sinkronisasi BMS (Battery Management)",
                "message": "📡 Sinkronisasi data voltase, suhu, dan parameter baterai (ISO 15118)...",
                "connector_id": connector_id,
                "connector_name": connector.name,
                "user_id": user_id
            })
            await asyncio.sleep(1.5)

            # Stage 3: Auto-Detect Real EV from Fleet
            detected_vehicle = cls.auto_detect_ev(db, user_id)
            vehicle_data = {
                "id": detected_vehicle.id,
                "brand": detected_vehicle.brand,
                "model": detected_vehicle.model,
                "battery_capacity_kwh": detected_vehicle.battery_capacity_kwh,
                "current_soc": detected_vehicle.current_soc,
                "license_plate": detected_vehicle.license_plate,
                "efficiency_km_kwh": detected_vehicle.efficiency_km_kwh or 6.8,
                "architecture_voltage": detected_vehicle.architecture_voltage or 400.0,
                "max_ac_kw": detected_vehicle.max_ac_kw,
                "max_dc_kw": detected_vehicle.max_dc_kw
            }

            await cls.broadcast({
                "event": "HANDSHAKE_STAGE",
                "stage": "VEHICLE_IDENTIFIED",
                "step": 3,
                "total_steps": 4,
                "title": "Verifikasi Identitas & Tipe Kendaraan",
                "message": f"🚗 Terverifikasi: {detected_vehicle.brand} {detected_vehicle.model} ({detected_vehicle.license_plate}) • Baterai: {detected_vehicle.battery_capacity_kwh} kWh (SoC {detected_vehicle.current_soc}%)",
                "connector_id": connector_id,
                "connector_name": connector.name,
                "vehicle": vehicle_data,
                "user_id": user_id
            })
            await asyncio.sleep(1.2)

            # Stage 4: High-Voltage Insulation Test
            voltage_str = f"{detected_vehicle.architecture_voltage:.0f}V" if detected_vehicle.architecture_voltage else "400V"
            await cls.broadcast({
                "event": "HANDSHAKE_STAGE",
                "stage": "INSULATION_TEST",
                "step": 4,
                "total_steps": 4,
                "title": "Uji Isolasi & Keamanan Listrik",
                "message": f"⚡ Pengujian resistansi isolasi ({voltage_str}) aman • Relay daya siap diaktifkan!",
                "connector_id": connector_id,
                "connector_name": connector.name,
                "voltage": detected_vehicle.architecture_voltage or 400.0,
                "user_id": user_id
            })
            await asyncio.sleep(1.0)

            # Stage 5: Handshake Complete -> Connected
            connector.status = "CONNECTED"
            if user_id:
                connector.locked_by_user_id = user_id
            db.commit()
            db.refresh(connector)

            await cls.broadcast({
                "event": "HANDSHAKE_COMPLETE",
                "connector_id": connector.id,
                "connector_name": connector.name,
                "status": "CONNECTED",
                "vehicle": vehicle_data,
                "user_id": user_id,
                "message": f"✅ Verifikasi sistem selesai. {detected_vehicle.brand} {detected_vehicle.model} siap menerima pengisian daya."
            })

            await cls.broadcast({
                "event": "PORT_NOZZLE_CONNECTED",
                "connector_id": connector.id,
                "connector_name": connector.name,
                "status": "CONNECTED",
                "vehicle": vehicle_data,
                "user_id": user_id,
                "message": f"✅ {connector.name} siap mengalirkan listrik! Silakan pilih target pengisian."
            })

            await cls.broadcast({
                "event": "NOZZLE_PLUGGED",
                "station_id": connector.station_id,
                "connector_id": connector.id,
                "connector_name": connector.name,
                "status": "CONNECTED",
                "vehicle": vehicle_data,
                "user_id": user_id
            })

        finally:
            cls._active_handshakes.pop(connector_id, None)
            db.close()

    @classmethod
    async def sync_battery_soc(cls, session_id: int, new_soc: float):
        """
        External sync from slider or ADB.
        """
        db = SessionLocal()
        try:
            session = db.query(models.ChargingSession).filter(models.ChargingSession.id == session_id).first()
            if not session or session.status != "CHARGING":
                return

            new_soc = min(100.0, max(session.start_soc, round(new_soc, 1)))
            session.current_soc = new_soc

            vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == session.vehicle_id).first()
            cap = vehicle.battery_capacity_kwh if vehicle else 72.6
            efficiency = vehicle.efficiency_km_kwh if (vehicle and vehicle.efficiency_km_kwh) else 6.8
            arch_voltage = vehicle.architecture_voltage if (vehicle and vehicle.architecture_voltage) else 400.0

            if vehicle:
                vehicle.current_soc = session.current_soc

            added_soc = max(0.0, session.current_soc - session.start_soc)
            energy_from_soc = round((added_soc / 100.0) * cap, 3)
            if energy_from_soc > session.energy_delivered_kwh:
                session.energy_delivered_kwh = energy_from_soc

            connector = db.query(models.Connector).filter(models.Connector.id == session.connector_id).first()
            tariff = connector.tariff_per_kwh if connector else 2466.0
            deposit = session.deposit_paid
            current_cost = min(deposit, round(session.energy_delivered_kwh * tariff, 0))
            remaining_deposit = max(0.0, deposit - current_cost)

            # Layman calculation
            layman = cls.calculate_layman_metrics(
                energy_kwh=session.energy_delivered_kwh,
                power_kw=session.current_power_kw,
                efficiency_km_kwh=efficiency,
                actual_cost=current_cost,
                current_soc=session.current_soc,
                target_soc=session.target_soc,
                target_kwh=session.target_kwh
            )

            db.commit()

            await cls.broadcast({
                "event": "TELEMETRY_UPDATE",
                "station_id": session.station_id,
                "connector_id": session.connector_id,
                "session_id": session.id,
                "session_code": session.session_code,
                "current_soc": session.current_soc,
                "target_soc": session.target_soc,
                "energy_delivered_kwh": session.energy_delivered_kwh,
                "current_power_kw": session.current_power_kw,
                "current_power_w": round(session.current_power_kw * 1000.0, 1),
                "voltage": round(arch_voltage, 1),
                "current_amps": round((session.current_power_kw * 1000.0) / arch_voltage, 1) if arch_voltage > 0 else 0.0,
                "temperature": 32.5,
                "current_cost": current_cost,
                "remaining_deposit": remaining_deposit,
                "target_kwh": session.target_kwh,
                "car_brand": vehicle.brand if vehicle else "EV",
                "car_model": vehicle.model if vehicle else "Electric Vehicle",
                "car_plate": vehicle.license_plate if vehicle else "B 1234 EV",
                **layman
            })

            if session.target_type == "FULL" and session.current_soc >= session.target_soc:
                cls.request_stop(session_id)
        finally:
            db.close()

    @classmethod
    async def run_simulation_loop(cls, session_id: int):
        cls._active_sessions[session_id] = True
        db = SessionLocal()

        try:
            session = db.query(models.ChargingSession).filter(models.ChargingSession.id == session_id).first()
            if not session:
                return

            connector = db.query(models.Connector).filter(models.Connector.id == session.connector_id).first()
            vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == session.vehicle_id).first()

            if not connector or not vehicle:
                return

            battery_cap = vehicle.battery_capacity_kwh or 72.6
            efficiency = vehicle.efficiency_km_kwh or 6.8
            arch_voltage = vehicle.architecture_voltage or 400.0
            tariff = connector.tariff_per_kwh
            deposit = session.deposit_paid

            # Max power negotiation between Station Nozzle and Vehicle BMS
            if connector.type_category == "AC":
                base_kw = min(connector.max_power_kw, vehicle.max_ac_kw or 11.0)
            else:
                base_kw = min(connector.max_power_kw, vehicle.max_dc_kw or 150.0)

            if base_kw <= 0:
                base_kw = 22.0

            # Dynamic demonstration charging pace:
            # Delivers ~0.10 - 0.20 kWh per second tick so progress moves smoothly and dynamically during presentation
            kwh_rate_per_sec = (base_kw / 150.0) * 0.12 + 0.06

            # Broadcast session started
            await cls.broadcast({
                "event": "SESSION_STARTED",
                "station_id": session.station_id,
                "connector_id": session.connector_id,
                "session_id": session.id,
                "session_code": session.session_code,
                "payment_method": session.payment_method,
                "deposit_paid": deposit,
                "start_soc": session.start_soc,
                "target_soc": session.target_soc,
                "max_power_kw": base_kw,
                "car_brand": vehicle.brand,
                "car_model": vehicle.model,
                "car_plate": vehicle.license_plate,
                "battery_capacity_kwh": battery_cap
            })

            stop_reason = "USER_STOP"

            while cls._active_sessions.get(session_id, False):
                await asyncio.sleep(1.0)

                if not cls._active_sessions.get(session_id, False):
                    stop_reason = "USER_STOP"
                    break

                db.refresh(session)
                current_soc = session.current_soc

                # Real EV Tapering Curve: power ramps down above 80% SoC to protect cell chemistry
                if current_soc >= 80.0:
                    taper_factor = max(0.20, (100.0 - current_soc) / 20.0)
                    actual_kw = max(4.0, round(base_kw * taper_factor + random.uniform(-0.5, 0.5), 1))
                    kwh_step = kwh_rate_per_sec * taper_factor
                else:
                    actual_kw = max(5.0, round(base_kw + random.uniform(-0.8, 0.8), 1))
                    kwh_step = kwh_rate_per_sec

                session.energy_delivered_kwh = round(session.energy_delivered_kwh + kwh_step, 3)
                session.current_power_kw = actual_kw

                added_soc = (session.energy_delivered_kwh / battery_cap) * 100.0
                session.current_soc = min(100.0, round(session.start_soc + added_soc, 1))
                vehicle.current_soc = session.current_soc

                # Voltage & Amps based on vehicle architecture
                voltage = arch_voltage + random.uniform(-3.5, 3.5)
                current_amps = round((actual_kw * 1000.0) / voltage, 1)

                current_cost = min(deposit, round(session.energy_delivered_kwh * tariff, 0))
                remaining_deposit = max(0.0, deposit - current_cost)

                # Layman telemetry translation
                layman = cls.calculate_layman_metrics(
                    energy_kwh=session.energy_delivered_kwh,
                    power_kw=session.current_power_kw,
                    efficiency_km_kwh=efficiency,
                    actual_cost=current_cost,
                    current_soc=session.current_soc,
                    target_soc=session.target_soc,
                    target_kwh=session.target_kwh
                )

                db.commit()

                # Live Broadcast
                await cls.broadcast({
                    "event": "TELEMETRY_UPDATE",
                    "station_id": session.station_id,
                    "connector_id": session.connector_id,
                    "session_id": session.id,
                    "session_code": session.session_code,
                    "current_soc": session.current_soc,
                    "target_soc": session.target_soc,
                    "energy_delivered_kwh": session.energy_delivered_kwh,
                    "current_power_kw": session.current_power_kw,
                    "current_power_w": round(session.current_power_kw * 1000.0, 1),
                    "voltage": round(voltage, 1),
                    "current_amps": current_amps,
                    "temperature": round(31.5 + (session.energy_delivered_kwh * 0.4), 1),
                    "current_cost": current_cost,
                    "remaining_deposit": remaining_deposit,
                    "target_kwh": session.target_kwh,
                    "car_brand": vehicle.brand,
                    "car_model": vehicle.model,
                    "car_plate": vehicle.license_plate,
                    "battery_capacity_kwh": battery_cap,
                    **layman
                })

                # Check auto-cutoff conditions
                if session.target_type == "FULL" and session.current_soc >= session.target_soc and session.energy_delivered_kwh > 0:
                    stop_reason = "FULL_TARGET_REACHED"
                    break
                elif session.target_type in ("MANUAL_KWH", "MANUAL_MAH") and session.energy_delivered_kwh >= session.target_kwh:
                    stop_reason = "MANUAL_TARGET_REACHED"
                    break
                elif current_cost >= deposit and session.energy_delivered_kwh > 0:
                    stop_reason = "DEPOSIT_LIMIT_REACHED"
                    break

            # Settle session
            db.refresh(session)
            if session.status == "CHARGING":
                session.status = "COMPLETED"
                session.stop_reason = stop_reason
                connector.status = "AVAILABLE"
                connector.current_session_id = None
                connector.locked_by_user_id = None
                StationManager.simulated_plugged_ids.discard(session.connector_id)

                actual_cost, refund_amount = BillingService.settle_and_refund(db, session)
                db.commit()

                final_layman = cls.calculate_layman_metrics(
                    energy_kwh=session.energy_delivered_kwh,
                    power_kw=0.0,
                    efficiency_km_kwh=efficiency,
                    actual_cost=actual_cost,
                    current_soc=session.current_soc,
                    target_soc=session.target_soc,
                    target_kwh=session.target_kwh
                )

                await cls.broadcast({
                    "event": "SESSION_COMPLETED",
                    "station_id": session.station_id,
                    "connector_id": session.connector_id,
                    "session_id": session.id,
                    "session_code": session.session_code,
                    "stop_reason": stop_reason,
                    "final_soc": session.current_soc,
                    "total_energy_kwh": session.energy_delivered_kwh,
                    "deposit_paid": deposit,
                    "actual_cost": actual_cost,
                    "refund_amount": refund_amount,
                    "payment_method": session.payment_method,
                    "car_brand": vehicle.brand,
                    "car_model": vehicle.model,
                    "car_plate": vehicle.license_plate,
                    **final_layman
                })

                await cls.broadcast({
                    "event": "NOZZLE_RELEASED",
                    "station_id": session.station_id,
                    "connector_id": session.connector_id,
                    "connector_name": connector.name
                })

        except Exception:
            try:
                db.refresh(session)
                if session.status == "CHARGING":
                    session.status = "COMPLETED"
                    session.stop_reason = "SYSTEM_ERROR"
                    connector.status = "AVAILABLE"
                    connector.current_session_id = None
                    connector.locked_by_user_id = None
                    StationManager.simulated_plugged_ids.discard(session.connector_id)
                    BillingService.settle_and_refund(db, session)
                    db.commit()
                    await cls.broadcast({
                        "event": "NOZZLE_RELEASED",
                        "station_id": session.station_id,
                        "connector_id": session.connector_id,
                        "connector_name": connector.name
                    })
            except Exception:
                pass
        finally:
            cls._active_sessions.pop(session_id, None)
            db.close()
