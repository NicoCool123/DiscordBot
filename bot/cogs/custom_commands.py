"""Custom commands cog — loads user-created slash commands from the API."""

import asyncio
from typing import Optional

import discord
from discord.ext import commands, tasks

from bot.services.logger import get_logger

logger = get_logger(__name__)


class CustomCommands(commands.Cog):
    """Dynamically registers custom slash commands from the dashboard."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # guild_id -> {command_name: command_data}
        self._commands_cache: dict[str, dict] = {}
        self._registered_commands: dict[str, discord.app_commands.Command] = {}

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Load custom commands when bot is ready."""
        logger.info("Loading custom commands for all guilds...")
        for guild in self.bot.guilds:
            await self._load_guild_commands(guild)
        self.refresh_commands.start()

    def cog_unload(self) -> None:
        self.refresh_commands.cancel()

    @tasks.loop(minutes=2)
    async def refresh_commands(self) -> None:
        """Periodically refresh custom commands from API."""
        for guild in self.bot.guilds:
            await self._load_guild_commands(guild)

    async def _load_guild_commands(self, guild: discord.Guild) -> None:
        """Fetch and register custom commands for a guild."""
        if not self.bot.api:
            return

        try:
            data = await self.bot.api.get_custom_commands(str(guild.id))
            commands_list = data.get("commands", [])
        except Exception as e:
            logger.warning(f"Failed to fetch custom commands for guild {guild.id}: {e}")
            return

        guild_id = str(guild.id)
        new_cache = {}

        for cmd_data in commands_list:
            if not cmd_data.get("enabled", True):
                continue
            name = cmd_data["name"]
            new_cache[name] = cmd_data

        # Unregister removed commands
        old_names = set(self._commands_cache.get(guild_id, {}).keys())
        new_names = set(new_cache.keys())
        removed = old_names - new_names

        for name in removed:
            key = f"{guild_id}:{name}"
            if key in self._registered_commands:
                self.bot.tree.remove_command(name, guild=guild)
                del self._registered_commands[key]

        # Register new or updated commands
        for name, cmd_data in new_cache.items():
            key = f"{guild_id}:{name}"
            old_data = self._commands_cache.get(guild_id, {}).get(name)
            if old_data == cmd_data:
                continue  # No change

            # Remove old version if exists
            if key in self._registered_commands:
                self.bot.tree.remove_command(name, guild=guild)

            # Create new command
            response_text = cmd_data["response"]
            ephemeral = cmd_data.get("ephemeral", False)
            description = cmd_data.get("description", "Custom command")

            @discord.app_commands.command(name=name, description=description)
            async def custom_callback(
                interaction: discord.Interaction,
                _response=response_text,
                _ephemeral=ephemeral,
            ):
                # Simple template substitution
                text = _response.replace("{user}", interaction.user.display_name)
                text = text.replace("{server}", interaction.guild.name if interaction.guild else "DM")
                text = text.replace("{channel}", interaction.channel.name if hasattr(interaction.channel, "name") else "DM")
                await interaction.response.send_message(text, ephemeral=_ephemeral)

            self.bot.tree.add_command(custom_callback, guild=guild)
            self._registered_commands[key] = custom_callback

        self._commands_cache[guild_id] = new_cache

        if removed or (new_names - old_names):
            try:
                await self.bot.tree.sync(guild=guild)
            except Exception as e:
                logger.warning(f"Failed to sync commands for guild {guild.id}: {e}")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(CustomCommands(bot))
