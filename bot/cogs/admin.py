"""Admin Cog for bot management commands."""

import platform
import sys
from datetime import datetime
from typing import Optional

import discord
from discord import SlashCommandGroup
from discord.ext import commands, tasks

from bot.services.logger import get_logger

logger = get_logger(__name__)


class Admin(commands.Cog):
    """Administrative commands for bot management."""

    def __init__(self, bot: commands.Bot):
        """Initialize the Admin cog."""
        self.bot = bot
        self.start_time = datetime.utcnow()
        self.status_reporter.start()

    def cog_unload(self) -> None:
        """Cleanup when cog is unloaded."""
        self.status_reporter.cancel()

    # -------------------------------------------------------------------------
    # Slash Command Group
    # -------------------------------------------------------------------------

    admin = SlashCommandGroup(
        name="admin",
        description="Administrative commands",
        default_member_permissions=discord.Permissions(administrator=True),
    )

    # -------------------------------------------------------------------------
    # Status Command
    # -------------------------------------------------------------------------

    @admin.command(name="status", description="Show bot status and statistics")
    async def status(self, ctx: discord.ApplicationContext) -> None:
        """Display bot status information."""
        uptime = datetime.utcnow() - self.start_time
        uptime_str = str(uptime).split(".")[0]  # Remove microseconds

        # Calculate memory usage
        import psutil

        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024

        # Create embed
        embed = discord.Embed(
            title="Bot Status",
            color=discord.Color.green(),
            timestamp=datetime.utcnow(),
        )

        # Bot info
        embed.add_field(
            name="Bot",
            value=f"**Name:** {self.bot.user.name}\n"
            f"**ID:** {self.bot.user.id}\n"
            f"**Latency:** {self.bot.latency * 1000:.2f}ms",
            inline=True,
        )

        # Server stats
        total_users = sum(g.member_count or 0 for g in self.bot.guilds)
        embed.add_field(
            name="Statistics",
            value=f"**Servers:** {len(self.bot.guilds)}\n"
            f"**Users:** {total_users:,}\n"
            f"**Commands:** {len(self.bot.commands)}",
            inline=True,
        )

        # System info
        embed.add_field(
            name="System",
            value=f"**Python:** {sys.version.split()[0]}\n"
            f"**Discord.py:** {discord.__version__}\n"
            f"**Memory:** {memory_mb:.2f} MB",
            inline=True,
        )

        # Uptime
        embed.add_field(
            name="Uptime",
            value=f"```{uptime_str}```",
            inline=False,
        )

        embed.set_footer(text=f"Platform: {platform.system()} {platform.release()}")

        await ctx.respond(embed=embed)

    # -------------------------------------------------------------------------
    # Reload Command
    # -------------------------------------------------------------------------

    @admin.command(name="reload", description="Reload a bot cog")
    @discord.option(
        name="cog",
        description="Name of the cog to reload",
        choices=["admin", "moderation", "minecraft"],
    )
    async def reload(
        self,
        ctx: discord.ApplicationContext,
        cog: str,
    ) -> None:
        """Reload a specific cog."""
        await ctx.defer(ephemeral=True)

        cog_name = f"bot.cogs.{cog}"

        try:
            await self.bot.reload_extension(cog_name)
            logger.info(f"Reloaded cog: {cog}", user_id=ctx.author.id)

            await ctx.respond(
                f"Successfully reloaded `{cog}`",
                ephemeral=True,
            )

            # Log to API
            if self.bot.api:
                await self.bot.api.create_audit_log(
                    action="reload_cog",
                    resource=cog,
                    user_id=ctx.author.id,
                    guild_id=ctx.guild_id,
                    details={"cog_name": cog},
                )

        except commands.ExtensionNotLoaded:
            await ctx.respond(
                f"Cog `{cog}` is not loaded. Use `/admin load` instead.",
                ephemeral=True,
            )
        except commands.ExtensionNotFound:
            await ctx.respond(
                f"Cog `{cog}` not found.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to reload cog {cog}: {e}")
            await ctx.respond(
                f"Failed to reload `{cog}`: {e}",
                ephemeral=True,
            )

    # -------------------------------------------------------------------------
    # Load/Unload Commands
    # -------------------------------------------------------------------------

    @admin.command(name="load", description="Load a bot cog")
    @discord.option(
        name="cog",
        description="Name of the cog to load",
        choices=["admin", "moderation", "minecraft"],
    )
    async def load(
        self,
        ctx: discord.ApplicationContext,
        cog: str,
    ) -> None:
        """Load a specific cog."""
        await ctx.defer(ephemeral=True)

        cog_name = f"bot.cogs.{cog}"

        try:
            await self.bot.load_extension(cog_name)
            logger.info(f"Loaded cog: {cog}", user_id=ctx.author.id)
            await ctx.respond(f"Successfully loaded `{cog}`", ephemeral=True)

        except commands.ExtensionAlreadyLoaded:
            await ctx.respond(f"Cog `{cog}` is already loaded.", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to load cog {cog}: {e}")
            await ctx.respond(f"Failed to load `{cog}`: {e}", ephemeral=True)

    @admin.command(name="unload", description="Unload a bot cog")
    @discord.option(
        name="cog",
        description="Name of the cog to unload",
        choices=["moderation", "minecraft"],  # Admin cog cannot be unloaded
    )
    async def unload(
        self,
        ctx: discord.ApplicationContext,
        cog: str,
    ) -> None:
        """Unload a specific cog."""
        await ctx.defer(ephemeral=True)

        cog_name = f"bot.cogs.{cog}"

        try:
            await self.bot.unload_extension(cog_name)
            logger.info(f"Unloaded cog: {cog}", user_id=ctx.author.id)
            await ctx.respond(f"Successfully unloaded `{cog}`", ephemeral=True)

        except commands.ExtensionNotLoaded:
            await ctx.respond(f"Cog `{cog}` is not loaded.", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to unload cog {cog}: {e}")
            await ctx.respond(f"Failed to unload `{cog}`: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Sync Commands
    # -------------------------------------------------------------------------

    @admin.command(name="sync", description="Sync slash commands")
    @discord.option(
        name="scope",
        description="Sync scope",
        choices=["global", "guild"],
        default="guild",
    )
    async def sync(
        self,
        ctx: discord.ApplicationContext,
        scope: str,
    ) -> None:
        """Sync slash commands."""
        await ctx.defer(ephemeral=True)

        try:
            if scope == "global":
                synced = await self.bot.tree.sync()
                await ctx.respond(
                    f"Synced {len(synced)} commands globally.",
                    ephemeral=True,
                )
            else:
                synced = await self.bot.tree.sync(guild=ctx.guild)
                await ctx.respond(
                    f"Synced {len(synced)} commands to this guild.",
                    ephemeral=True,
                )

            logger.info(f"Synced commands ({scope})", user_id=ctx.author.id)

        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
            await ctx.respond(f"Failed to sync: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Prefix Command (Prefix-based for backwards compatibility)
    # -------------------------------------------------------------------------

    @commands.command(name="setprefix")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def setprefix(
        self,
        ctx: commands.Context,
        prefix: str,
    ) -> None:
        """Set the command prefix for this server.

        Usage: !setprefix <new_prefix>
        """
        if len(prefix) > 5:
            await ctx.send("Prefix must be 5 characters or less.")
            return

        try:
            if self.bot.api:
                await self.bot.api.update_guild_settings(
                    guild_id=ctx.guild.id,
                    prefix=prefix,
                )
            elif self.bot.db:
                await self.bot.db.set_guild_prefix(ctx.guild.id, prefix)

            # Invalidate cache
            self.bot.invalidate_prefix_cache(ctx.guild.id)

            await ctx.send(f"Prefix set to `{prefix}`")
            logger.info(
                f"Prefix changed to {prefix}",
                guild_id=ctx.guild.id,
                user_id=ctx.author.id,
            )

        except Exception as e:
            logger.error(f"Failed to set prefix: {e}")
            await ctx.send("Failed to update prefix. Please try again.")

    # -------------------------------------------------------------------------
    # Shutdown Command
    # -------------------------------------------------------------------------

    @admin.command(name="shutdown", description="Shutdown the bot")
    async def shutdown(self, ctx: discord.ApplicationContext) -> None:
        """Shutdown the bot gracefully."""
        # Check if user is bot owner
        app_info = await self.bot.application_info()
        if ctx.author.id != app_info.owner.id:
            await ctx.respond(
                "Only the bot owner can use this command.",
                ephemeral=True,
            )
            return

        await ctx.respond("Shutting down...", ephemeral=True)
        logger.info("Bot shutdown initiated", user_id=ctx.author.id)

        await self.bot.close()

    # -------------------------------------------------------------------------
    # Background Tasks
    # -------------------------------------------------------------------------

    @tasks.loop(minutes=5)
    async def status_reporter(self) -> None:
        """Report bot status to API periodically."""
        if not self.bot.is_ready() or not self.bot.api:
            return

        try:
            uptime = (datetime.utcnow() - self.start_time).total_seconds()
            total_users = sum(g.member_count or 0 for g in self.bot.guilds)

            await self.bot.api.report_status(
                guild_count=len(self.bot.guilds),
                user_count=total_users,
                latency_ms=self.bot.latency * 1000,
                uptime_seconds=uptime,
            )
        except Exception as e:
            logger.warning(f"Failed to report status: {e}")

    @status_reporter.before_loop
    async def before_status_reporter(self) -> None:
        """Wait until bot is ready before starting status reporter."""
        await self.bot.wait_until_ready()

    # -------------------------------------------------------------------------
    # Event Listeners
    # -------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Called when cog is ready."""
        logger.info("Admin cog loaded and ready")


def setup(bot: commands.Bot) -> None:
    """Setup function for loading the cog."""
    bot.add_cog(Admin(bot))
