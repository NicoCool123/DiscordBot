"""Admin Cog for bot management commands."""

import platform
import sys
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
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

    admin = app_commands.Group(
        name="admin",
        description="Administrative commands",
        default_permissions=discord.Permissions(administrator=True),
    )

    # -------------------------------------------------------------------------
    # Status Command
    # -------------------------------------------------------------------------

    @admin.command(name="status", description="Show bot status and statistics")
    async def status(self, interaction: discord.Interaction) -> None:
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

        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------------------------
    # Reload Command
    # -------------------------------------------------------------------------

    @admin.command(name="reload", description="Reload a bot cog")
    @app_commands.describe(cog="Name of the cog to reload")
    @app_commands.choices(cog=[
        app_commands.Choice(name="admin", value="admin"),
        app_commands.Choice(name="moderation", value="moderation"),
        app_commands.Choice(name="minecraft", value="minecraft"),
        app_commands.Choice(name="custom_commands", value="custom_commands"),
    ])
    async def reload(
        self,
        interaction: discord.Interaction,
        cog: app_commands.Choice[str],
    ) -> None:
        """Reload a specific cog."""
        await interaction.response.defer(ephemeral=True)

        cog_name = f"bot.cogs.{cog.value}"

        try:
            await self.bot.reload_extension(cog_name)
            logger.info(f"Reloaded cog: {cog.value}", user_id=interaction.user.id)

            await interaction.followup.send(
                f"Successfully reloaded `{cog.value}`",
                ephemeral=True,
            )

            # Log to API
            if self.bot.api:
                await self.bot.api.create_audit_log(
                    action="reload_cog",
                    resource=cog.value,
                    user_id=interaction.user.id,
                    guild_id=interaction.guild_id,
                    details={"cog_name": cog.value},
                )

        except commands.ExtensionNotLoaded:
            await interaction.followup.send(
                f"Cog `{cog.value}` is not loaded. Use `/admin load` instead.",
                ephemeral=True,
            )
        except commands.ExtensionNotFound:
            await interaction.followup.send(
                f"Cog `{cog.value}` not found.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to reload cog {cog.value}: {e}")
            await interaction.followup.send(
                f"Failed to reload `{cog.value}`: {e}",
                ephemeral=True,
            )

    # -------------------------------------------------------------------------
    # Load/Unload Commands
    # -------------------------------------------------------------------------

    @admin.command(name="load", description="Load a bot cog")
    @app_commands.describe(cog="Name of the cog to load")
    @app_commands.choices(cog=[
        app_commands.Choice(name="admin", value="admin"),
        app_commands.Choice(name="moderation", value="moderation"),
        app_commands.Choice(name="minecraft", value="minecraft"),
        app_commands.Choice(name="custom_commands", value="custom_commands"),
    ])
    async def load(
        self,
        interaction: discord.Interaction,
        cog: app_commands.Choice[str],
    ) -> None:
        """Load a specific cog."""
        await interaction.response.defer(ephemeral=True)

        cog_name = f"bot.cogs.{cog.value}"

        try:
            await self.bot.load_extension(cog_name)
            logger.info(f"Loaded cog: {cog.value}", user_id=interaction.user.id)
            await interaction.followup.send(f"Successfully loaded `{cog.value}`", ephemeral=True)

        except commands.ExtensionAlreadyLoaded:
            await interaction.followup.send(f"Cog `{cog.value}` is already loaded.", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to load cog {cog.value}: {e}")
            await interaction.followup.send(f"Failed to load `{cog.value}`: {e}", ephemeral=True)

    @admin.command(name="unload", description="Unload a bot cog")
    @app_commands.describe(cog="Name of the cog to unload")
    @app_commands.choices(cog=[
        app_commands.Choice(name="moderation", value="moderation"),
        app_commands.Choice(name="minecraft", value="minecraft"),
    ])
    async def unload(
        self,
        interaction: discord.Interaction,
        cog: app_commands.Choice[str],
    ) -> None:
        """Unload a specific cog."""
        await interaction.response.defer(ephemeral=True)

        cog_name = f"bot.cogs.{cog.value}"

        try:
            await self.bot.unload_extension(cog_name)
            logger.info(f"Unloaded cog: {cog.value}", user_id=interaction.user.id)
            await interaction.followup.send(f"Successfully unloaded `{cog.value}`", ephemeral=True)

        except commands.ExtensionNotLoaded:
            await interaction.followup.send(f"Cog `{cog.value}` is not loaded.", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to unload cog {cog.value}: {e}")
            await interaction.followup.send(f"Failed to unload `{cog.value}`: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Sync Commands
    # -------------------------------------------------------------------------

    @admin.command(name="sync", description="Sync slash commands")
    @app_commands.describe(scope="Sync scope")
    @app_commands.choices(scope=[
        app_commands.Choice(name="global", value="global"),
        app_commands.Choice(name="guild", value="guild"),
    ])
    async def sync(
        self,
        interaction: discord.Interaction,
        scope: Optional[app_commands.Choice[str]] = None,
    ) -> None:
        """Sync slash commands."""
        await interaction.response.defer(ephemeral=True)

        scope_val = scope.value if scope else "guild"

        try:
            if scope_val == "global":
                synced = await self.bot.tree.sync()
                await interaction.followup.send(
                    f"Synced {len(synced)} commands globally.",
                    ephemeral=True,
                )
            else:
                synced = await self.bot.tree.sync(guild=interaction.guild)
                await interaction.followup.send(
                    f"Synced {len(synced)} commands to this guild.",
                    ephemeral=True,
                )

            logger.info(f"Synced commands ({scope_val})", user_id=interaction.user.id)

        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
            await interaction.followup.send(f"Failed to sync: {e}", ephemeral=True)

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
    async def shutdown(self, interaction: discord.Interaction) -> None:
        """Shutdown the bot gracefully."""
        # Check if user is bot owner
        app_info = await self.bot.application_info()
        if interaction.user.id != app_info.owner.id:
            await interaction.response.send_message(
                "Only the bot owner can use this command.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message("Shutting down...", ephemeral=True)
        logger.info("Bot shutdown initiated", user_id=interaction.user.id)

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


async def setup(bot: commands.Bot) -> None:
    """Setup function for loading the cog."""
    await bot.add_cog(Admin(bot))
