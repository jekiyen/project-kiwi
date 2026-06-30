"""Add extended AI analysis fields to job table.

Revision ID: 001
Revises:
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

_NEW_COLUMNS = [
    ("ai_priority",         sa.String(),  True),
    ("ai_reasons",          sa.Text(),    True),
    ("ai_pros",             sa.Text(),    True),
    ("ai_cons",             sa.Text(),    True),
    ("ai_visa_probability", sa.Integer(), True),
    ("ai_confidence",       sa.Integer(), True),
    ("ai_provider",         sa.String(),  True),
    ("ai_model",            sa.String(),  True),
]


def _existing_columns(table: str) -> set[str]:
    bind = op.get_bind()
    result = bind.execute(sa.text(f"PRAGMA table_info({table})"))
    return {row[1] for row in result.fetchall()}


def upgrade() -> None:
    existing = _existing_columns("job")
    for col_name, col_type, nullable in _NEW_COLUMNS:
        if col_name not in existing:
            op.add_column("job", sa.Column(col_name, col_type, nullable=nullable))


def downgrade() -> None:
    # SQLite does not support DROP COLUMN in older versions.
    # Columns are left in place on downgrade; data is harmless.
    pass
