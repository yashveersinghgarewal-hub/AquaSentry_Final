"""
Database connection setup & schema migration manager.

Defaults to SQLite (zero-config, single file, perfect for prototype / field laptop).
Supports PostgreSQL via DATABASE_URL if configured.
Includes non-destructive schema migrations for SQLite.
"""

import os
import shutil

from .logs import get_logger

log = get_logger("database")
from typing import Dict, Any
from sqlalchemy import create_engine, event, inspect, text
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
            log.warning("Could not copy initial DB to /tmp: %s", e)
    DATABASE_URL = f"sqlite:///{tmp_db_path}"

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}


def _sqlite_has_wal_reset_fix() -> bool:
    import sqlite3
    v = sqlite3.sqlite_version_info
    # 3.7.0-3.51.2 have a WAL-reset race fixed in 3.51.3 (backports 3.50.7, 3.44.6)
    return v >= (3, 51, 3) or (3, 50, 7) <= v < (3, 51, 0) or (3, 44, 6) <= v < (3, 45, 0) or v < (3, 7, 0)


def _single_connection() -> bool:
    """The WAL-reset bug needs two connections writing or checkpointing at the same instant. On an
    SQLite without the fix (Debian/Ubuntu images ship 3.46), the server keeps ONE connection, so that
    can never happen. A sensor network's load is tiny, so serialising database access costs nothing
    noticeable. SQLITE_SINGLE_CONNECTION=1 forces it, =0 turns it off."""
    mode = os.getenv("SQLITE_SINGLE_CONNECTION", "auto").lower()
    if not DATABASE_URL.startswith("sqlite") or ":memory:" in DATABASE_URL or mode in ("0", "false", "no"):
        return False
    return mode in ("1", "true", "yes") or not _sqlite_has_wal_reset_fix()


SINGLE_CONNECTION = _single_connection()
_pool_args = {"pool_size": 1, "max_overflow": 0, "pool_timeout": 30} if SINGLE_CONNECTION else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True, **_pool_args)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        """Per-connection settings: SQLite forgets these when a connection closes.
        busy_timeout makes a writer wait up to 5 s for another writer instead of failing with
        "database is locked"; foreign_keys enforces device -> reading links; FULL sync is the safe
        choice for safety records (the write volume of a sensor network is tiny)."""
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA synchronous=FULL")
        cur.close()
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
    except Exception as e:
        log.warning("Could not enable SQLite WAL mode: %s", e)

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
            "api_key_hash": "VARCHAR(64)",
            "api_key_hint": "VARCHAR(16)",
        }
        existing_cols = {col["name"] for col in inspector.get_columns("devices")}
        missing = devices_required.keys() - existing_cols

        if missing:
            with engine.begin() as conn:
                for col_name in missing:
                    conn.execute(
                        text(f"ALTER TABLE devices ADD COLUMN {col_name} {devices_required[col_name]}")
                    )


def ensure_indexes():
    """Indexes added after the first release (CREATE INDEX IF NOT EXISTS is safe to repeat)."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_readings_device_recorded ON readings (device_id, recorded_at)"))
    except Exception as e:
        log.warning("Could not create index: %s", e)


def sqlite_info() -> Dict[str, Any]:
    import sqlite3
    return {"sqlite_version": sqlite3.sqlite_version, "wal_reset_bug_fixed": _sqlite_has_wal_reset_fix(),
            "single_connection_mode": SINGLE_CONNECTION}


def backup_database(dest_dir: str) -> Dict[str, Any]:
    """Consistent online copy using SQLite's backup API (safe while the server is writing)."""
    import sqlite3
    from datetime import datetime, timezone
    if not DATABASE_URL.startswith("sqlite"):
        return {"status": "skipped", "message": "Backups here only cover SQLite; use your database's own tools."}
    src_path = DATABASE_URL.replace("sqlite:///", "", 1)
    os.makedirs(dest_dir, exist_ok=True)
    name = "aquasentry-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + ".db"
    dest_path = os.path.join(dest_dir, name)
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dest_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return {"status": "success", "file": dest_path, "size_bytes": os.path.getsize(dest_path)}


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


# ---------------------------------------------------------------------------- migrations
HEAD_BASELINE = "0001_v5_5_baseline"


def _alembic_config(connection):
    from alembic.config import Config
    cfg = Config()
    cfg.set_main_option("script_location", os.path.join(_PLATFORM_DIR, "app", "migrations"))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    cfg.attributes["connection"] = connection
    return cfg


def init_db() -> str:
    """Bring the database to the current schema and say how:
    - new database: create every table, then mark it as up to date ("created")
    - database from before migrations (v5.5 and older): old column patches, mark as the v5.5 baseline,
      then run the migrations since ("migrated")
    - database already under migrations: run any new ones ("upgraded")."""
    from alembic import command
    from . import models  # noqa: F401  (registers the tables)

    tables = set(inspect(engine).get_table_names())
    legacy = "alembic_version" not in tables and ("readings" in tables or "devices" in tables)
    if legacy:
        # The old column patches open their own connections, so run them BEFORE holding one below:
        # in single-connection mode a second connection would wait 30 s and the server would not start.
        ensure_sqlite_columns()
    with engine.begin() as conn:
        cfg = _alembic_config(conn)
        if "alembic_version" in tables:
            command.upgrade(cfg, "head")
            how = "upgraded"
        elif legacy:
            command.stamp(cfg, HEAD_BASELINE)
            command.upgrade(cfg, "head")
            how = "migrated"
        else:
            Base.metadata.create_all(bind=conn)
            command.stamp(cfg, "head")
            how = "created"
    ensure_indexes()
    if how != "upgraded":
        log.info("Database %s (schema at the latest migration).", how)
    return how


def schema_revision(db=None) -> str:
    """Pass the request's session: in single-connection mode a second connection would have to wait."""
    try:
        if db is not None:
            return db.execute(text("SELECT version_num FROM alembic_version")).scalar() or "none"
        with engine.connect() as conn:
            return conn.execute(text("SELECT version_num FROM alembic_version")).scalar() or "none"
    except Exception:
        return "none"
