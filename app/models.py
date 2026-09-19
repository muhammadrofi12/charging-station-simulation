from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

def utc_now() -> datetime:
    """Returns current UTC datetime as a naive object for SQLite/PostgreSQL compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), default="081234567890")
    password_hash = Column(String(200), default="password123")
    role = Column(String(20), default="DRIVER")  # DRIVER, OPERATOR, ADMIN
    wallet_balance = Column(Float, default=150000.0)
    created_at = Column(DateTime, default=utc_now)

    vehicles = relationship("Vehicle", back_populates="owner", cascade="all, delete-orphan")
    cards = relationship("RFIDCard", back_populates="owner", cascade="all, delete-orphan")
    sessions = relationship("ChargingSession", back_populates="user")
    wallet_logs = relationship("WalletTransaction", back_populates="user")

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    brand = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    battery_capacity_kwh = Column(Float, nullable=False)
    max_ac_kw = Column(Float, default=11.0)
    max_dc_kw = Column(Float, default=150.0)
    current_soc = Column(Float, default=25.0)  # State of charge %
    license_plate = Column(String(20), default="B 1234 EV")
    efficiency_km_kwh = Column(Float, default=6.8)  # km per kWh
    architecture_voltage = Column(Float, default=400.0)  # 400V or 800V architecture

    owner = relationship("User", back_populates="vehicles")
    sessions = relationship("ChargingSession", back_populates="vehicle")

class RFIDCard(Base):
    __tablename__ = "rfid_cards"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    card_uid = Column(String(50), unique=True, index=True, nullable=False)
    card_name = Column(String(100), nullable=False)
    balance = Column(Float, default=100000.0)
    card_type = Column(String(50), default="BCA Flazz")

    owner = relationship("User", back_populates="cards")

class Station(Base):
    __tablename__ = "stations"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    location = Column(String(200), nullable=False)
    latitude = Column(Float, default=-6.2088)
    longitude = Column(Float, default=106.8456)
    status = Column(String(20), default="AVAILABLE")  # AVAILABLE, IN_USE, OFFLINE

    connectors = relationship("Connector", back_populates="station", cascade="all, delete-orphan")
    sessions = relationship("ChargingSession", back_populates="station")

class Connector(Base):
    __tablename__ = "connectors"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("stations.id"), nullable=False)
    connector_number = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    type_category = Column(String(10), nullable=False)  # "AC" or "DC"
    connector_type = Column(String(50), nullable=False)  # "Type 2", "CCS2"
    max_power_kw = Column(Float, nullable=False)        # 7.4, 22.0, 50.0, 150.0
    tariff_per_kwh = Column(Float, nullable=False)      # 2466, 3000, 3500
    status = Column(String(20), default="AVAILABLE")    # AVAILABLE, CONNECTED, CHARGING, FAULTED
    current_session_id = Column(Integer, nullable=True)
    locked_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    station = relationship("Station", back_populates="connectors")
    sessions = relationship("ChargingSession", back_populates="connector")
    locked_by_user = relationship("User", foreign_keys=[locked_by_user_id])

class ChargingSession(Base):
    __tablename__ = "charging_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_code = Column(String(50), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    station_id = Column(Integer, ForeignKey("stations.id"), nullable=False)
    connector_id = Column(Integer, ForeignKey("connectors.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)

    start_soc = Column(Float, nullable=False)
    target_soc = Column(Float, nullable=False)
    current_soc = Column(Float, nullable=False)
    target_type = Column(String(20), default="FULL")  # FULL, MANUAL_KWH
    target_kwh = Column(Float, nullable=False)
    energy_delivered_kwh = Column(Float, default=0.0)
    current_power_kw = Column(Float, default=0.0)

    deposit_paid = Column(Float, nullable=False)
    actual_cost = Column(Float, default=0.0)
    refund_amount = Column(Float, default=0.0)
    payment_method = Column(String(20), nullable=False)  # WALLET, QRIS, EMONEY
    payment_card_uid = Column(String(50), nullable=True)

    status = Column(String(20), default="CHARGING")  # PREPARING, CHARGING, STOPPED, COMPLETED
    start_time = Column(DateTime, default=utc_now)
    end_time = Column(DateTime, nullable=True)
    stop_reason = Column(String(50), default="IN_PROGRESS")  # USER_STOP, FULL_TARGET_REACHED, TIMEOUT

    user = relationship("User", back_populates="sessions")
    station = relationship("Station", back_populates="sessions")
    connector = relationship("Connector", back_populates="sessions")
    vehicle = relationship("Vehicle", back_populates="sessions")

class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    tx_type = Column(String(20), nullable=False)  # TOPUP, HOLD, SETTLEMENT, REFUND
    description = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=utc_now)

    user = relationship("User", back_populates="wallet_logs")
