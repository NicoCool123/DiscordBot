"""Add audit log retention and anonymization.

Revision ID: 004_audit_log_retention
Revises: 003_drop_custom_commands
Create Date: 2026-02-17 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_audit_log_retention"
down_revision: Union[str, None] = "003_drop_custom_commands"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add retention_days and anonymized columns to audit_logs."""
    # Add retention_days column
    op.add_column(
        "audit_logs",
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default="90"),
    )

    # Add anonymized flag
    op.add_column(
        "audit_logs",
        sa.Column("anonymized", sa.Boolean(), nullable=False, server_default="false"),
    )

    # Create index for cleanup queries
    op.create_index(
        "ix_audit_logs_created_anonymized",
        "audit_logs",
        ["created_at", "anonymized"],
    )


def downgrade() -> None:
    """Remove retention columns from audit_logs."""
    op.drop_index("ix_audit_logs_created_anonymized", table_name="audit_logs")
    op.drop_column("audit_logs", "anonymized")
    op.drop_column("audit_logs", "retention_days")
