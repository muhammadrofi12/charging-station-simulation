import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..core.exceptions import AppError, NotFoundError
from ..services.billing_service import BillingService
from ..services.charging_engine import ChargingEngine
from ..services.station_manager import StationManager
from ..services.port_mapper import PortMapper
from ..services.adb_battery import ADBBatteryMonitor

router = APIRouter(prefix="/api/station", tags=["Station & Charging Operations"])

def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

@router.get("/adb-battery")
def get_adb_battery() -> Dict[str, Any]:
    state = ADBBatteryMonitor.get_last_state()
    if not state or not state.get("connected", False):
        return {"connected": False}
    return state

@router.get("/{station_code}/active-sessions")
def get_station_active_sessions(station_code: str, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    station = db.query(models.Station).filter(models.Station.code == station_code).first()
    if not station:
        raise HTTPException(status_code=404, detail="Stasiun tidak ditemukan.")
    
    sessions = db.query(models.ChargingSession).filter(
        models.ChargingSession.station_id == station.id,
        models.ChargingSession.status == "CHARGING"
    ).all()
    
    result = []
    for s in sessions:
        connector = db.query(models.Connector).filter(models.Connector.id == s.connector_id).first()
        vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == s.vehicle_id).first()
        tariff = connector.tariff_per_kwh if connector else 2466.0
        efficiency = vehicle.efficiency_km_kwh if vehicle else 6.8
        km_added = round((s.energy_delivered_kwh or 0.0) * efficiency, 1)
        cost = min(s.deposit_paid, round((s.energy_delivered_kwh or 0.0) * tariff, 0))
        petrol_cost = km_added * 1300.0
        money_saved = max(0.0, petrol_cost - cost)
        arch_v = vehicle.architecture_voltage if vehicle and vehicle.architecture_voltage else 400.0
        kw = s.current_power_kw or 0.0
        current_amps = round((kw * 1000.0) / arch_v, 1) if arch_v else 0.0
        
        result.append({
            "session_id": s.id,
            "session_code": s.session_code,
            "connector_id": s.connector_id,
            "connector_name": connector.name if connector else f"Nozzle #{s.connector_id}",
            "connector_number": connector.connector_number if connector else 1,
            "car_brand": vehicle.brand if vehicle else "EV",
            "car_model": vehicle.model if vehicle else "Real EV",
            "car_plate": vehicle.license_plate if vehicle else "-",
            "current_soc": s.current_soc,
            "target_soc": s.target_soc,
            "energy_delivered_kwh": s.energy_delivered_kwh,
            "current_power_kw": kw,
            "voltage": round(arch_v, 1),
            "current_amps": current_amps,
            "km_added": km_added,
            "charging_speed_km_per_min": round((kw * efficiency) / 60.0, 1) if kw else 0.0,
            "money_saved_petrol": money_saved,
            "current_cost": cost,
            "deposit_paid": s.deposit_paid
        })
    return result

@router.get("/{station_code}", response_model=schemas.StationResponse)
def get_station_info(station_code: str, db: Session = Depends(get_db)):
    try:
        return StationManager.get_station_with_connectors(db, station_code)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)

class PlugNozzleRequest(BaseModel):
    user_id: Optional[int] = None

