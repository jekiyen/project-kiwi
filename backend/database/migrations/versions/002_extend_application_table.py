"""Add applied_at, interview_date, follow_up_date to application table.

Revision ID: 002
Revises: 001
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

_NEW_COLUMNS = [
    ("applied_at",      sa.DateTime(), True),
    ("interview_date",  sa.DateTime(), True),
    ("follow_up_date",  sa.DateTime(), True),
]


def _existing_columns(table: str) -> set[str]:
    bind = op.get_bind()
    result = bind.execute(sa.text(f"PRAGMA table_info({table})"))
    return {row[1] for row in result.fetchall()}


def upgrade() -> None:
    existing = _existing_columns("application")
    for col_name, col_type, nullable in _NEW_COLUMNS:
        if col_name not in existing:
            op.add_column("application", sa.Column(col_name, col_type, nullable=nullable))


def downgrade() -> None:
    pass
