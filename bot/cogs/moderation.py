"""Moderation Cog for server moderation commands."""

from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import commands, tasks
from discord.commands import SlashCommandGroup, option
from discord.ext import commands

from bot.services.logger import get_logger

logger = get_logger(__name__)


class Moderation(commands.Cog):
    """Moderation commands for server management."""

    def __init__(self, bot: commands.Bot):
        """Initialize the Moderation cog."""
        self.bot = bot

    async def cog_before_invoke(self, ctx) -> None:
        """Check if the command is enabled for this guild."""
        if ctx.guild and self.bot.api:
            cmd_name = ctx.command.qualified_name if hasattr(ctx.command, 'qualified_name') else str(ctx.command)
            config = await self.bot.api.get_command_config(str(ctx.guild.id), cmd_name)
            if not config.get("enabled", True):
                raise commands.CheckFailure(f"Command `{cmd_name}` is disabled in this server.")

    # -------------------------------------------------------------------------
    # Slash Command Group
    # -------------------------------------------------------------------------

    mod = SlashCommandGroup(
        name="mod",
        description="Moderation commands",
        default_member_permissions=discord.Permissions(moderate_members=True),
    )

    # -------------------------------------------------------------------------
    # Ban Command
    # -------------------------------------------------------------------------

    @mod.command(name="ban", description="Ban a member from the server")
    @discord.option(name="member", description="Member to ban", type=discord.Member)
    @discord.option(
        name="reason", description="Reason for the ban", default="No reason provided"
    )
    @discord.option(
        name="delete_days",
        description="Days of messages to delete (0-7)",
        min_value=0,
        max_value=7,
        default=0,
    )
    async def ban(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        reason: str,
        delete_days: int,
    ) -> None:
        """Ban a member from the server."""
        # Permission checks
        if member == ctx.author:
            await ctx.respond("You cannot ban yourself.", ephemeral=True)
            return

        if member == ctx.guild.owner:
            await ctx.respond("You cannot ban the server owner.", ephemeral=True)
            return

        if member.top_role >= ctx.author.top_role:
            await ctx.respond(
                "You cannot ban someone with an equal or higher role.",
                ephemeral=True,
            )
            return

        if member.top_role >= ctx.guild.me.top_role:
            await ctx.respond(
                "I cannot ban someone with an equal or higher role than me.",
                ephemeral=True,
            )
            return

        try:
            # Send DM to user before ban
            try:
                dm_embed = discord.Embed(
                    title=f"You have been banned from {ctx.guild.name}",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow(),
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                dm_embed.add_field(name="Moderator", value=ctx.author.mention)
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass  # User has DMs disabled

            # Execute ban
            await member.ban(
                reason=f"{reason} | Banned by {ctx.author}",
                delete_message_days=delete_days,
            )

            # Response embed
            embed = discord.Embed(
                title="Member Banned",
                color=discord.Color.red(),
                timestamp=datetime.utcnow(),
            )
            embed.add_field(name="Member", value=f"{member} ({member.id})")
            embed.add_field(name="Reason", value=reason)
            embed.add_field(name="Moderator", value=ctx.author.mention)
            embed.set_thumbnail(url=member.display_avatar.url)

            await ctx.respond(embed=embed)

            # Log to API
            if self.bot.api:
                await self.bot.api.create_audit_log(
                    action="ban",
                    resource=f"user:{member.id}",
                    user_id=ctx.author.id,
                    guild_id=ctx.guild_id,
                    details={
                        "target_id": member.id,
                        "target_name": str(member),
                        "reason": reason,
                    },
                )

            logger.info(
                f"Banned {member} from {ctx.guild.name}",
                moderator_id=ctx.author.id,
                target_id=member.id,
                reason=reason,
            )

        except discord.Forbidden:
            await ctx.respond(
                "I don't have permission to ban this member.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to ban {member}: {e}")
            await ctx.respond(f"Failed to ban member: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Kick Command
    # -------------------------------------------------------------------------

    @mod.command(name="kick", description="Kick a member from the server")
    @discord.option(name="member", description="Member to kick", type=discord.Member)
    @discord.option(
        name="reason", description="Reason for the kick", default="No reason provided"
    )
    async def kick(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        reason: str,
    ) -> None:
        """Kick a member from the server."""
        # Permission checks
        if member == ctx.author:
            await ctx.respond("You cannot kick yourself.", ephemeral=True)
            return

        if member == ctx.guild.owner:
            await ctx.respond("You cannot kick the server owner.", ephemeral=True)
            return

        if member.top_role >= ctx.author.top_role:
            await ctx.respond(
                "You cannot kick someone with an equal or higher role.",
                ephemeral=True,
            )
            return

        try:
            # Send DM to user before kick
            try:
                dm_embed = discord.Embed(
                    title=f"You have been kicked from {ctx.guild.name}",
                    color=discord.Color.orange(),
                    timestamp=datetime.utcnow(),
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                dm_embed.add_field(name="Moderator", value=ctx.author.mention)
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass

            # Execute kick
            await member.kick(reason=f"{reason} | Kicked by {ctx.author}")

            # Response embed
            embed = discord.Embed(
                title="Member Kicked",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow(),
            )
            embed.add_field(name="Member", value=f"{member} ({member.id})")
            embed.add_field(name="Reason", value=reason)
            embed.add_field(name="Moderator", value=ctx.author.mention)

            await ctx.respond(embed=embed)

            logger.info(
                f"Kicked {member} from {ctx.guild.name}",
                moderator_id=ctx.author.id,
                target_id=member.id,
                reason=reason,
            )

        except discord.Forbidden:
            await ctx.respond(
                "I don't have permission to kick this member.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to kick {member}: {e}")
            await ctx.respond(f"Failed to kick member: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Mute/Timeout Command
    # -------------------------------------------------------------------------

    @mod.command(name="mute", description="Timeout a member")
    @discord.option(name="member", description="Member to mute", type=discord.Member)
    @discord.option(
        name="duration",
        description="Duration in minutes",
        min_value=1,
        max_value=40320,  # 28 days max (Discord limit)
        default=60,
    )
    @discord.option(
        name="reason", description="Reason for the mute", default="No reason provided"
    )
    async def mute(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        duration: int,
        reason: str,
    ) -> None:
        """Timeout (mute) a member for a specified duration."""
        if member == ctx.author:
            await ctx.respond("You cannot mute yourself.", ephemeral=True)
            return

        if member == ctx.guild.owner:
            await ctx.respond("You cannot mute the server owner.", ephemeral=True)
            return

        if member.top_role >= ctx.author.top_role:
            await ctx.respond(
                "You cannot mute someone with an equal or higher role.",
                ephemeral=True,
            )
            return

        try:
            timeout_until = datetime.utcnow() + timedelta(minutes=duration)

            await member.timeout(
                timeout_until,
                reason=f"{reason} | Muted by {ctx.author}",
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
            embed.add_field(name="Moderator", value=ctx.author.mention)

            await ctx.respond(embed=embed)

            logger.info(
                f"Muted {member} for {duration_str}",
                moderator_id=ctx.author.id,
                target_id=member.id,
                duration=duration,
            )

        except discord.Forbidden:
            await ctx.respond(
                "I don't have permission to timeout this member.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to mute {member}: {e}")
            await ctx.respond(f"Failed to mute member: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Unmute Command
    # -------------------------------------------------------------------------

    @mod.command(name="unmute", description="Remove timeout from a member")
    @discord.option(
        name="member", description="Member to unmute", type=discord.Member
    )
    async def unmute(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
    ) -> None:
        """Remove timeout from a member."""
        try:
            await member.timeout(None, reason=f"Unmuted by {ctx.author}")

            embed = discord.Embed(
                title="Member Unmuted",
                color=discord.Color.green(),
                timestamp=datetime.utcnow(),
            )
            embed.add_field(name="Member", value=f"{member} ({member.id})")
            embed.add_field(name="Moderator", value=ctx.author.mention)

            await ctx.respond(embed=embed)

            logger.info(
                f"Unmuted {member}",
                moderator_id=ctx.author.id,
                target_id=member.id,
            )

        except discord.Forbidden:
            await ctx.respond(
                "I don't have permission to unmute this member.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to unmute {member}: {e}")
            await ctx.respond(f"Failed to unmute member: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Warn Command
    # -------------------------------------------------------------------------

    @mod.command(name="warn", description="Warn a member")
    @discord.option(name="member", description="Member to warn", type=discord.Member)
    @discord.option(name="reason", description="Reason for the warning")
    async def warn(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        reason: str,
    ) -> None:
        """Issue a warning to a member."""
        if member == ctx.author:
            await ctx.respond("You cannot warn yourself.", ephemeral=True)
            return

        if member.bot:
            await ctx.respond("You cannot warn bots.", ephemeral=True)
            return

        try:
            # Send DM to user
            try:
                dm_embed = discord.Embed(
                    title=f"You have received a warning in {ctx.guild.name}",
                    color=discord.Color.yellow(),
                    timestamp=datetime.utcnow(),
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                dm_embed.add_field(name="Moderator", value=ctx.author.mention)
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
            embed.add_field(name="Moderator", value=ctx.author.mention)
            embed.add_field(name="DM Sent", value="Yes" if dm_sent else "No (DMs disabled)")

            await ctx.respond(embed=embed)

            # Log to API
            if self.bot.api:
                await self.bot.api.create_audit_log(
                    action="warn",
                    resource=f"user:{member.id}",
                    user_id=ctx.author.id,
                    guild_id=ctx.guild_id,
                    details={
                        "target_id": member.id,
                        "target_name": str(member),
                        "reason": reason,
                    },
                )

            logger.info(
                f"Warned {member}",
                moderator_id=ctx.author.id,
                target_id=member.id,
                reason=reason,
            )

        except Exception as e:
            logger.error(f"Failed to warn {member}: {e}")
            await ctx.respond(f"Failed to warn member: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Clear/Purge Command
    # -------------------------------------------------------------------------

    @mod.command(name="clear", description="Delete messages from a channel")
    @discord.option(
        name="amount",
        description="Number of messages to delete",
        min_value=1,
        max_value=100,
    )
    @discord.option(
        name="user",
        description="Only delete messages from this user",
        type=discord.Member,
        default=None,
    )
    async def clear(
        self,
        ctx: discord.ApplicationContext,
        amount: int,
        user: Optional[discord.Member],
    ) -> None:
        """Delete messages from the channel."""
        await ctx.defer(ephemeral=True)

        try:
            if user:
                # Delete only messages from specific user
                def check(m):
                    return m.author == user

                deleted = await ctx.channel.purge(limit=amount, check=check)
            else:
                deleted = await ctx.channel.purge(limit=amount)

            embed = discord.Embed(
                title="Messages Cleared",
                description=f"Deleted {len(deleted)} message(s)",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow(),
            )
            if user:
                embed.add_field(name="From User", value=user.mention)

            await ctx.respond(embed=embed, ephemeral=True)

            logger.info(
                f"Cleared {len(deleted)} messages",
                moderator_id=ctx.author.id,
                channel_id=ctx.channel_id,
            )

        except discord.Forbidden:
            await ctx.respond(
                "I don't have permission to delete messages.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to clear messages: {e}")
            await ctx.respond(f"Failed to clear messages: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Slowmode Command
    # -------------------------------------------------------------------------

    @mod.command(name="slowmode", description="Set channel slowmode")
    @discord.option(
        name="seconds",
        description="Slowmode delay in seconds (0 to disable)",
        min_value=0,
        max_value=21600,  # 6 hours max
    )
    async def slowmode(
        self,
        ctx: discord.ApplicationContext,
        seconds: int,
    ) -> None:
        """Set or disable slowmode for the channel."""
        try:
            await ctx.channel.edit(slowmode_delay=seconds)

            if seconds == 0:
                await ctx.respond("Slowmode disabled.", ephemeral=True)
            else:
                await ctx.respond(
                    f"Slowmode set to {seconds} second(s).",
                    ephemeral=True,
                )

            logger.info(
                f"Slowmode set to {seconds}s",
                moderator_id=ctx.author.id,
                channel_id=ctx.channel_id,
            )

        except discord.Forbidden:
            await ctx.respond(
                "I don't have permission to modify this channel.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to set slowmode: {e}")
            await ctx.respond(f"Failed to set slowmode: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Unban Command
    # -------------------------------------------------------------------------

    @mod.command(name="unban", description="Unban a user from the server")
    @discord.option(name="user_id", description="User ID to unban")
    async def unban(
        self,
        ctx: discord.ApplicationContext,
        user_id: str,
    ) -> None:
        """Unban a user by their ID."""
        try:
            user_id_int = int(user_id)
        except ValueError:
            await ctx.respond("Invalid user ID.", ephemeral=True)
            return

        try:
            user = await self.bot.fetch_user(user_id_int)
            await ctx.guild.unban(user, reason=f"Unbanned by {ctx.author}")

            embed = discord.Embed(
                title="User Unbanned",
                color=discord.Color.green(),
                timestamp=datetime.utcnow(),
            )
            embed.add_field(name="User", value=f"{user} ({user.id})")
            embed.add_field(name="Moderator", value=ctx.author.mention)

            await ctx.respond(embed=embed)

            logger.info(
                f"Unbanned {user}",
                moderator_id=ctx.author.id,
                target_id=user.id,
            )

        except discord.NotFound:
            await ctx.respond("User not found or not banned.", ephemeral=True)
        except discord.Forbidden:
            await ctx.respond(
                "I don't have permission to unban users.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to unban user {user_id}: {e}")
            await ctx.respond(f"Failed to unban user: {e}", ephemeral=True)


def setup(bot: commands.Bot) -> None:
    """Setup function for loading the cog."""
    bot.add_cog(Moderation(bot))
