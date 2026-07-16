"""Phase 8.0 — Application Profile: single source of truth for reusable
applicant information (personal details, work rights, professional links,
references, emergency contact, notes).

Exactly one `applicationprofile` row ever exists — the API upserts it rather
than exposing multiple records. `applicationreference` rows belong to that
profile and are replaced wholesale on every PUT. Resume data is never
duplicated here — the Resume Vault (`resume` table) remains the source of
truth for that.

Revision ID: 008
Revises: 007
Create Date: 2026-07-16
"""
import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def _existing_tables() -> set[str]:
    bind = op.get_bind()
    result = bind.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table'")
    )
    return {row[0] for row in result.fetchall()}


def upgrade() -> None:
    existing = _existing_tables()

    if "applicationprofile" not in existing:
        op.create_table(
            "applicationprofile",
            sa.Column("id", sa.Integer(), primary_key=True),
            # Personal Information
            sa.Column("full_name", sa.String(), nullable=True),
            sa.Column("preferred_name", sa.String(), nullable=True),
            sa.Column("email", sa.String(), nullable=True),
            sa.Column("phone", sa.String(), nullable=True),
            sa.Column("current_address", sa.String(), nullable=True),
            sa.Column("city", sa.String(), nullable=True),
            sa.Column("country", sa.String(), nullable=True),
            sa.Column("nationality", sa.String(), nullable=True),
            # Work Rights
            sa.Column("work_rights_current_country", sa.String(), nullable=True),
            sa.Column("visa_status", sa.String(), nullable=True),
            sa.Column("eligible_to_work_nz", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("need_sponsorship", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("driver_license", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("own_vehicle", sa.Boolean(), nullable=False, server_default=sa.false()),
            # Professional Links
            sa.Column("linkedin_url", sa.String(), nullable=True),
            sa.Column("portfolio_url", sa.String(), nullable=True),
            sa.Column("github_url", sa.String(), nullable=True),
            sa.Column("website_url", sa.String(), nullable=True),
            # Emergency Contact
            sa.Column("emergency_contact_name", sa.String(), nullable=True),
            sa.Column("emergency_contact_relationship", sa.String(), nullable=True),
            sa.Column("emergency_contact_phone", sa.String(), nullable=True),
            # Notes
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    existing = _existing_tables()
    if "applicationreference" not in existing:
        op.create_table(
            "applicationreference",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "profile_id",
                sa.Integer(),
                sa.ForeignKey("applicationprofile.id"),
                nullable=False,
            ),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("company", sa.String(), nullable=True),
            sa.Column("relationship", sa.String(), nullable=True),
            sa.Column("email", sa.String(), nullable=True),
            sa.Column("phone", sa.String(), nullable=True),
        )
        op.create_index(
            "ix_applicationreference_profile_id",
            "applicationreference",
            ["profile_id"],
        )


def downgrade() -> None:
    pass
