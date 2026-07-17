"""Phase 8 — Application Copilot: Application Session tracking + the
cover-letter-generated marker the Readiness Engine checks.

`Job.cover_letter_generated_at` is stamped whenever the Cover Letter prompt
is generated for that job (backend/api/v1/jobs.py::generate_job_prompt) —
Kiwi never stores the AI's actual output, only that a cover letter prompt
was prepared. `applicationsession` tracks each "Launch Application" attempt
(started/resumed/completed/cancelled) — see backend/core/application_readiness.py.

Revision ID: 009
Revises: 008
Create Date: 2026-07-16
"""
import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"
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
    if "cover_letter_generated_at" not in _existing_columns("job"):
        with op.batch_alter_table("job") as batch_op:
            batch_op.add_column(sa.Column("cover_letter_generated_at", sa.DateTime(), nullable=True))

    if "applicationsession" not in _existing_tables():
        op.create_table(
            "applicationsession",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "application_id",
                sa.Integer(),
                sa.ForeignKey("application.id"),
                nullable=False,
            ),
            sa.Column("status", sa.String(), nullable=False, server_default="started"),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("last_opened_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("resume_version", sa.String(), nullable=True),
            sa.Column("cover_letter_version", sa.String(), nullable=True),
            sa.Column("profile_version", sa.String(), nullable=True),
        )
        op.create_index(
            "ix_applicationsession_application_id",
            "applicationsession",
            ["application_id"],
        )


def downgrade() -> None:
    pass
