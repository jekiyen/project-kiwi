"""Phase 6.1 — Application Intelligence: resume/cover letter versions + timeline.

Adds resume_version and cover_letter_version columns to application, and
creates the application_event table used for per-application history.

Revision ID: 004
Revises: 003
Create Date: 2026-07-10
"""

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def _existing_columns(table: str) -> set[str]:
    bind = op.get_bind()
    result = bind.execute(sa.text(f"PRAGMA table_info({table})"))
    return {row[1] for row in result.fetchall()}


def _existing_tables() -> set[str]:
    bind = op.get_bind()
    result = bind.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'"))
    return {row[0] for row in result.fetchall()}


def upgrade() -> None:
    existing_app_cols = _existing_columns("application")
    new_app_cols = [
        ("resume_version", sa.String()),
        ("cover_letter_version", sa.String()),
    ]
    for col_name, col_type in new_app_cols:
        if col_name not in existing_app_cols:
            op.add_column("application", sa.Column(col_name, col_type, nullable=True))

    if "applicationevent" not in _existing_tables():
        op.create_table(
            "applicationevent",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("application_id", sa.Integer(), sa.ForeignKey("application.id"), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("from_status", sa.String(), nullable=True),
            sa.Column("to_status", sa.String(), nullable=True),
            sa.Column("detail", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_applicationevent_application_id", "applicationevent", ["application_id"])


def downgrade() -> None:
    pass
