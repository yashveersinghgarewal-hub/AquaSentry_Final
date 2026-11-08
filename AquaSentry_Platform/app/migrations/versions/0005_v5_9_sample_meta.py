"""v5.9: sample metadata on readings, spike-recovery baseline on QC runs.

Revision ID: 0005_v5_9_sample_meta
Revises: 0004_v5_8_traces_outcome
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_v5_9_sample_meta"
down_revision = "0004_v5_8_traces_outcome"
branch_labels = None
depends_on = None


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
    _add_missing("readings", [("sample_json", sa.Text())])
    _add_missing("qc_runs", [("baseline_ug_l", sa.Float())])


def downgrade():
    with op.batch_alter_table("readings") as b:
        b.drop_column("sample_json")
    with op.batch_alter_table("qc_runs") as b:
        b.drop_column("baseline_ug_l")
