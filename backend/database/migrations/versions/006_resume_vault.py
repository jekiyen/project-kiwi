"""Phase 7.3 — Resume Vault: strip the resume table down to file metadata only.

Kiwi no longer parses resumes (no regex extraction, no AI extraction) — the
uploaded document itself is the source of truth. This drops every column
that only existed to support structured parsing, renames version_name to
filename, and adds file_size (backfilled from the actual file on disk).

Revision ID: 006
Revises: 005
Create Date: 2026-07-11
"""
import os

import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

_PARSING_COLUMNS = [
    "version_name",
    "parse_status",
    "parser_version",
    "parse_error",
    "raw_text",
    "parsed_name",
    "parsed_email",
    "parsed_phone",
    "parsed_linkedin",
    "parsed_portfolio",
    "parsed_skills",
    "parsed_companies",
    "parsed_job_titles",
    "parsed_education",
    "parsed_experience",
]


def _existing_columns(table: str) -> set[str]:
    bind = op.get_bind()
    result = bind.execute(sa.text(f"PRAGMA table_info({table})"))
    return {row[1] for row in result.fetchall()}


def upgrade() -> None:
    existing = _existing_columns("resume")

    if "filename" not in existing:
        with op.batch_alter_table("resume") as batch_op:
            batch_op.add_column(sa.Column("filename", sa.String(), nullable=True))
        if "version_name" in existing:
            op.get_bind().execute(sa.text("UPDATE resume SET filename = version_name"))

    existing = _existing_columns("resume")
    if "file_size" not in existing:
        with op.batch_alter_table("resume") as batch_op:
            batch_op.add_column(sa.Column("file_size", sa.Integer(), nullable=True, server_default="0"))

        # Backfill from the real file on disk — this table has at most a
        # handful of rows for a single-user local tool, so a direct
        # filesystem read here is simpler and safer than leaving it at 0.
        from backend.config.settings import settings

        bind = op.get_bind()
        rows = bind.execute(sa.text("SELECT id, stored_filename FROM resume")).fetchall()
        for row_id, stored_filename in rows:
            path = os.path.join(settings.resume_upload_dir, stored_filename)
            size = os.path.getsize(path) if os.path.exists(path) else 0
            bind.execute(
                sa.text("UPDATE resume SET file_size = :size WHERE id = :id"),
                {"size": size, "id": row_id},
            )

    existing = _existing_columns("resume")
    to_drop = [c for c in _PARSING_COLUMNS if c in existing]
    if to_drop:
        with op.batch_alter_table("resume") as batch_op:
            for col in to_drop:
                batch_op.drop_column(col)


def downgrade() -> None:
    pass
