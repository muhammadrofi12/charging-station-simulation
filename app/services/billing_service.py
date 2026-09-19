from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from .. import models, schemas
from ..core.exceptions import ValidationError, InsufficientBalanceError

def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class BillingService:
    """
    Billing and financial calculation domain service.
    Framework-agnostic: relies on pure Python calculations and domain exceptions.
    """

    @staticmethod
    def calculate_estimate(
        vehicle: models.Vehicle,
        connector: models.Connector,
        target_type: str,
        manual_kwh: Optional[float] = 15.0,
        custom_target_soc: Optional[float] = 100.0,
        manual_mah: Optional[float] = None
    ) -> schemas.EstimateResponse:
        current_soc = vehicle.current_soc
        battery_cap = vehicle.battery_capacity_kwh
        tariff = connector.tariff_per_kwh
        battery_mah = 5000.0 if battery_cap <= 0.1 else round(battery_cap * 250000.0, 0)

        # Non-mutating effective SoC for estimation
        effective_soc = current_soc

        if target_type == "FULL":
            target_soc = min(100.0, custom_target_soc if custom_target_soc else 100.0)
            if target_soc <= effective_soc:
                if effective_soc < 100.0:
                    target_soc = 100.0
                else:
                    # When battery is already 100%, estimate for a standard cycle without mutating the model
                    effective_soc = 28.0
            soc_diff = max(1.0, target_soc - effective_soc)
            energy_needed = battery_cap * (soc_diff / 100.0)
        else:  # MANUAL_KWH or MANUAL_MAH
            if manual_mah is not None and manual_mah > 0:
                energy_needed = min(
                    (manual_mah / battery_mah) * battery_cap,
                    battery_cap * ((100.0 - effective_soc) / 100.0)
                )
            else:
                energy_needed = min(
                    manual_kwh if manual_kwh else 15.0,
                    battery_cap * ((100.0 - effective_soc) / 100.0)
                )
            if energy_needed <= 0:
                energy_needed = min(15.0, battery_cap * 0.2)
            target_soc = min(100.0, effective_soc + (energy_needed / battery_cap * 100.0))

        if energy_needed <= 0:
            energy_needed = min(10.0, battery_cap * 0.15)
            target_soc = min(100.0, effective_soc + (energy_needed / battery_cap * 100.0))

        energy_needed_mah = round((energy_needed / battery_cap) * battery_mah, 0)

        # Max charging power negotiated between connector and vehicle limits
        if connector.type_category == "AC":
            max_power = min(connector.max_power_kw, vehicle.max_ac_kw or 11.0)
        else:
            max_power = min(connector.max_power_kw, vehicle.max_dc_kw or 150.0)

        if max_power <= 0:
            max_power = 7.4

        # Estimated duration in minutes with 90% transfer efficiency factor
        efficiency = 0.90
        estimated_duration_min = (
            (energy_needed / (max_power * efficiency)) * 60.0
            if energy_needed > 0
            else 0.0
        )

        # Cost calculation
        if battery_cap <= 0.1:
            estimated_cost = (energy_needed_mah / 500.0) * tariff
            if energy_needed > 0:
                estimated_cost = max(2000.0, round(estimated_cost, 0))
                energy_needed_kwh = max(0.0001, round(energy_needed, 6))
            else:
                estimated_cost = 5000.0
                energy_needed_kwh = 0.005
        else:
            estimated_cost = max(5000.0, round(energy_needed * tariff, 0))
            energy_needed_kwh = round(energy_needed, 6)

        return schemas.EstimateResponse(
            current_soc=round(effective_soc, 1),
            target_soc=round(target_soc, 1),
            battery_capacity_kwh=round(battery_cap, 3),
            energy_needed_kwh=energy_needed_kwh,
            energy_needed_mah=energy_needed_mah,
            tariff_per_kwh=tariff,
            estimated_cost=round(estimated_cost, 0),
            estimated_duration_minutes=round(estimated_duration_min, 0),
            max_charging_kw=round(max_power, 3)
        )

    @staticmethod
    def process_payment(
        db: Session,
        user: models.User,
        deposit_amount: float,
        payment_method: str,
        card_uid: Optional[str] = None
    ) -> None:
        """
        Validates and locks the deposit payment before charging commences.
        Supports WALLET, QRIS, and EMONEY methods.
        """
        deposit_amount = round(deposit_amount, 0)
        if deposit_amount <= 0:
            raise ValidationError("Nominal pengisian harus lebih dari Rp 0.")

        if payment_method == "WALLET":
            if user.wallet_balance < deposit_amount:
                raise InsufficientBalanceError(
                    f"Saldo Dompet Tidak Cukup! Sisa Saldo: Rp {user.wallet_balance:,.0f}, "
                    f"Diperlukan: Rp {deposit_amount:,.0f}. Silakan Top-up terlebih dahulu."
                )
            user.wallet_balance -= deposit_amount
            tx = models.WalletTransaction(
                user_id=user.id,
                amount=-deposit_amount,
                tx_type="HOLD",
                description=f"Hold Saldo Pengisian (Deposit Rp {deposit_amount:,.0f})"
            )
            db.add(tx)
            db.commit()

        elif payment_method == "EMONEY":
            if not card_uid:
                raise ValidationError("Kartu E-Money belum dipilih atau di-tap!")
            card = db.query(models.RFIDCard).filter(models.RFIDCard.card_uid == card_uid).first()
            if not card:
                card = models.RFIDCard(
                    user_id=user.id,
                    card_uid=card_uid,
                    card_name=f"BCA Flazz (Demo #{card_uid.split('-')[-1] if '-' in card_uid else card_uid})",
                    card_type="BCA FLAZZ",
                    balance=max(149790.0, deposit_amount + 50000.0)
                )
                db.add(card)
                db.commit()
                db.refresh(card)
            elif card.balance < deposit_amount:
                raise InsufficientBalanceError(
                    f"Saldo E-Money Tidak Cukup! Sisa: Rp {card.balance:,.0f}, "
                    f"Butuh: Rp {deposit_amount:,.0f}. Silakan gunakan metode lain."
                )
            card.balance -= deposit_amount
            tx = models.WalletTransaction(
                user_id=user.id,
                amount=-deposit_amount,
                tx_type="HOLD",
                description=f"Pembayaran E-Money [{card.card_name} ({card_uid})] - Deposit Rp {deposit_amount:,.0f}"
            )
            db.add(tx)
            db.commit()

        elif payment_method == "QRIS":
            tx = models.WalletTransaction(
                user_id=user.id,
                amount=0.0,
                tx_type="SETTLEMENT",
                description=f"Pembayaran QRIS Dinamis Lunas: Rp {deposit_amount:,.0f}"
            )
            db.add(tx)
            db.commit()
        else:
            raise ValidationError(f"Metode pembayaran '{payment_method}' tidak dikenali.")

    @staticmethod
    def settle_and_refund(
        db: Session,
        session: models.ChargingSession
    ) -> Tuple[float, float]:
        """
        Calculates actual cost based on delivered energy and refunds unspent deposit.
        """
        connector = db.query(models.Connector).filter(models.Connector.id == session.connector_id).first()
        tariff = connector.tariff_per_kwh if connector else 2466.0

        vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == session.vehicle_id).first()
        is_smartphone = (vehicle.battery_capacity_kwh <= 0.1) if vehicle else True

        if is_smartphone:
            battery_cap = vehicle.battery_capacity_kwh if vehicle else 0.02
            battery_mah = 5000.0
            delivered_mah = (session.energy_delivered_kwh / battery_cap) * battery_mah
            actual_cost = round((delivered_mah / 500.0) * tariff, 0)
        else:
            actual_cost = round(session.energy_delivered_kwh * tariff, 0)

        actual_cost = min(actual_cost, session.deposit_paid)
        refund_amount = max(0.0, session.deposit_paid - actual_cost)

        session.actual_cost = actual_cost
        session.refund_amount = refund_amount
        session.end_time = utc_now()

        user = db.query(models.User).filter(models.User.id == session.user_id).first()

        if refund_amount > 0 and user:
            if session.payment_method == "EMONEY" and session.payment_card_uid:
                card = db.query(models.RFIDCard).filter(models.RFIDCard.card_uid == session.payment_card_uid).first()
                if card:
                    card.balance += refund_amount
                else:
                    user.wallet_balance += refund_amount
            else:
                user.wallet_balance += refund_amount

            tx_refund = models.WalletTransaction(
                user_id=user.id,
                amount=refund_amount,
                tx_type="REFUND",
                description=f"Pengembalian Sisa Deposit Sesi #{session.session_code}: Rp {refund_amount:,.0f}"
            )
            db.add(tx_refund)

        db.commit()
        return actual_cost, refund_amount
