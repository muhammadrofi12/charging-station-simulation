from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..core.exceptions import AppError

router = APIRouter(prefix="/api/auth", tags=["Auth & Profile"])

@router.post("/login", response_model=schemas.UserResponse)
def login(req: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == req.username).first()
    if not user or user.password_hash != req.password:
        raise HTTPException(status_code=401, detail="Username atau password salah!")
    return user

@router.post("/register", response_model=schemas.UserResponse)
def register(user_in: schemas.RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.username == user_in.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username sudah terdaftar! Gunakan username lain.")
    user = models.User(
        username=user_in.username,
        full_name=user_in.full_name,
        phone=user_in.phone,
        password_hash=user_in.password,
        role="DRIVER",
        wallet_balance=150000.0
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Initial default vehicle for registered user
    default_ev = models.Vehicle(
        user_id=user.id,
        brand="Hyundai",
        model="Ioniq 5 Long Range",
        battery_capacity_kwh=72.6,
        max_ac_kw=11.0,
        max_dc_kw=220.0,
        current_soc=28.0,
        license_plate="B 1888 ION",
        efficiency_km_kwh=6.8,
        architecture_voltage=800.0
    )
    card = models.RFIDCard(
        user_id=user.id,
        card_uid=f"FLAZZ-{user.id:04d}",
        card_name=f"Flazz {user.full_name}",
        balance=100000.0,
        card_type="Flazz BCA"
    )
    db.add_all([default_ev, card])
    db.commit()
    return user

@router.get("/users", response_model=List[schemas.UserResponse])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()

@router.get("/user/{user_id}", response_model=schemas.UserResponse)
def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")
    return user

@router.post("/topup/{user_id}")
def topup_wallet(user_id: int, req: schemas.TopUpRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")
    
    user.wallet_balance += req.amount
    tx = models.WalletTransaction(
        user_id=user.id,
        amount=req.amount,
        tx_type="TOPUP",
        description=f"Top Up Saldo via {req.method} sebesar Rp {req.amount:,.0f}"
    )
    db.add(tx)
    db.commit()
    db.refresh(user)
    return {
        "status": "SUCCESS",
        "message": f"Top up Rp {req.amount:,.0f} berhasil!",
        "new_balance": user.wallet_balance
    }

@router.get("/vehicles/{user_id}", response_model=List[schemas.VehicleResponse])
def get_user_vehicles(user_id: int, db: Session = Depends(get_db)):
    vehicles = db.query(models.Vehicle).filter(models.Vehicle.user_id == user_id).all()
    if not vehicles:
        default_ev = models.Vehicle(
            user_id=user_id,
            brand="Hyundai",
            model="Ioniq 5 Long Range",
            battery_capacity_kwh=72.6,
            max_ac_kw=11.0,
            max_dc_kw=220.0,
            current_soc=28.0,
            license_plate="B 1888 ION",
            efficiency_km_kwh=6.8,
            architecture_voltage=800.0
        )
        db.add(default_ev)
        db.commit()
        db.refresh(default_ev)
        vehicles = [default_ev]

    return vehicles

@router.post("/vehicles/{user_id}", response_model=schemas.VehicleResponse)
def add_user_vehicle(user_id: int, car_in: schemas.VehicleCreate, db: Session = Depends(get_db)):
    car = models.Vehicle(user_id=user_id, **car_in.model_dump())
    db.add(car)
    db.commit()
    db.refresh(car)
    return car

@router.get("/cards/{user_id}", response_model=List[schemas.RFIDCardResponse])
def get_user_cards(user_id: int, db: Session = Depends(get_db)):
    return db.query(models.RFIDCard).filter(models.RFIDCard.user_id == user_id).all()

@router.post("/cards/{user_id}", response_model=schemas.RFIDCardResponse)
def add_user_card(user_id: int, card_in: schemas.RFIDCardCreate, db: Session = Depends(get_db)):
    card = models.RFIDCard(user_id=user_id, **card_in.model_dump())
    db.add(card)
    db.commit()
    db.refresh(card)
    return card
