"""Phase 7.6 — Job Intelligence: add summary_json to job.

Stores the deterministically-generated "Kiwi Job Summary" alongside the raw
description — description is never overwritten. Existing rows are backfilled
lazily (see backend/job_summary/service.py:load_job_summary) rather than in
this migration, since generation is pure Python and happens on first read.

Revision ID: 007
Revises: 006
Create Date: 2026-07-11
"""
import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def _existing_columns(table: str) -> set[str]:
    bind = op.get_bind()
    result = bind.execute(sa.text(f"PRAGMA table_info({table})"))
    return {row[1] for row in result.fetchall()}


def upgrade() -> None:
    if "summary_json" not in _existing_columns("job"):
        with op.batch_alter_table("job") as batch_op:
            batch_op.add_column(sa.Column("summary_json", sa.Text(), nullable=True))


def downgrade() -> None:
    pass
