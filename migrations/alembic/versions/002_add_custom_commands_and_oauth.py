"""Add custom commands, command configs, and Discord OAuth user fields.

Revision ID: 002_commands_oauth
Revises: 001_initial
Create Date: 2026-02-07 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_commands_oauth"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === Add Discord OAuth columns to users ===
    op.add_column("users", sa.Column("discord_access_token", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("discord_avatar", sa.String(length=255), nullable=True))

    # Make password_hash nullable (Discord OAuth users have no password)
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=True)

    # === Custom commands table ===
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

    # === Command configs table ===
    op.create_table(
        "command_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.String(length=20), nullable=False),
        sa.Column("command_name", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_command_configs")),
        sa.UniqueConstraint("guild_id", "command_name", name="uq_command_configs_guild_cmd"),
    )
    op.create_index(
        op.f("ix_command_configs_guild_id"), "command_configs", ["guild_id"]
    )


def downgrade() -> None:
    op.drop_table("command_configs")
    op.drop_table("custom_commands")
    op.drop_column("users", "discord_avatar")
    op.drop_column("users", "discord_access_token")
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=False)
