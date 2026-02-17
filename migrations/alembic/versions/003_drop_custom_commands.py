"""Drop custom_commands table.

Revision ID: 003_drop_custom_commands
Revises: 002_commands_oauth
Create Date: 2026-02-17 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_drop_custom_commands"
down_revision: Union[str, None] = "002_commands_oauth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f("ix_custom_commands_guild_id"), table_name="custom_commands")
    op.drop_table("custom_commands")


def downgrade() -> None:
    op.create_table(
        "custom_commands",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=100), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("ephemeral", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_custom_commands_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_custom_commands")),
        sa.UniqueConstraint("guild_id", "name", name="uq_custom_commands_guild_name"),
    )
    op.create_index(
        op.f("ix_custom_commands_guild_id"), "custom_commands", ["guild_id"]
    )
