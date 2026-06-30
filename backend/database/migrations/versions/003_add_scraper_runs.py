"""Add ScraperRun table and Phase 5.5 aggregate columns to Scan.

Revision ID: 003
Revises: 002
Create Date: 2026-06-30
"""

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
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
    tables = _existing_tables()

    # Create scraperrun table
    if "scraperrun" not in tables:
        op.create_table(
            "scraperrun",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("scan_id", sa.Integer(), sa.ForeignKey("scan.id"), nullable=False),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="success"),
            sa.Column("jobs_found", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("jobs_inserted", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duplicates_skipped", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("errors", sa.String(), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_scraperrun_scan_id", "scraperrun", ["scan_id"])

    # Add new aggregate columns to scan (idempotent)
    existing_scan_cols = _existing_columns("scan")
    new_scan_cols = [
        ("total_duplicates", sa.Integer(), "0"),
        ("total_errors", sa.Integer(), "0"),
        ("duration_ms", sa.Integer(), None),
    ]
    for col_name, col_type, default in new_scan_cols:
        if col_name not in existing_scan_cols:
            op.add_column(
                "scan",
                sa.Column(col_name, col_type, nullable=True, server_default=default),
            )


def downgrade() -> None:
    pass
