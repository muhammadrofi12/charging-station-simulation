import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .core.config import STATIC_DIR, TEMPLATES_DIR, STATION_CODE
from .core.exceptions import AppError
from .database import engine, Base, SessionLocal, migrate_db
from . import models
from .routers import api_auth, api_station, ws_charging
from .routers.ws_charging import setup_ws_broadcaster
from .services.adb_battery import ADBBatteryMonitor

def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

def seed_initial_data():
    """Seeds initial station, connectors, and driver accounts idempotently."""
    db = SessionLocal()
    try:
        # Check if station exists
        station = db.query(models.Station).filter(models.Station.code == STATION_CODE).first()
        if not station:
            station = models.Station(
                code=STATION_CODE,
                name="SPKLU Sudirman Central Hub",
                location="Jl. Jend. Sudirman Kav 52, SCBD, Jakarta",
                latitude=-6.2238,
                longitude=106.8088,
                status="AVAILABLE"
            )
            db.add(station)
            db.commit()
            db.refresh(station)

        # Ensure exactly 3 standard connectors (AC, DC CHAdeMO, DC CCS2)
        c1 = db.query(models.Connector).filter(
            models.Connector.station_id == station.id,
            models.Connector.connector_number == 1
        ).first()
        if not c1:
            c1 = models.Connector(station_id=station.id, connector_number=1)
            db.add(c1)
        c1.name = "Nozzle 1 - AC (Type 2)"
        c1.type_category = "AC"
        c1.connector_type = "Type 2"
        c1.max_power_kw = 22.0
        c1.tariff_per_kwh = 2466.0
        c1.status = "AVAILABLE"

        c2 = db.query(models.Connector).filter(
            models.Connector.station_id == station.id,
            models.Connector.connector_number == 2
        ).first()
        if not c2:
            c2 = models.Connector(station_id=station.id, connector_number=2)
            db.add(c2)
        c2.name = "Nozzle 2 - DC (CHAdeMO)"
        c2.type_category = "DC"
        c2.connector_type = "CHAdeMO"
        c2.max_power_kw = 50.0
        c2.tariff_per_kwh = 3000.0
        c2.status = "AVAILABLE"

        c3 = db.query(models.Connector).filter(
            models.Connector.station_id == station.id,
            models.Connector.connector_number == 3
        ).first()
        if not c3:
            c3 = models.Connector(station_id=station.id, connector_number=3)
            db.add(c3)
        c3.name = "Nozzle 3 - CCS (CCS2)"
        c3.type_category = "DC"
        c3.connector_type = "CCS2"
        c3.max_power_kw = 150.0
        c3.tariff_per_kwh = 3500.0
        c3.status = "AVAILABLE"

        # Remove any extraneous connectors
        extra_conns = db.query(models.Connector).filter(
            models.Connector.station_id == station.id,
            models.Connector.connector_number > 3
        ).all()
        for ec in extra_conns:
            db.query(models.ChargingSession).filter(models.ChargingSession.connector_id == ec.id).delete()
            db.delete(ec)
        db.commit()

        # Seed Driver 1 (Budi Santoso)
        user1 = db.query(models.User).filter(models.User.username == "driver1").first()
        if not user1:
            user1 = models.User(
                username="driver1",
                full_name="Budi Santoso",
                phone="081298765432",
                password_hash="password123",
                role="DRIVER",
                wallet_balance=150000.0
            )
            db.add(user1)
            db.commit()
            db.refresh(user1)

            ev1 = models.Vehicle(
                user_id=user1.id,
                brand="Hyundai",
                model="Ioniq 5 Long Range",
                battery_capacity_kwh=72.6,
                max_ac_kw=11.0,
                max_dc_kw=220.0,
                current_soc=28.0,
                license_plate="B 1888 ION",
                efficiency_km_kwh=6.6,
                architecture_voltage=800.0
            )
            db.add(ev1)

            rfid1 = models.RFIDCard(
                user_id=user1.id,
                card_uid="FLAZZ-88219",
                card_name="BCA Flazz Utama (Budi)",
                balance=100000.0,
                card_type="Flazz BCA"
            )
            rfid2 = models.RFIDCard(
                user_id=user1.id,
                card_uid="EMONEY-LOW-99",
                card_name="Mandiri E-Money (Saldo Minim)",
                balance=15000.0,
                card_type="Mandiri E-Money"
            )
            db.add_all([rfid1, rfid2])
            db.commit()

        # Seed Driver 2 (Siti Rahma)
        user2 = db.query(models.User).filter(models.User.username == "driver2").first()
        if not user2:
            user2 = models.User(
                username="driver2",
                full_name="Siti Rahma",
                phone="081311223344",
                password_hash="password123",
                role="DRIVER",
                wallet_balance=200000.0
            )
            db.add(user2)
            db.commit()
            db.refresh(user2)

            ev2 = models.Vehicle(
                user_id=user2.id,
                brand="Wuling",
                model="Binguo EV Max",
                battery_capacity_kwh=31.9,
                max_ac_kw=7.0,
                max_dc_kw=50.0,
                current_soc=35.0,
                license_plate="B 2468 WLG",
                efficiency_km_kwh=10.4,
                architecture_voltage=400.0
            )
            rfid_siti = models.RFIDCard(
                user_id=user2.id,
                card_uid="FLAZZ-SITI-01",
                card_name="BCA Flazz Siti",
                balance=125000.0,
                card_type="Flazz BCA"
            )
            db.add_all([ev2, rfid_siti])
            db.commit()

        # Seed Admin / Operator
        admin = db.query(models.User).filter(models.User.username == "admin").first()
        if not admin:
            admin = models.User(
                username="admin",
                full_name="Operator SPKLU Sudirman",
                phone="081100998877",
                password_hash="admin123",
                role="OPERATOR",
                wallet_balance=500000.0
            )
            db.add(admin)
            db.commit()

    finally:
        db.close()

