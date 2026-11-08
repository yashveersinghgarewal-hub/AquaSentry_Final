"""Baseline: the schema as of AquaSentry v5.5.

Databases from before migrations existed are brought to this point by create_all plus the column
patches in app.database.ensure_sqlite_columns(), then stamped with this revision.

Revision ID: 0001_v5_5_baseline
Revises:
"""
revision = "0001_v5_5_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
