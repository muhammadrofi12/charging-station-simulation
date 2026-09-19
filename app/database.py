import os
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .core.config import DATABASE_URL, DB_PATH

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
else:
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def migrate_db():
    """Applies schema migrations idempotently without failing on existing columns."""
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if "connectors" in tables:
            columns = [col["name"] for col in inspector.get_columns("connectors")]
            if "locked_by_user_id" not in columns:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE connectors ADD COLUMN locked_by_user_id INTEGER REFERENCES users(id)"))
        if "vehicles" in tables:
            v_columns = [col["name"] for col in inspector.get_columns("vehicles")]
            if "efficiency_km_kwh" not in v_columns:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE vehicles ADD COLUMN efficiency_km_kwh FLOAT DEFAULT 6.8"))
            if "architecture_voltage" not in v_columns:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE vehicles ADD COLUMN architecture_voltage FLOAT DEFAULT 400.0"))
    except Exception:
        pass

def get_db():
    """FastAPI dependency for database session lifecycle."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
