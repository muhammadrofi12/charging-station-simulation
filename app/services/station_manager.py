from typing import Set
from sqlalchemy.orm import Session
from .. import models
from ..core.exceptions import NotFoundError, ValidationError

class StationManager:
    """
    Manages station inventory and connector physical state.
    Framework-agnostic domain service.
    """
    simulated_plugged_ids: Set[int] = set()

    @staticmethod
    def get_station_with_connectors(db: Session, station_code: str) -> models.Station:
        station = db.query(models.Station).filter(models.Station.code == station_code).first()
        if not station:
            raise NotFoundError(f"Stasiun '{station_code}' tidak ditemukan.")
        return station

    @classmethod
    def plug_connector(cls, db: Session, connector_id: int, is_simulated: bool = False) -> models.Connector:
        connector = db.query(models.Connector).filter(models.Connector.id == connector_id).first()
        if not connector:
            raise NotFoundError("Konektor tidak ditemukan.")
        if connector.status == "CHARGING":
            raise ValidationError("Konektor sedang dalam proses pengisian!")
        
        connector.status = "CONNECTED"
        if is_simulated:
            cls.simulated_plugged_ids.add(connector_id)
        db.commit()
        db.refresh(connector)
        return connector

    @classmethod
    def unplug_connector(cls, db: Session, connector_id: int) -> models.Connector:
        connector = db.query(models.Connector).filter(models.Connector.id == connector_id).first()
        if not connector:
            raise NotFoundError("Konektor tidak ditemukan.")
        if connector.status == "CHARGING":
            raise ValidationError("Harap hentikan pengisian terlebih dahulu sebelum mencabut kabel!")
        
        connector.status = "AVAILABLE"
        connector.current_session_id = None
        connector.locked_by_user_id = None
        cls.simulated_plugged_ids.discard(connector_id)
        db.commit()
        db.refresh(connector)
        return connector
