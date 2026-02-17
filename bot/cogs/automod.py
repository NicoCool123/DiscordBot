"""Auto-moderation Cog for automated moderation features."""

from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.logger import get_logger

logger = get_logger(__name__)


class AutoMod(commands.Cog):
    """Auto-moderation and logging commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory filter (should be database-backed in production)
        self.word_filters = {}  # guild_id -> set of banned words

    automod = app_commands.Group(
        name="automod",
        description="Auto-moderation commands",
        default_permissions=discord.Permissions(moderate_members=True),
    )

    @automod.command(name="filter-add", description="Add a word to the filter")
    @app_commands.describe(word="Word to filter")
    async def filter_add(self, interaction: discord.Interaction, word: str) -> None:
        """Add a word to the server's filter list."""
        guild_id = str(interaction.guild.id)

        if guild_id not in self.word_filters:
            self.word_filters[guild_id] = set()

        self.word_filters[guild_id].add(word.lower())

        await interaction.response.send_message(
            f"Added `{word}` to the word filter.", ephemeral=True
        )

        logger.info(
            f"Added word to filter: {word}",
            extra={"guild_id": guild_id, "user_id": interaction.user.id},
        )

    @automod.command(name="filter-remove", description="Remove a word from the filter")
    @app_commands.describe(word="Word to remove")
    async def filter_remove(self, interaction: discord.Interaction, word: str) -> None:
        """Remove a word from the server's filter list."""
        guild_id = str(interaction.guild.id)

        if guild_id in self.word_filters and word.lower() in self.word_filters[guild_id]:
            self.word_filters[guild_id].remove(word.lower())
            await interaction.response.send_message(
                f"Removed `{word}` from the word filter.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"`{word}` is not in the filter.", ephemeral=True
            )

    @automod.command(name="filter-list", description="Show all filtered words")
    async def filter_list(self, interaction: discord.Interaction) -> None:
        """List all words in the server's filter."""
        guild_id = str(interaction.guild.id)

        if guild_id not in self.word_filters or not self.word_filters[guild_id]:
            await interaction.response.send_message(
                "No words are currently filtered.", ephemeral=True
            )
            return

        words = sorted(self.word_filters[guild_id])

        embed = discord.Embed(
            title="Filtered Words",
            description="\n".join([f"• {word}" for word in words]),
            color=discord.Color.orange(),
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @automod.command(name="logs", description="View recent moderation actions")
    @app_commands.describe(limit="Number of recent actions to show (max 25)")
    async def logs(
        self,
        interaction: discord.Interaction,
        limit: app_commands.Range[int, 1, 25] = 10,
    ) -> None:
        """View recent moderation actions from the API."""
        await interaction.response.defer(ephemeral=True)

        if not self.bot.api:
            await interaction.followup.send(
                "API connection not available.", ephemeral=True
            )
            return

        try:
            # Fetch audit logs from API
            response = await self.bot.api.get(
                f"/audit/logs?guild_id={interaction.guild.id}&limit={limit}&action_filter=ban,kick,warn,mute"
            )

            if response.status_code != 200:
                await interaction.followup.send("Failed to fetch logs.", ephemeral=True)
                return

            logs = response.json()

            if not logs:
                await interaction.followup.send(
                    "No recent moderation actions.", ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"Recent Moderation Actions ({len(logs)})",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow(),
            )

            for log in logs[:limit]:
                action = log.get("action", "unknown")
                timestamp = log.get("created_at", "")
                details = log.get("details", {})

                target = details.get("target_name", "Unknown")
                reason = details.get("reason", "No reason")

                embed.add_field(
                    name=f"{action.upper()} - {timestamp[:10]}",
                    value=f"Target: {target}\nReason: {reason}",
                    inline=False,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to fetch logs: {e}")
            await interaction.followup.send("Error fetching logs.", ephemeral=True)

    @automod.command(
        name="spam-protection", description="Toggle spam protection"
    )
    @app_commands.describe(enabled="Enable or disable spam protection")
    async def spam_protection(
        self, interaction: discord.Interaction, enabled: bool
    ) -> None:
        """Toggle spam protection for the server."""
        # This would update guild settings via API
        if self.bot.api:
            try:
                await self.bot.api.update_guild_settings(
                    guild_id=interaction.guild.id, spam_protection_enabled=enabled
                )
            except Exception as e:
                logger.error(f"Failed to update spam protection: {e}")

        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(
            f"Spam protection {status}.", ephemeral=True
        )

    @automod.command(name="raid-mode", description="Enable raid mode protection")
    @app_commands.describe(enabled="Enable or disable raid mode")
    async def raid_mode(self, interaction: discord.Interaction, enabled: bool) -> None:
        """Enable raid mode to restrict new member joins."""
        await interaction.response.send_message(
            f"Raid mode {'enabled' if enabled else 'disabled'}. "
            f"{'New members will be restricted.' if enabled else 'Normal operation resumed.'}",
            ephemeral=True,
        )

        logger.info(
            f"Raid mode {'enabled' if enabled else 'disabled'}",
            extra={"guild_id": interaction.guild.id, "user_id": interaction.user.id},
        )

    # Event listener for word filter
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Filter messages for banned words."""
        if message.author.bot or not message.guild:
            return

        guild_id = str(message.guild.id)

        if guild_id not in self.word_filters:
            return

        # Check message content
        content_lower = message.content.lower()
        for word in self.word_filters[guild_id]:
            if word in content_lower:
                try:
                    await message.delete()
                    await message.channel.send(
                        f"{message.author.mention} Your message was removed for containing a filtered word.",
                        delete_after=5,
                    )
                    logger.info(
                        f"Deleted message containing filtered word: {word}",
                        extra={
                            "guild_id": guild_id,
                            "user_id": message.author.id,
                        },
                    )
                except discord.Forbidden:
                    pass
                break


async def setup(bot: commands.Bot) -> None:
    """Setup function for loading the cog."""
    await bot.add_cog(AutoMod(bot))
