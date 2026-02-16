"""Moderation Cog for server moderation commands."""

from datetime import datetime, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.logger import get_logger

logger = get_logger(__name__)


class Moderation(commands.Cog):
    """Moderation commands for server management."""

    def __init__(self, bot: commands.Bot):
        """Initialize the Moderation cog."""
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if the command is enabled for this guild."""
        if interaction.guild and self.bot.api:
            cmd_name = interaction.command.qualified_name if interaction.command else "unknown"
            config = await self.bot.api.get_command_config(str(interaction.guild.id), cmd_name)
            if not config.get("enabled", True):
                await interaction.response.send_message(
                    f"Command `{cmd_name}` is disabled in this server.",
                    ephemeral=True,
                )
                return False
        return True

    # -------------------------------------------------------------------------
    # Slash Command Group
    # -------------------------------------------------------------------------

    mod = app_commands.Group(
        name="mod",
        description="Moderation commands",
        default_permissions=discord.Permissions(moderate_members=True),
    )

    # -------------------------------------------------------------------------
    # Ban Command
    # -------------------------------------------------------------------------

    @mod.command(name="ban", description="Ban a member from the server")
    @app_commands.describe(
        member="Member to ban",
        reason="Reason for the ban",
        delete_days="Days of messages to delete (0-7)",
    )
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
        delete_days: app_commands.Range[int, 0, 7] = 0,
    ) -> None:
        """Ban a member from the server."""
        # Permission checks
        if member == interaction.user:
            await interaction.response.send_message("You cannot ban yourself.", ephemeral=True)
            return

        if member == interaction.guild.owner:
            await interaction.response.send_message("You cannot ban the server owner.", ephemeral=True)
            return

        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message(
                "You cannot ban someone with an equal or higher role.",
                ephemeral=True,
            )
            return

        if member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                "I cannot ban someone with an equal or higher role than me.",
                ephemeral=True,
            )
            return

        try:
            # Send DM to user before ban
            try:
                dm_embed = discord.Embed(
                    title=f"You have been banned from {interaction.guild.name}",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow(),
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                dm_embed.add_field(name="Moderator", value=interaction.user.mention)
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass  # User has DMs disabled

            # Execute ban
            await member.ban(
                reason=f"{reason} | Banned by {interaction.user}",
                delete_message_seconds=delete_days * 86400,
            )

            # Response embed
            embed = discord.Embed(
                title="Member Banned",
                color=discord.Color.red(),
                timestamp=datetime.utcnow(),
            )
            embed.add_field(name="Member", value=f"{member} ({member.id})")
            embed.add_field(name="Reason", value=reason)
            embed.add_field(name="Moderator", value=interaction.user.mention)
            embed.set_thumbnail(url=member.display_avatar.url)

            await interaction.response.send_message(embed=embed)

            # Log to API
            if self.bot.api:
                await self.bot.api.create_audit_log(
                    action="ban",
                    resource=f"user:{member.id}",
                    user_id=interaction.user.id,
                    guild_id=interaction.guild_id,
                    details={
                        "target_id": member.id,
                        "target_name": str(member),
                        "reason": reason,
                    },
                )

            logger.info(
                f"Banned {member} from {interaction.guild.name}",
                moderator_id=interaction.user.id,
                target_id=member.id,
                reason=reason,
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to ban this member.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to ban {member}: {e}")
            await interaction.response.send_message(f"Failed to ban member: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Kick Command
    # -------------------------------------------------------------------------

    @mod.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(
        member="Member to kick",
        reason="Reason for the kick",
    )
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ) -> None:
        """Kick a member from the server."""
        # Permission checks
        if member == interaction.user:
            await interaction.response.send_message("You cannot kick yourself.", ephemeral=True)
            return

        if member == interaction.guild.owner:
            await interaction.response.send_message("You cannot kick the server owner.", ephemeral=True)
            return

        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message(
                "You cannot kick someone with an equal or higher role.",
                ephemeral=True,
            )
            return

        if member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                "I cannot kick someone with an equal or higher role than me.",
                ephemeral=True,
            )
            return

        try:
            # Send DM to user before kick
            try:
                dm_embed = discord.Embed(
                    title=f"You have been kicked from {interaction.guild.name}",
                    color=discord.Color.orange(),
                    timestamp=datetime.utcnow(),
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                dm_embed.add_field(name="Moderator", value=interaction.user.mention)
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass

            # Execute kick
            await member.kick(reason=f"{reason} | Kicked by {interaction.user}")

            # Response embed
            embed = discord.Embed(
                title="Member Kicked",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow(),
            )
            embed.add_field(name="Member", value=f"{member} ({member.id})")
            embed.add_field(name="Reason", value=reason)
            embed.add_field(name="Moderator", value=interaction.user.mention)

            await interaction.response.send_message(embed=embed)

            logger.info(
                f"Kicked {member} from {interaction.guild.name}",
                moderator_id=interaction.user.id,
                target_id=member.id,
                reason=reason,
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to kick this member.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to kick {member}: {e}")
            await interaction.response.send_message(f"Failed to kick member: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Mute/Timeout Command
    # -------------------------------------------------------------------------

    @mod.command(name="mute", description="Timeout a member")
    @app_commands.describe(
        member="Member to mute",
        duration="Duration in minutes",
        reason="Reason for the mute",
    )
    async def mute(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration: app_commands.Range[int, 1, 40320] = 60,
        reason: str = "No reason provided",
    ) -> None:
        """Timeout (mute) a member for a specified duration."""
        if member == interaction.user:
            await interaction.response.send_message("You cannot mute yourself.", ephemeral=True)
            return

        if member == interaction.guild.owner:
            await interaction.response.send_message("You cannot mute the server owner.", ephemeral=True)
            return

        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message(
                "You cannot mute someone with an equal or higher role.",
                ephemeral=True,
            )
            return

        try:
            await member.timeout(
                timedelta(minutes=duration),
                reason=f"{reason} | Muted by {interaction.user}",
            )

            # Format duration string
            if duration >= 1440:
                duration_str = f"{duration // 1440} day(s)"
            elif duration >= 60:
                duration_str = f"{duration // 60} hour(s)"
            else:
                duration_str = f"{duration} minute(s)"

            embed = discord.Embed(
                title="Member Muted",
                color=discord.Color.gold(),
                timestamp=datetime.utcnow(),
            )
            embed.add_field(name="Member", value=f"{member} ({member.id})")
            embed.add_field(name="Duration", value=duration_str)
            embed.add_field(name="Reason", value=reason)
            embed.add_field(name="Moderator", value=interaction.user.mention)

            await interaction.response.send_message(embed=embed)

            logger.info(
                f"Muted {member} for {duration_str}",
                moderator_id=interaction.user.id,
                target_id=member.id,
                duration=duration,
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to timeout this member.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to mute {member}: {e}")
            await interaction.response.send_message(f"Failed to mute member: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Unmute Command
    # -------------------------------------------------------------------------

    @mod.command(name="unmute", description="Remove timeout from a member")
    @app_commands.describe(member="Member to unmute")
    async def unmute(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ) -> None:
        """Remove timeout from a member."""
        try:
            await member.timeout(None, reason=f"Unmuted by {interaction.user}")

            embed = discord.Embed(
                title="Member Unmuted",
                color=discord.Color.green(),
                timestamp=datetime.utcnow(),
            )
            embed.add_field(name="Member", value=f"{member} ({member.id})")
            embed.add_field(name="Moderator", value=interaction.user.mention)

            await interaction.response.send_message(embed=embed)

            logger.info(
                f"Unmuted {member}",
                moderator_id=interaction.user.id,
                target_id=member.id,
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to unmute this member.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to unmute {member}: {e}")
            await interaction.response.send_message(f"Failed to unmute member: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Warn Command
    # -------------------------------------------------------------------------

    @mod.command(name="warn", description="Warn a member")
    @app_commands.describe(
        member="Member to warn",
        reason="Reason for the warning",
    )
    async def warn(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
    ) -> None:
        """Issue a warning to a member."""
        if member == interaction.user:
            await interaction.response.send_message("You cannot warn yourself.", ephemeral=True)
            return

        if member.bot:
            await interaction.response.send_message("You cannot warn bots.", ephemeral=True)
            return

        try:
            # Send DM to user
            try:
                dm_embed = discord.Embed(
                    title=f"You have received a warning in {interaction.guild.name}",
                    color=discord.Color.yellow(),
                    timestamp=datetime.utcnow(),
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                dm_embed.add_field(name="Moderator", value=interaction.user.mention)
                await member.send(embed=dm_embed)
                dm_sent = True
            except discord.Forbidden:
                dm_sent = False

            # Response embed
            embed = discord.Embed(
                title="Warning Issued",
                color=discord.Color.yellow(),
                timestamp=datetime.utcnow(),
            )
            embed.add_field(name="Member", value=f"{member} ({member.id})")
            embed.add_field(name="Reason", value=reason)
            embed.add_field(name="Moderator", value=interaction.user.mention)
            embed.add_field(name="DM Sent", value="Yes" if dm_sent else "No (DMs disabled)")

            await interaction.response.send_message(embed=embed)

            # Log to API
            if self.bot.api:
                await self.bot.api.create_audit_log(
                    action="warn",
                    resource=f"user:{member.id}",
                    user_id=interaction.user.id,
                    guild_id=interaction.guild_id,
                    details={
                        "target_id": member.id,
                        "target_name": str(member),
                        "reason": reason,
                    },
                )

            logger.info(
                f"Warned {member}",
                moderator_id=interaction.user.id,
                target_id=member.id,
                reason=reason,
            )

        except Exception as e:
            logger.error(f"Failed to warn {member}: {e}")
            await interaction.response.send_message(f"Failed to warn member: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Clear/Purge Command
    # -------------------------------------------------------------------------

    @mod.command(name="clear", description="Delete messages from a channel")
    @app_commands.describe(
        amount="Number of messages to delete",
        user="Only delete messages from this user",
    )
    async def clear(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100],
        user: Optional[discord.Member] = None,
    ) -> None:
        """Delete messages from the channel."""
        await interaction.response.defer(ephemeral=True)

        try:
            if user:
                # Delete only messages from specific user
                def check(m):
                    return m.author == user

                deleted = await interaction.channel.purge(limit=amount, check=check)
            else:
                deleted = await interaction.channel.purge(limit=amount)

            embed = discord.Embed(
                title="Messages Cleared",
                description=f"Deleted {len(deleted)} message(s)",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow(),
            )
            if user:
                embed.add_field(name="From User", value=user.mention)

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(
                f"Cleared {len(deleted)} messages",
                moderator_id=interaction.user.id,
                channel_id=interaction.channel.id,
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have permission to delete messages.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to clear messages: {e}")
            await interaction.followup.send(f"Failed to clear messages: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Slowmode Command
    # -------------------------------------------------------------------------

    @mod.command(name="slowmode", description="Set channel slowmode")
    @app_commands.describe(seconds="Slowmode delay in seconds (0 to disable)")
    async def slowmode(
        self,
        interaction: discord.Interaction,
        seconds: app_commands.Range[int, 0, 21600],
    ) -> None:
        """Set or disable slowmode for the channel."""
        try:
            await interaction.channel.edit(slowmode_delay=seconds)

            if seconds == 0:
                await interaction.response.send_message("Slowmode disabled.", ephemeral=True)
            else:
                await interaction.response.send_message(
                    f"Slowmode set to {seconds} second(s).",
                    ephemeral=True,
                )

            logger.info(
                f"Slowmode set to {seconds}s",
                moderator_id=interaction.user.id,
                channel_id=interaction.channel.id,
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to modify this channel.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to set slowmode: {e}")
            await interaction.response.send_message(f"Failed to set slowmode: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Unban Command
    # -------------------------------------------------------------------------

    @mod.command(name="unban", description="Unban a user from the server")
    @app_commands.describe(user_id="User ID to unban")
    async def unban(
        self,
        interaction: discord.Interaction,
        user_id: str,
    ) -> None:
        """Unban a user by their ID."""
        try:
            user_id_int = int(user_id)
        except ValueError:
            await interaction.response.send_message("Invalid user ID.", ephemeral=True)
            return

        try:
            user = await self.bot.fetch_user(user_id_int)
            await interaction.guild.unban(user, reason=f"Unbanned by {interaction.user}")

            embed = discord.Embed(
                title="User Unbanned",
                color=discord.Color.green(),
                timestamp=datetime.utcnow(),
            )
            embed.add_field(name="User", value=f"{user} ({user.id})")
            embed.add_field(name="Moderator", value=interaction.user.mention)

            await interaction.response.send_message(embed=embed)

            logger.info(
                f"Unbanned {user}",
                moderator_id=interaction.user.id,
                target_id=user.id,
            )

        except discord.NotFound:
            await interaction.response.send_message("User not found or not banned.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to unban users.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to unban user {user_id}: {e}")
            await interaction.response.send_message(f"Failed to unban user: {e}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Setup function for loading the cog."""
    await bot.add_cog(Moderation(bot))
