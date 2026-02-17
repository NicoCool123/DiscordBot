"""Utility Cog for general-purpose commands."""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from bot.services.logger import get_logger

logger = get_logger(__name__)


class Utility(commands.Cog):
    """General utility commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    util = app_commands.Group(
        name="util",
        description="Utility commands",
    )

    @util.command(name="serverinfo", description="Show server information")
    async def serverinfo(self, interaction: discord.Interaction) -> None:
        """Display detailed server information."""
        guild = interaction.guild

        embed = discord.Embed(
            title=f"{guild.name} Server Info",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow(),
        )

        # Server details
        embed.add_field(name="Server ID", value=guild.id, inline=True)
        embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
        embed.add_field(
            name="Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True
        )

        # Stats
        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(name="Channels", value=len(guild.channels), inline=True)
        embed.add_field(name="Roles", value=len(guild.roles), inline=True)

        # Boost info
        embed.add_field(name="Boost Level", value=guild.premium_tier, inline=True)
        embed.add_field(
            name="Boost Count", value=guild.premium_subscription_count or 0, inline=True
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        await interaction.response.send_message(embed=embed)

    @util.command(name="userinfo", description="Show user information")
    @app_commands.describe(member="User to get info about")
    async def userinfo(
        self, interaction: discord.Interaction, member: discord.Member = None
    ) -> None:
        """Display detailed user information."""
        member = member or interaction.user

        embed = discord.Embed(
            title=f"User Info - {member}",
            color=member.color,
            timestamp=datetime.utcnow(),
        )

        embed.add_field(name="User ID", value=member.id, inline=True)
        embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
        embed.add_field(name="Bot", value="Yes" if member.bot else "No", inline=True)

        embed.add_field(
            name="Created", value=member.created_at.strftime("%Y-%m-%d"), inline=True
        )
        embed.add_field(
            name="Joined", value=member.joined_at.strftime("%Y-%m-%d"), inline=True
        )

        roles = [role.mention for role in member.roles[1:]]  # Skip @everyone
        embed.add_field(
            name=f"Roles ({len(roles)})",
            value=" ".join(roles) if roles else "None",
            inline=False,
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        await interaction.response.send_message(embed=embed)

    @util.command(name="avatar", description="Show user's avatar")
    @app_commands.describe(member="User to get avatar of")
    async def avatar(
        self, interaction: discord.Interaction, member: discord.Member = None
    ) -> None:
        """Display user's avatar in full size."""
        member = member or interaction.user

        embed = discord.Embed(title=f"{member}'s Avatar", color=member.color)
        embed.set_image(url=member.display_avatar.url)

        await interaction.response.send_message(embed=embed)

    @util.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction) -> None:
        """Display bot latency and API response time."""
        await interaction.response.defer()

        # Calculate response time
        start = datetime.utcnow()
        await interaction.followup.send("Pong!")
        end = datetime.utcnow()
        response_time = (end - start).total_seconds() * 1000

        embed = discord.Embed(title="Pong!", color=discord.Color.green())
        embed.add_field(
            name="WebSocket Latency",
            value=f"{self.bot.latency * 1000:.2f}ms",
            inline=True,
        )
        embed.add_field(
            name="API Response Time", value=f"{response_time:.2f}ms", inline=True
        )

        await interaction.edit_original_response(content=None, embed=embed)

    @util.command(name="poll", description="Create a poll")
    @app_commands.describe(
        question="Poll question",
        option1="First option",
        option2="Second option",
        option3="Third option (optional)",
        option4="Fourth option (optional)",
        option5="Fifth option (optional)",
    )
    async def poll(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option3: str = None,
        option4: str = None,
        option5: str = None,
    ) -> None:
        """Create a reaction poll."""
        options = [option1, option2]
        if option3:
            options.append(option3)
        if option4:
            options.append(option4)
        if option5:
            options.append(option5)

        # Emoji reactions
        reactions = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

        embed = discord.Embed(
            title=f"📊 {question}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow(),
        )

        description = ""
        for i, option in enumerate(options):
            description += f"{reactions[i]} {option}\n"

        embed.description = description
        embed.set_footer(text=f"Poll by {interaction.user}")

        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()

        # Add reactions
        for i in range(len(options)):
            await message.add_reaction(reactions[i])

    @util.command(name="deletedata", description="Delete all your data from the bot")
    async def deletedata(self, interaction: discord.Interaction) -> None:
        """Delete all user data (GDPR right to erasure)."""
        # Create confirmation embed
        embed = discord.Embed(
            title="⚠️ Delete All Your Data",
            description=(
                "This will **permanently delete**:\n"
                "• Your user account\n"
                "• All audit logs\n"
                "• All API keys\n"
                "• All role assignments\n\n"
                "**This action cannot be undone!**\n\n"
                "To confirm, type: `DELETE MY ACCOUNT`"
            ),
            color=discord.Color.red(),
        )
        embed.set_footer(text="This is a GDPR-compliant data deletion.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Wait for confirmation message
        def check(m):
            return (
                m.author.id == interaction.user.id
                and m.channel.id == interaction.channel.id
                and m.content == "DELETE MY ACCOUNT"
            )

        try:
            await self.bot.wait_for("message", timeout=60.0, check=check)

            # User confirmed, proceed with deletion
            if not self.bot.api:
                await interaction.followup.send(
                    "❌ API connection not available. Cannot delete data.",
                    ephemeral=True,
                )
                return

            try:
                # Call API to delete account
                response = await self.bot.api.delete(
                    "/users/me",
                    params={"confirmation": "DELETE MY ACCOUNT"},
                )

                if response.status_code == 200:
                    await interaction.followup.send(
                        "✅ **All your data has been permanently deleted.**\n\n"
                        "Your account has been removed from the system. "
                        "You will need to create a new account to use the dashboard again.",
                        ephemeral=True,
                    )
                    logger.info(
                        f"User {interaction.user.id} deleted their account via Discord"
                    )
                else:
                    await interaction.followup.send(
                        f"❌ Failed to delete data: {response.text}", ephemeral=True
                    )

            except Exception as e:
                logger.error(f"Failed to delete user data: {e}")
                await interaction.followup.send(
                    "❌ An error occurred while deleting your data. Please try again or contact an administrator.",
                    ephemeral=True,
                )

        except TimeoutError:
            await interaction.followup.send(
                "⏱️ Confirmation timeout. Data deletion cancelled.", ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    """Setup function for loading the cog."""
    await bot.add_cog(Utility(bot))
