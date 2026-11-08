"""v5.7: check-standard / blank QC runs, reading QC status and time source.

Revision ID: 0003_v5_7_qc_runs
Revises: 0002_v5_6_sites_lab_alerts
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_v5_7_qc_runs"
down_revision = "0002_v5_6_sites_lab_alerts"
branch_labels = None
depends_on = None

READING_COLS = [("qc_status", sa.String(16)), ("time_source", sa.String(24))]


def upgrade():
    insp = sa.inspect(op.get_bind())
    tables = insp.get_table_names()
    if "readings" in tables:
        have = {c["name"] for c in insp.get_columns("readings")}
        todo = [(n, t) for n, t in READING_COLS if n not in have]
        if todo:
            with op.batch_alter_table("readings") as b:
                for name, typ in todo:
                    b.add_column(sa.Column(name, typ, nullable=True))
    if "qc_runs" not in tables:
        op.create_table(
            "qc_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("device_code", sa.String(64), nullable=False, index=True),
            sa.Column("run_type", sa.String(24), nullable=False),
            sa.Column("expected_ug_l", sa.Float()),
            sa.Column("measured_ug_l", sa.Float()),
            sa.Column("peak_current_ua", sa.Float()),
            sa.Column("recovery_pct", sa.Float()),
            sa.Column("passed", sa.Boolean(), nullable=False),
            sa.Column("detail", sa.Text()),
            sa.Column("recorded_at", sa.DateTime(), index=True),
        )


def downgrade():
    op.drop_table("qc_runs")
    with op.batch_alter_table("readings") as b:
        for name, _ in READING_COLS:
            b.drop_column(name)
