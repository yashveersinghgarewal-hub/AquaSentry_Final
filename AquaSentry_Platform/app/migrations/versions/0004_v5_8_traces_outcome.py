"""v5.8: raw scan traces as evidence, screening outcome, censored lab results.

Revision ID: 0004_v5_8_traces_outcome
Revises: 0003_v5_7_qc_runs
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_v5_8_traces_outcome"
down_revision = "0003_v5_7_qc_runs"
branch_labels = None
depends_on = None

READING_COLS = [("screening_outcome", sa.String(24)), ("trace_id", sa.Integer()), ("analysis_version", sa.String(24)),
                ("sample_code", sa.String(64)), ("electrode_lot", sa.String(64)), ("reprocessed_from_id", sa.Integer())]
TRACE_COLS = [("device_id", sa.Integer()), ("source_type", sa.String(32)), ("checksum_sha256", sa.String(64)),
              ("raw_file_name", sa.String(128)), ("n_points", sa.Integer()), ("firmware_version", sa.String(32)),
              ("analysis_version", sa.String(24)), ("calibration_id", sa.String(64)), ("estimated_ug_l", sa.Float()),
              ("uncertainty_ug_l", sa.Float()), ("qc_status", sa.String(16)), ("qc_flags", sa.Text()),
              ("features_json", sa.Text()), ("scan_settings_json", sa.Text()), ("sample_code", sa.String(64)),
              ("uploaded_at", sa.DateTime())]
LAB_COLS = [("reporting_limit_ug_l", sa.Float()), ("qualifier", sa.String(8)), ("species", sa.String(16))]


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
    _add_missing("readings", READING_COLS)
    _add_missing("raw_voltammetry_traces", TRACE_COLS)
    _add_missing("lab_results", LAB_COLS)


def downgrade():
    for table, cols in (("lab_results", LAB_COLS), ("raw_voltammetry_traces", TRACE_COLS), ("readings", READING_COLS)):
        with op.batch_alter_table(table) as b:
            for name, _ in cols:
                b.drop_column(name)
