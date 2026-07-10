"""Phase 7.1 — Resume Library: add the resume table.

Revision ID: 005
Revises: 004
Create Date: 2026-07-10
"""

import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def _existing_tables() -> set[str]:
    bind = op.get_bind()
    result = bind.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'"))
    return {row[0] for row in result.fetchall()}


def upgrade() -> None:
    if "resume" in _existing_tables():
        return

    op.create_table(
        "resume",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("stored_filename", sa.String(), nullable=False),
        sa.Column("version_name", sa.String(), nullable=False),
        sa.Column("file_type", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("parse_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("parser_version", sa.String(), nullable=True),
        sa.Column("parse_error", sa.String(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("parsed_name", sa.String(), nullable=True),
        sa.Column("parsed_email", sa.String(), nullable=True),
        sa.Column("parsed_phone", sa.String(), nullable=True),
        sa.Column("parsed_linkedin", sa.String(), nullable=True),
        sa.Column("parsed_portfolio", sa.String(), nullable=True),
        sa.Column("parsed_skills", sa.Text(), nullable=True),
        sa.Column("parsed_companies", sa.Text(), nullable=True),
        sa.Column("parsed_job_titles", sa.Text(), nullable=True),
        sa.Column("parsed_education", sa.Text(), nullable=True),
        sa.Column("parsed_experience", sa.Text(), nullable=True),
    )
    op.create_index("ix_resume_stored_filename", "resume", ["stored_filename"])


def downgrade() -> None:
    pass