@router.post("/connector/{connector_id}/plug")
async def plug_nozzle(
    connector_id: int,
    req: Optional[PlugNozzleRequest] = None,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    uid = req.user_id if (req and req.user_id) else user_id
    connector = db.query(models.Connector).filter(models.Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Konektor tidak ditemukan.")
    
    # 1. Check if nozzle is actively charging
    if connector.status == "CHARGING":
        raise HTTPException(status_code=409, detail=f"❌ {connector.name} sedang dalam proses pengisian aktif!")

    # 2. Check if nozzle is locked by another user
    if connector.locked_by_user_id and connector.locked_by_user_id != uid:
        other_user = db.query(models.User).filter(models.User.id == connector.locked_by_user_id).first()
        other_name = other_user.full_name if other_user else "pengguna lain"
        raise HTTPException(
            status_code=409,
            detail=f"❌ {connector.name} sedang digunakan oleh {other_name}. Silakan pilih nozzle lain!"
        )

    # 3. Check if user already has an active charging session
    if uid:
        active_sess = db.query(models.ChargingSession).filter(
            models.ChargingSession.user_id == uid,
            models.ChargingSession.status == "CHARGING"
        ).first()
        if active_sess:
            raise HTTPException(
                status_code=409,
                detail="❌ Anda sedang memiliki sesi pengisian aktif di stasiun ini! Selesaikan sesi tersebut terlebih dahulu."
            )

        # 4. Check if user already locked a different nozzle
        prev_claimed = db.query(models.Connector).filter(
            models.Connector.locked_by_user_id == uid,
            models.Connector.id != connector_id
        ).first()
        if prev_claimed:
            raise HTTPException(
                status_code=409,
                detail=f"❌ Akun Anda sedang memilih / menggunakan {prev_claimed.name}! Batalkan atau selesaikan nozzle tersebut terlebih dahulu sebelum memilih nozzle lain."
            )

        # 5. Return immediately if already locked and connected to this user
        if connector.locked_by_user_id == uid and connector.status == "CONNECTED":
            return {
                "status": "CONNECTED",
                "message": f"Kabel {connector.name} sudah terhubung ke kendaraan Anda!",
                "connector_id": connector.id,
                "connector_name": connector.name,
                "locked_by_user_id": connector.locked_by_user_id
            }

        connector.locked_by_user_id = uid
        connector.status = "CONNECTED"
        db.commit()
        db.refresh(connector)

        await ChargingEngine.broadcast({
            "event": "NOZZLE_CLAIMED",
            "station_id": connector.station_id,
            "connector_id": connector.id,
            "connector_name": connector.name,
            "locked_by_user_id": uid
        })

    # Mark connector simulated so ADB polling doesn't reset it
    StationManager.simulated_plugged_ids.add(connector_id)

    # Launch handshake sequence
    asyncio.create_task(ChargingEngine.run_handshake(connector_id, uid))

    return {
        "status": "HANDSHAKING",
        "message": f"Memulai inisialisasi & verifikasi keselamatan dengan {connector.name}...",
        "connector_id": connector.id,
        "connector_name": connector.name,
        "locked_by_user_id": connector.locked_by_user_id
    }

@router.post("/connector/{connector_id}/unplug")
async def unplug_nozzle(connector_id: int, db: Session = Depends(get_db)):
    try:
        connector = StationManager.unplug_connector(db, connector_id)
    except AppError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    await ChargingEngine.broadcast({
        "event": "NOZZLE_UNPLUGGED",
        "station_id": connector.station_id,
        "connector_id": connector.id,
        "connector_name": connector.name,
        "status": connector.status
    })
    return {
        "status": "SUCCESS",
        "message": f"{connector.name} telah dicabut dan kembali ke dock.",
        "connector_status": connector.status
    }

@router.post("/connector/{connector_id}/claim")
async def claim_nozzle(connector_id: int, req: schemas.ClaimRequest, db: Session = Depends(get_db)):
    connector = db.query(models.Connector).filter(models.Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Nozzle tidak ditemukan.")

    if connector.status == "CHARGING":
        raise HTTPException(status_code=400, detail="Nozzle ini sedang dalam proses pengisian!")

    # Check cable connected
    if connector.status == "AVAILABLE":
        raise HTTPException(
            status_code=400,
            detail="⚠️ Kabel belum dicolokkan ke mobil! Silakan colokkan nozzle ke port charging mobil terlebih dahulu."
        )

    # Check already claimed by another user
    if connector.locked_by_user_id and connector.locked_by_user_id != req.user_id:
        other_user = db.query(models.User).filter(models.User.id == connector.locked_by_user_id).first()
        other_name = other_user.full_name if other_user else "pengguna lain"
        raise HTTPException(
            status_code=409,
            detail=f"❌ Nozzle ini sedang digunakan oleh {other_name}. Silakan pilih nozzle lain!"
        )

    # Check active session for this user
    active_sess = db.query(models.ChargingSession).filter(
        models.ChargingSession.user_id == req.user_id,
        models.ChargingSession.status == "CHARGING"
    ).first()
    if active_sess:
        raise HTTPException(
            status_code=409,
            detail="❌ Anda sedang memiliki sesi pengisian aktif di stasiun ini! Selesaikan sesi tersebut terlebih dahulu."
        )

    # Check user already claimed another nozzle
    prev_claimed = db.query(models.Connector).filter(
        models.Connector.locked_by_user_id == req.user_id,
        models.Connector.id != connector_id
    ).first()
    if prev_claimed:
        raise HTTPException(
            status_code=409,
            detail=f"❌ Akun Anda sudah mengklaim {prev_claimed.name}! Batalkan pilihan {prev_claimed.name} terlebih dahulu sebelum memilih nozzle lain."
        )

    connector.locked_by_user_id = req.user_id
    db.commit()
    db.refresh(connector)

    await ChargingEngine.broadcast({
        "event": "NOZZLE_CLAIMED",
        "station_id": connector.station_id,
        "connector_id": connector.id,
        "connector_name": connector.name,
        "locked_by_user_id": req.user_id
    })

    return {
        "status": "SUCCESS",
        "message": f"Nozzle {connector.name} berhasil diklaim!",
        "connector_id": connector.id,
        "locked_by_user_id": connector.locked_by_user_id
    }

@router.post("/connector/{connector_id}/release")
async def release_nozzle(connector_id: int, req: schemas.ClaimRequest, db: Session = Depends(get_db)):
    connector = db.query(models.Connector).filter(models.Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Nozzle tidak ditemukan.")

    if connector.status == "CHARGING":
        raise HTTPException(status_code=400, detail="Tidak dapat melepas nozzle yang sedang aktif mengisi daya!")

    if connector.locked_by_user_id == req.user_id:
        connector.locked_by_user_id = None
        db.commit()
        db.refresh(connector)

        await ChargingEngine.broadcast({
            "event": "NOZZLE_RELEASED",
            "station_id": connector.station_id,
            "connector_id": connector.id,
            "connector_name": connector.name
        })

    return {
        "status": "SUCCESS",
        "message": f"Klaim pada {connector.name} telah dilepas."
    }

@router.post("/estimate", response_model=schemas.EstimateResponse)
def get_charging_estimate(req: schemas.EstimateRequest, db: Session = Depends(get_db)):
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == req.vehicle_id).first()
    connector = db.query(models.Connector).filter(models.Connector.id == req.connector_id).first()
    if not vehicle or not connector:
        raise HTTPException(status_code=404, detail="Perangkat HP atau Konektor tidak ditemukan.")
    
    return BillingService.calculate_estimate(
        vehicle=vehicle,
        connector=connector,
        target_type=req.target_type,
        manual_kwh=req.manual_kwh,
        custom_target_soc=req.custom_target_soc,
        manual_mah=req.manual_mah
    )

@router.post("/vehicle/{vehicle_id}/soc")
def update_vehicle_soc(vehicle_id: int, req: schemas.UpdateSocRequest, db: Session = Depends(get_db)):
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Kendaraan tidak ditemukan.")
    vehicle.current_soc = min(100.0, max(0.0, round(req.soc, 1)))
    db.commit()
    return {"status": "SUCCESS", "vehicle_id": vehicle.id, "current_soc": vehicle.current_soc}

@router.post("/session/{session_id}/sync-battery")
async def sync_session_battery(session_id: int, req: schemas.UpdateSocRequest, db: Session = Depends(get_db)):
    session = db.query(models.ChargingSession).filter(models.ChargingSession.id == session_id).first()
    if not session or session.status != "CHARGING":
        return {"status": "SKIPPED", "message": "Session tidak aktif"}
    
    new_soc = min(100.0, max(0.0, round(req.soc, 1)))
    await ChargingEngine.sync_battery_soc(session_id, new_soc)
    return {"status": "SUCCESS", "session_id": session.id, "current_soc": new_soc}

@router.post("/start")
async def start_charging(req: schemas.StartChargingRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    connector = db.query(models.Connector).filter(models.Connector.id == req.connector_id).first()
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == req.vehicle_id).first()

    if not user or not connector or not vehicle:
        raise HTTPException(status_code=404, detail="User, Konektor, atau HP tidak ditemukan.")

    if connector.status == "CHARGING":
        raise HTTPException(status_code=400, detail="Konektor ini sedang digunakan untuk sesi pengisian lain!")

    if connector.locked_by_user_id and connector.locked_by_user_id != req.user_id:
        raise HTTPException(status_code=403, detail="Nozzle ini sedang diklaim oleh pengguna lain!")

    active_user_session = db.query(models.ChargingSession).filter(
        models.ChargingSession.user_id == req.user_id,
        models.ChargingSession.status == "CHARGING"
    ).first()
    if active_user_session:
        conn_name = active_user_session.connector.name if active_user_session.connector else "nozzle lain"
        raise HTTPException(
            status_code=400,
            detail=f"Anda masih memiliki sesi pengisian aktif (#{active_user_session.session_code}) di {conn_name}. Selesaikan sesi tersebut terlebih dahulu."
        )

    # Calculate estimate and deposit needed
    estimate = BillingService.calculate_estimate(
        vehicle=vehicle,
        connector=connector,
        target_type=req.target_type,
        manual_kwh=req.manual_kwh,
        custom_target_soc=req.target_soc,
        manual_mah=req.manual_mah
    )

    deposit_needed = estimate.estimated_cost
    if deposit_needed <= 0:
        deposit_needed = 15000.0

    # 1. Process payment / Lock deposit
    try:
        BillingService.process_payment(
            db=db,
            user=user,
            deposit_amount=deposit_needed,
            payment_method=req.payment_method,
            card_uid=req.card_uid
        )
    except AppError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    # 2. Create Charging Session
    session_code = f"EV-{utc_now().strftime('%y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    is_smartphone = vehicle.battery_capacity_kwh <= 0.1
    target_kwh = estimate.energy_needed_kwh
    if req.target_type in ("MANUAL_KWH", "MANUAL_MAH"):
        if req.manual_kwh and req.manual_kwh > 0:
            target_kwh = min(req.manual_kwh, estimate.energy_needed_kwh)
        elif is_smartphone and req.manual_mah and req.manual_mah > 0:
            target_kwh = max(0.0001, round((req.manual_mah / 5000.0) * 0.02, 6))
    elif is_smartphone:
        target_kwh = max(0.0001, round(estimate.energy_needed_kwh, 6))

    new_session = models.ChargingSession(
        session_code=session_code,
        user_id=user.id,
        station_id=connector.station_id,
        connector_id=connector.id,
        vehicle_id=vehicle.id,
        start_soc=vehicle.current_soc,
        target_soc=estimate.target_soc,
        current_soc=vehicle.current_soc,
        target_type=req.target_type,
        target_kwh=target_kwh,
        deposit_paid=deposit_needed,
        payment_method=req.payment_method,
        payment_card_uid=req.card_uid,
        status="CHARGING",
        start_time=utc_now()
    )
    db.add(new_session)
    connector.status = "CHARGING"
    connector.locked_by_user_id = user.id
    db.commit()
    db.refresh(new_session)

    connector.current_session_id = new_session.id
    db.commit()

    # 3. Launch background simulation loop
    asyncio.create_task(ChargingEngine.run_simulation_loop(new_session.id))

    return {
        "status": "SUCCESS",
        "message": "Pengisian daya berhasil dimulai! Listrik mulai mengalir.",
        "session_id": new_session.id,
        "session_code": new_session.session_code,
        "deposit_paid": deposit_needed,
        "payment_method": req.payment_method,
        "estimated_duration_minutes": estimate.estimated_duration_minutes
    }

@router.post("/stop")
async def stop_charging(req: schemas.StopChargingRequest, db: Session = Depends(get_db)):
    session = db.query(models.ChargingSession).filter(models.ChargingSession.id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi pengisian tidak ditemukan.")

    if session.status != "CHARGING":
        return {
            "status": "INFO",
            "message": "Sesi pengisian sudah berhenti.",
            "actual_cost": session.actual_cost,
            "refund_amount": session.refund_amount
        }

    # Signal engine to stop
    ChargingEngine.request_stop(session.id)

    # Wait briefly for settlement
    for _ in range(15):
        await asyncio.sleep(0.2)
        db.refresh(session)
        if session.status != "CHARGING":
            break

    return {
        "status": "SUCCESS",
        "message": f"Pengisian berhasil dihentikan. Biaya aktual: Rp {session.actual_cost:,.0f}. Sisa Rp {session.refund_amount:,.0f} telah dikembalikan!",
        "energy_delivered_kwh": session.energy_delivered_kwh,
        "actual_cost": session.actual_cost,
        "refund_amount": session.refund_amount,
        "final_soc": session.current_soc
    }

@router.get("/active-session/{connector_id}")
def get_active_session(connector_id: int, db: Session = Depends(get_db)):
    connector = db.query(models.Connector).filter(models.Connector.id == connector_id).first()
    if not connector or not connector.current_session_id:
        return {"active": False}
    
    session = db.query(models.ChargingSession).filter(models.ChargingSession.id == connector.current_session_id).first()
    if not session:
        return {"active": False}
    
    return {
        "active": session.status == "CHARGING",
        "session_id": session.id,
        "session_code": session.session_code,
        "current_soc": session.current_soc,
        "energy_delivered_kwh": session.energy_delivered_kwh,
        "energy_delivered_mah": round((session.energy_delivered_kwh / 0.02) * 5000),
        "current_power_kw": session.current_power_kw,
        "deposit_paid": session.deposit_paid,
        "payment_method": session.payment_method
    }

@router.get("/user-active-session/{user_id}")
def get_user_active_session(user_id: int, db: Session = Depends(get_db)):
    session = db.query(models.ChargingSession).filter(
        models.ChargingSession.user_id == user_id,
        models.ChargingSession.status == "CHARGING"
    ).order_by(models.ChargingSession.id.desc()).first()

    if not session:
        return {"has_active_session": False}

    connector = db.query(models.Connector).filter(models.Connector.id == session.connector_id).first()

    # Verify if session is truly valid or a zombie
    is_engine_stopped = (session.id in ChargingEngine._active_sessions and not ChargingEngine._active_sessions[session.id])
    is_connector_mismatch = (not connector or connector.status != "CHARGING" or (connector.current_session_id is not None and connector.current_session_id != session.id))

    if is_engine_stopped or is_connector_mismatch:
        session.status = "COMPLETED"
        session.stop_reason = "ORPHANED_CLEANUP"
        session.end_time = utc_now()
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            refund = max(0.0, session.deposit_paid - (session.actual_cost or 0.0))
            user.wallet_balance += refund
            session.refund_amount = refund
        if connector and connector.current_session_id == session.id:
            connector.status = "AVAILABLE"
            connector.current_session_id = None
        db.commit()
        return {"has_active_session": False}

    vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == session.vehicle_id).first()
    battery_cap = vehicle.battery_capacity_kwh if vehicle else 0.02
    battery_mah = 5000.0 if battery_cap <= 0.1 else round(battery_cap * 250000.0, 0)
    delivered_mah = round((session.energy_delivered_kwh / battery_cap) * battery_mah, 0)
    tariff = connector.tariff_per_kwh if connector else 2466.0

    if battery_cap <= 0.1:
        current_cost = min(session.deposit_paid, round((delivered_mah / 500.0) * tariff, 0))
    else:
        current_cost = min(session.deposit_paid, round(session.energy_delivered_kwh * tariff, 0))
    remaining_deposit = max(0.0, session.deposit_paid - current_cost)
    watts = (session.current_power_kw * 1000.0) if session.current_power_kw else 33.0

    efficiency = vehicle.efficiency_km_kwh if (vehicle and vehicle.efficiency_km_kwh) else 6.8
    layman = ChargingEngine.calculate_layman_metrics(
        energy_kwh=session.energy_delivered_kwh,
        power_kw=session.current_power_kw,
        efficiency_km_kwh=efficiency,
        actual_cost=current_cost,
        current_soc=session.current_soc,
        target_soc=session.target_soc,
        target_kwh=session.target_kwh
    )

    return {
        "has_active_session": True,
        "session_id": session.id,
        "session_code": session.session_code,
        "station_id": session.station_id,
        "connector_id": session.connector_id,
        "connector_name": connector.name if connector else "-",
        "connector_type": connector.connector_type if connector else "Type 2",
        "current_soc": session.current_soc,
        "energy_delivered_kwh": session.energy_delivered_kwh,
        "energy_delivered_mah": delivered_mah,
        "current_power_kw": session.current_power_kw,
        "current_power_w": round(watts, 1),
        "deposit_paid": session.deposit_paid,
        "current_cost": current_cost,
        "remaining_deposit": remaining_deposit,
        "payment_method": session.payment_method,
        "car_brand": vehicle.brand if vehicle else "Hyundai",
        "car_model": vehicle.model if vehicle else "Ioniq 5 Long Range",
        "car_plate": vehicle.license_plate if vehicle else "B 1888 ION",
        "battery_capacity_kwh": battery_cap,
        **layman
    }

@router.post("/emergency-reset")
async def emergency_reset(db: Session = Depends(get_db)):
    # 1. Stop all active simulation loops in memory
    for sid in list(ChargingEngine._active_sessions.keys()):
        ChargingEngine.request_stop(sid)
    ChargingEngine._active_sessions.clear()

    # 2. Settle all charging sessions in database
    sessions = db.query(models.ChargingSession).filter(models.ChargingSession.status == "CHARGING").all()
    for s in sessions:
        s.status = "COMPLETED"
        s.stop_reason = "EMERGENCY_RESET"
        s.end_time = utc_now()
        user = db.query(models.User).filter(models.User.id == s.user_id).first()
        if user:
            refund = max(0.0, s.deposit_paid - (s.actual_cost or 0.0))
            user.wallet_balance += refund
            s.refund_amount = refund

    # 3. Reset all connectors to AVAILABLE
    db.query(models.Connector).update({"status": "AVAILABLE", "current_session_id": None, "locked_by_user_id": None})
    StationManager.simulated_plugged_ids.clear()
    db.commit()

    # 4. Broadcast reset event to all clients
    await ChargingEngine.broadcast({
        "event": "STATION_RESET",
        "message": "Stasiun telah di-reset ke kondisi awal."
    })

    return {
        "status": "SUCCESS",
        "message": "Stasiun dan semua konektor berhasil di-reset ke kondisi awal."
    }

class PortCalibrateRequest(BaseModel):
    port_key: str
    connector_id: int
    label: Optional[str] = None

@router.get("/ports/config")
def get_port_config():
    return {
        "mappings": PortMapper.get_all_mappings(),
        "current_device": ADBBatteryMonitor.get_current_port_info()
    }

@router.post("/ports/calibrate")
def calibrate_port(req: PortCalibrateRequest):
    PortMapper.set_port_mapping(req.port_key, req.connector_id, req.label)
    return {
        "status": "SUCCESS",
        "message": f"Port '{req.port_key}' berhasil dipetakan ke Nozzle {req.connector_id}.",
        "mappings": PortMapper.get_all_mappings()
    }

class DevRemapPortRequest(BaseModel):
    connector_id: int
    port_key: Optional[str] = None

@router.post("/dev/remap-active-port")
async def dev_remap_active_port(req: DevRemapPortRequest, db: Session = Depends(get_db)):
    if req.connector_id not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="connector_id must be 1, 2, or 3")
    
    current = ADBBatteryMonitor.get_current_port_info()
    port_raw = current.get("port")
    port_key = req.port_key or (PortMapper.extract_port_key(port_raw) if port_raw else "Port_#0002")
    
    label = f"Port USB -> Nozzle {req.connector_id}"
    PortMapper.set_port_mapping(port_key, req.connector_id, label)
    
    active_devices = ADBBatteryMonitor.get_all_active_devices()
    if active_devices:
        device_map = {}
        for d in active_devices:
            d["connector_id"] = req.connector_id
            d["port_key"] = port_key
            device_map[d["serial"]] = d
        await ADBBatteryMonitor._sync_connectors_with_devices(device_map, force_all_unplugged=True)
    else:
        db.query(models.Connector).filter(models.Connector.status == "CONNECTED").update({"status": "AVAILABLE"})
        db.commit()
        await ChargingEngine.broadcast({
            "event": "PORT_NOZZLE_RECONFIGURED",
            "port_key": port_key,
            "connector_id": req.connector_id,
            "message": f"Port {port_key} berhasil dialihkan ke Nozzle {req.connector_id}."
        })

    return {
        "status": "SUCCESS",
        "port_key": port_key,
        "connector_id": req.connector_id,
        "message": f"Port hardware {port_key} berhasil dipetakan ke Nozzle {req.connector_id}."
    }
