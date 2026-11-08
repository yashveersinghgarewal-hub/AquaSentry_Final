"""v5.6: device sites, measurement quality fields, per-device calibrations, lab results, alert subscriptions.

Revision ID: 0002_v5_6_sites_lab_alerts
Revises: 0001_v5_5_baseline
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_v5_6_sites_lab_alerts"
down_revision = "0001_v5_5_baseline"
branch_labels = None
depends_on = None

DEVICE_COLS = [
    ("latitude", sa.Float()), ("longitude", sa.Float()), ("state", sa.String(64)), ("district", sa.String(64)),
    ("block", sa.String(64)), ("panchayat", sa.String(64)), ("village", sa.String(64)), ("source_kind", sa.String(32)),
]
READING_COLS = [
    ("arsenic_species", sa.String(16)), ("cu_peak_ua", sa.Float()), ("qc_flags", sa.String(128)),
    ("calibration_ref", sa.String(64)),
]
CAL_COLS = [
    ("device_id", sa.Integer()), ("electrode_lot", sa.String(64)), ("method", sa.String(32)),
    ("points_json", sa.Text()), ("notes", sa.Text()),
]


def _add_missing(table, cols):
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return
    have = {c["name"] for c in insp.get_columns(table)}
    todo = [(n, t) for n, t in cols if n not in have]
    if todo:
        with op.batch_alter_table(table) as b:
            for name, typ in todo:
                b.add_column(sa.Column(name, typ, nullable=True))


def upgrade():
    _add_missing("devices", DEVICE_COLS)
    _add_missing("readings", READING_COLS)
    _add_missing("calibration_records", CAL_COLS)
    tables = sa.inspect(op.get_bind()).get_table_names()
    if "lab_results" not in tables:
        op.create_table(
            "lab_results",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id"), nullable=False, index=True),
            sa.Column("reading_id", sa.Integer(), sa.ForeignKey("readings.id"), nullable=True),
            sa.Column("sample_code", sa.String(64)),
            sa.Column("sampled_at", sa.DateTime(), nullable=False),
            sa.Column("lab_name", sa.String(128)),
            sa.Column("lab_method", sa.String(32), nullable=False),
            sa.Column("arsenic_ug_l", sa.Float(), nullable=False),
            sa.Column("as3_ug_l", sa.Float()),
            sa.Column("nabl_accredited", sa.Boolean()),
            sa.Column("notes", sa.Text()),
            sa.Column("entered_at", sa.DateTime()),
        )
    if "alert_subscriptions" not in tables:
        op.create_table(
            "alert_subscriptions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("channel", sa.String(16), nullable=False),
            sa.Column("target", sa.Text(), nullable=False),
            sa.Column("target_hash", sa.String(64), nullable=False, unique=True, index=True),
            sa.Column("device_code", sa.String(64)),
            sa.Column("min_level", sa.String(16)),
            sa.Column("language", sa.String(8)),
            sa.Column("label", sa.String(64)),
            sa.Column("active", sa.Boolean()),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("last_sent_at", sa.DateTime()),
            sa.Column("last_error", sa.String(255)),
            sa.Column("failures", sa.Integer()),
        )


def downgrade():
    op.drop_table("alert_subscriptions")
    op.drop_table("lab_results")
    for table, cols in (("calibration_records", CAL_COLS), ("readings", READING_COLS), ("devices", DEVICE_COLS)):
        with op.batch_alter_table(table) as b:
            for name, _ in cols:
                b.drop_column(name)
