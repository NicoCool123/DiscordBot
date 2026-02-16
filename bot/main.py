"""Discord Bot Main Entry Point."""

import asyncio
import signal
import sys
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands

from bot.config import settings
from bot.services.logger import get_logger, setup_logging
from bot.services.api_connector import APIConnector
from bot.services.database import DatabaseService

# Setup logging
setup_logging()
logger = get_logger(__name__)


class DiscordBot(commands.Bot):
    """Custom Discord Bot class with extended functionality."""

    def __init__(self) -> None:
        """Initialize the bot with intents and configuration."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True

        super().__init__(
            command_prefix=self._get_prefix,
            intents=intents,
            help_command=commands.DefaultHelpCommand(),
        )

        self.api: Optional[APIConnector] = None
        self.db: Optional[DatabaseService] = None
        self._prefix_cache: dict[int, str] = {}

    async def _get_prefix(
        self, bot: commands.Bot, message: discord.Message
    ) -> list[str]:
        """Get dynamic prefix for a guild."""
        if message.guild is None:
            return [settings.discord_prefix]

        guild_id = message.guild.id
        if guild_id in self._prefix_cache:
            prefix = self._prefix_cache[guild_id]
        else:
            # Try to fetch from API
            try:
                if self.api:
                    guild_settings = await self.api.get_guild_settings(guild_id)
                    prefix = guild_settings.get("prefix", settings.discord_prefix)
                    self._prefix_cache[guild_id] = prefix
                else:
                    prefix = settings.discord_prefix
            except Exception as e:
                logger.warning(f"Failed to fetch prefix for guild {guild_id}: {e}")
                prefix = settings.discord_prefix

        # Always allow mention as prefix
        return commands.when_mentioned_or(prefix)(bot, message)

    async def setup_hook(self) -> None:
        """Initialize services and load cogs when bot is ready."""
        logger.info("Setting up bot services...")

        # Initialize API connector
        self.api = APIConnector(
            base_url=settings.api_url,
            api_key=settings.bot_api_key,
        )

        # Initialize database service
        self.db = DatabaseService(settings.database_url)
        await self.db.connect()

        # Load all cogs
        await self._load_cogs()

        # Set up app command error handler
        self.tree.on_error = self.on_app_command_error

        logger.info("Bot setup complete")

    async def _load_cogs(self) -> None:
        """Load all cogs from the cogs directory."""
        cogs_dir = Path(__file__).parent / "cogs"

        # Core cogs to load
        core_cogs = ["admin", "moderation", "custom_commands"]

        # Optional cogs based on settings
        if settings.rcon_enabled:
            core_cogs.append("minecraft")

        for cog_name in core_cogs:
            cog_path = cogs_dir / f"{cog_name}.py"
            if cog_path.exists():
                try:
                    await self.load_extension(f"bot.cogs.{cog_name}")
                    logger.info(f"Loaded cog: {cog_name}")
                except Exception as e:
                    logger.error(f"Failed to load cog {cog_name}: {e}")
            else:
                logger.warning(f"Cog file not found: {cog_path}")

    async def on_ready(self) -> None:
        """Called when the bot is ready."""
        logger.info(f"Bot is ready! Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")

        # Set presence
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(self.guilds)} servers | {settings.discord_prefix}help",
        )
        await self.change_presence(activity=activity)

        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Called when the bot joins a new guild."""
        logger.info(f"Joined guild: {guild.name} (ID: {guild.id})")

        # Create default settings for the guild
        if self.api:
            try:
                await self.api.create_guild_settings(
                    guild_id=guild.id,
                    prefix=settings.discord_prefix,
                )
            except Exception as e:
                logger.error(f"Failed to create settings for guild {guild.id}: {e}")

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Called when the bot leaves a guild."""
        logger.info(f"Left guild: {guild.name} (ID: {guild.id})")

        # Remove from prefix cache
        self._prefix_cache.pop(guild.id, None)

    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Global error handler for prefix commands."""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing required argument: `{error.param.name}`")
            return

        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
            return

        if isinstance(error, commands.BotMissingPermissions):
            await ctx.send("I don't have the required permissions for this command.")
            return

        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"This command is on cooldown. Try again in {error.retry_after:.1f}s"
            )
            return

        # Log unexpected errors
        logger.error(f"Command error in {ctx.command}: {error}", exc_info=error)
        await ctx.send("An unexpected error occurred. Please try again later.")

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError
    ) -> None:
        """Global error handler for slash commands."""
        if isinstance(error, discord.app_commands.CheckFailure):
            if interaction.response.is_done():
                await interaction.followup.send(
                    "You don't have permission to use this command.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "You don't have permission to use this command.",
                    ephemeral=True,
                )
            return

        logger.error(f"Slash command error: {error}", exc_info=error)
        if interaction.response.is_done():
            await interaction.followup.send(
                "An unexpected error occurred. Please try again later.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "An unexpected error occurred. Please try again later.",
                ephemeral=True,
            )

    async def close(self) -> None:
        """Clean up resources before shutdown."""
        logger.info("Shutting down bot...")

        # Close API connector
        if self.api:
            await self.api.close()

        # Close database connection
        if self.db:
            await self.db.disconnect()

        await super().close()
        logger.info("Bot shutdown complete")

    def invalidate_prefix_cache(self, guild_id: int) -> None:
        """Invalidate cached prefix for a guild."""
        self._prefix_cache.pop(guild_id, None)


# Global bot instance
bot = DiscordBot()


def handle_shutdown(signum: int, frame) -> None:
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating shutdown...")
    asyncio.create_task(bot.close())


def main() -> None:
    """Main entry point for the bot."""
    # Register signal handlers for graceful shutdown
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)

    try:
        logger.info("Starting Discord bot...")
        bot.run(settings.discord_token)
    except discord.LoginFailure:
        logger.critical("Invalid Discord token. Please check your configuration.")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