def reset_stale_sessions():
    """Resets any lingering sessions and connector locks on application startup."""
    db = SessionLocal()
    try:
        stale_sessions = db.query(models.ChargingSession).filter(models.ChargingSession.status == "CHARGING").all()
        for s in stale_sessions:
            s.status = "COMPLETED"
            s.stop_reason = "SERVER_RESTART"
            s.end_time = utc_now()
            user = db.query(models.User).filter(models.User.id == s.user_id).first()
            if user:
                refund = max(0.0, s.deposit_paid - (s.actual_cost or 0.0))
                user.wallet_balance += refund
                s.refund_amount = refund

        db.query(models.Connector).update({"status": "AVAILABLE", "current_session_id": None, "locked_by_user_id": None})
        db.commit()
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Modern lifespan event handler for FastAPI.
    Encapsulates startup initialization and graceful shutdown cleanup.
    """
    # 1. Database table creation & migrations
    Base.metadata.create_all(bind=engine)
    migrate_db()

    # 2. Seed initial data
    seed_initial_data()

    # 3. Clean up stale sessions
    reset_stale_sessions()

    # 4. Register WebSocket broadcaster
    setup_ws_broadcaster()

    # 5. Start ADB background hardware monitor
    adb_task = asyncio.create_task(ADBBatteryMonitor.start_monitoring())

    yield

    # Shutdown: gracefully terminate ADB monitor
    ADBBatteryMonitor.stop()
    adb_task.cancel()
    try:
        await adb_task
    except asyncio.CancelledError:
        pass

# Ensure directories exist
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(STATIC_DIR / "css", exist_ok=True)
os.makedirs(STATIC_DIR / "js", exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app = FastAPI(
    title="EV Charging Station Simulator",
    version="2.0.0",
    lifespan=lifespan
)

# Global Domain Exception Handler
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Register Routers
app.include_router(api_auth.router)
app.include_router(api_station.router)
app.include_router(ws_charging.router)

@app.get("/")
def index():
    return RedirectResponse(url="/kiosk")

@app.get("/kiosk")
def kiosk_page(request: Request):
    return templates.TemplateResponse(request=request, name="kiosk.html", context={"station_code": STATION_CODE})

@app.get("/driver")
def driver_page(request: Request):
    return templates.TemplateResponse(request=request, name="driver.html", context={"station_code": STATION_CODE})
