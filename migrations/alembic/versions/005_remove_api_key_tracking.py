"""Remove API key usage tracking.

Revision ID: 005_remove_api_key_tracking
Revises: 004_audit_log_retention
Create Date: 2026-02-17 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005_remove_api_key_tracking"
down_revision: Union[str, None] = "004_audit_log_retention"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove usage tracking columns from api_keys."""
    op.drop_column("api_keys", "last_used_at")
    op.drop_column("api_keys", "usage_count")


def downgrade() -> None:
    """Restore usage tracking columns to api_keys."""
    op.add_column(
        "api_keys",
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "api_keys",
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
    )
