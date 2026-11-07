"""
Database connection setup & schema migration manager.

Defaults to SQLite (zero-config, single file, perfect for prototype / field laptop).
Supports PostgreSQL via DATABASE_URL if configured.
Includes non-destructive schema migrations for SQLite.
"""

import os
import shutil
from typing import Dict, Any
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

# Default database lives next to the platform code, whatever folder the server was started from
# (a relative "./aquasentry.db" used to create an empty second database when launched elsewhere).
_PLATFORM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_DB = os.path.join(_PLATFORM_DIR, "aquasentry.db")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///" + _DEFAULT_DB)

if os.environ.get("VERCEL") or os.environ.get("VERCEL_URL"):
    tmp_db_path = "/tmp/aquasentry.db"
    if not os.path.exists(tmp_db_path):
        try:
            shutil.copy2(_DEFAULT_DB, tmp_db_path)
        except Exception as e:
            print(f"Warning: Could not copy initial DB to /tmp: {e}")
    DATABASE_URL = f"sqlite:///{tmp_db_path}"

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_sqlite_columns():
    """Non-destructively add any missing columns and create new tables in SQLite."""
    # Ensure all tables registered on Base exist
    Base.metadata.create_all(bind=engine)

    if not DATABASE_URL.startswith("sqlite"):
        return

    # Imp 22: Enable SQLite Write-Ahead Logging (WAL) and synchronous=NORMAL
    try:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL;"))
            conn.execute(text("PRAGMA synchronous=NORMAL;"))
    except Exception as e:
        print(f"Warning: Could not enable SQLite WAL mode: {e}")

    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    # Readings table migrations
    if "readings" in table_names:
        readings_required = {
            "battery_pct": "FLOAT",
            "source_label": "VARCHAR(64)",
            "source_type": "VARCHAR(32) DEFAULT 'simulated'",
            "analytical_status": "VARCHAR(64) DEFAULT 'within_calibrated_range'",
            "regulatory_tier": "VARCHAR(64) DEFAULT 'Caution'",
            "is_safe_to_drink": "BOOLEAN",
            "uncertainty_ppb": "FLOAT",
            "is_simulated": "BOOLEAN DEFAULT 1",
            "method_version": "VARCHAR(32) DEFAULT 'MAS-G1-v1.2'",
            "model_version": "VARCHAR(32) DEFAULT 'AquaNet-V1'",
            "idempotency_key": "VARCHAR(64)",
        }
        existing_cols = {col["name"] for col in inspector.get_columns("readings")}
        missing = readings_required.keys() - existing_cols

        if missing:
            with engine.begin() as conn:
                for col_name in missing:
                    conn.execute(
                        text(f"ALTER TABLE readings ADD COLUMN {col_name} {readings_required[col_name]}")
                    )

    # Devices table migrations
    if "devices" in table_names:
        devices_required = {
            "firmware_version": "VARCHAR(32) DEFAULT 'v1.0.0'",
            "status": "VARCHAR(32) DEFAULT 'online'",
        }
        existing_cols = {col["name"] for col in inspector.get_columns("devices")}
        missing = devices_required.keys() - existing_cols

        if missing:
            with engine.begin() as conn:
                for col_name in missing:
                    conn.execute(
                        text(f"ALTER TABLE devices ADD COLUMN {col_name} {devices_required[col_name]}")
                    )


def get_db():
    """FastAPI dependency: yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def compact_database() -> Dict[str, Any]:
    """Imp 22: Optimize SQLite database storage and return file diagnostics."""
    if not DATABASE_URL.startswith("sqlite"):
        return {"status": "skipped", "message": "Compaction only applies to SQLite"}

    db_path = DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")
    size_before = os.path.getsize(db_path) if os.path.exists(db_path) else 0

    try:
        with engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT").execute(text("PRAGMA optimize;"))
        size_after = os.path.getsize(db_path) if os.path.exists(db_path) else 0
        return {
            "status": "success",
            "journal_mode": "WAL",
            "size_before_bytes": size_before,
            "size_after_bytes": size_after,
            "saved_bytes": max(0, size_before - size_after),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
