from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class UserBase(BaseModel):
    username: str
    full_name: str
    phone: Optional[str] = "081234567890"

class UserCreate(UserBase):
    password: Optional[str] = "password123"
    role: Optional[str] = "DRIVER"

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    full_name: str
    phone: Optional[str] = "081234567890"
    password: str

class UserResponse(UserBase):
    id: int
    role: str = "DRIVER"
    wallet_balance: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TopUpRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Nominal top up saldo")
    method: str = Field(default="QRIS", description="Metode top up: QRIS, VA, CC")

class VehicleCreate(BaseModel):
    brand: str
    model: str
    battery_capacity_kwh: float
    max_ac_kw: Optional[float] = 11.0
    max_dc_kw: Optional[float] = 150.0
    current_soc: Optional[float] = 25.0
    license_plate: Optional[str] = "B 1234 EV"
    efficiency_km_kwh: Optional[float] = 6.8
    architecture_voltage: Optional[float] = 400.0

class VehicleResponse(VehicleCreate):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)

class RFIDCardCreate(BaseModel):
    card_uid: str
    card_name: str
    card_type: Optional[str] = "BCA Flazz"
    balance: Optional[float] = 100000.0

class RFIDCardResponse(RFIDCardCreate):
    id: int
    user_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class ConnectorResponse(BaseModel):
    id: int
    connector_number: int
    name: str
    type_category: str
    connector_type: str
    max_power_kw: float
    tariff_per_kwh: float
    status: str
    current_session_id: Optional[int] = None
    locked_by_user_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class ClaimRequest(BaseModel):
    user_id: int

class StationResponse(BaseModel):
    id: int
    code: str
    name: str
    location: str
    status: str
    connectors: List[ConnectorResponse] = []

    model_config = ConfigDict(from_attributes=True)

class EstimateRequest(BaseModel):
    vehicle_id: int
    connector_id: int
    target_type: str = Field(default="FULL", description="'FULL' (Cas 80%/100%) atau 'MANUAL_KWH'")
    manual_kwh: Optional[float] = 15.0
    manual_mah: Optional[float] = None  # Kept for backward compatibility if client sends it
    custom_target_soc: Optional[float] = 100.0

class EstimateResponse(BaseModel):
    current_soc: float
    target_soc: float
    battery_capacity_kwh: float
    energy_needed_kwh: float
    tariff_per_kwh: float
    estimated_cost: float
    estimated_duration_minutes: float
    max_charging_kw: float

class StartChargingRequest(BaseModel):
    user_id: int
    station_code: str
    connector_id: int
    vehicle_id: int
    target_type: str = "FULL"  # "FULL" or "MANUAL_KWH"
    manual_kwh: Optional[float] = None
    manual_mah: Optional[float] = None  # Kept for backward compatibility if client sends it
    target_soc: Optional[float] = 100.0
    payment_method: str = "WALLET"  # "WALLET", "QRIS", "EMONEY"
    card_uid: Optional[str] = None

class StopChargingRequest(BaseModel):
    session_id: int
    user_id: int

class ChargingSessionResponse(BaseModel):
    id: int
    session_code: str
    status: str
    start_soc: float
    current_soc: float
    target_soc: float
    energy_delivered_kwh: float
    current_power_kw: float
    deposit_paid: float
    actual_cost: float
    refund_amount: float
    payment_method: str
    start_time: datetime
    end_time: Optional[datetime] = None
    stop_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class UpdateSocRequest(BaseModel):
    soc: float
