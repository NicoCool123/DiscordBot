"""Minecraft RCON Integration Cog."""

import asyncio
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks
from mcrcon import MCRcon, MCRconException

from bot.config import settings
from bot.services.logger import get_logger

logger = get_logger(__name__)


class Minecraft(commands.Cog):
    """Minecraft server integration via RCON."""

    def __init__(self, bot: commands.Bot):
        """Initialize the Minecraft cog."""
        self.bot = bot
        self.rcon_host = settings.rcon_host
        self.rcon_port = settings.rcon_port
        self.rcon_password = settings.rcon_password
        self._last_status: Optional[dict] = None

        # Start status checker if RCON is enabled
        if settings.rcon_enabled:
            self.status_checker.start()

    def cog_unload(self) -> None:
        """Cleanup when cog is unloaded."""
        self.status_checker.cancel()

    def _execute_rcon(self, command: str) -> str:
        """Execute an RCON command.

        Args:
            command: Command to execute

        Returns:
            Command response

        Raises:
            MCRconException: If connection fails
        """
        with MCRcon(
            self.rcon_host,
            self.rcon_password,
            port=self.rcon_port,
        ) as mcr:
            return mcr.command(command)

    # -------------------------------------------------------------------------
    # Slash Command Group
    # -------------------------------------------------------------------------

    mc = app_commands.Group(
        name="mc",
        description="Minecraft server commands",
        default_permissions=discord.Permissions(administrator=True),
    )

    # -------------------------------------------------------------------------
    # Status Command
    # -------------------------------------------------------------------------

    @mc.command(name="status", description="Get Minecraft server status")
    async def status(self, interaction: discord.Interaction) -> None:
        """Get the current Minecraft server status."""
        await interaction.response.defer()

        try:
            # Get player list
            list_response = await asyncio.to_thread(self._execute_rcon, "list")

            # Parse player count (format: "There are X of Y players online: ...")
            parts = list_response.split(":")
            count_part = parts[0] if parts else list_response

            # Get TPS
            tps_response = ""
            try:
                # This command might not work on all server types
                tps_response = await asyncio.to_thread(self._execute_rcon, "forge tps")
            except Exception:
                try:
                    tps_response = await asyncio.to_thread(self._execute_rcon, "tps")
                except Exception:
                    tps_response = "TPS command not available"

            embed = discord.Embed(
                title="Minecraft Server Status",
                color=discord.Color.green(),
            )

            embed.add_field(
                name="Server",
                value=f"`{self.rcon_host}:{self.rcon_port}`",
                inline=True,
            )
            embed.add_field(
                name="Status",
                value="Online",
                inline=True,
            )
            embed.add_field(
                name="Players",
                value=count_part.strip(),
                inline=False,
            )

            if len(parts) > 1 and parts[1].strip():
                embed.add_field(
                    name="Online Players",
                    value=parts[1].strip() or "None",
                    inline=False,
                )

            if tps_response and "not available" not in tps_response:
                embed.add_field(
                    name="Server TPS",
                    value=f"```{tps_response[:500]}```",
                    inline=False,
                )

            await interaction.followup.send(embed=embed)

            # Cache status
            self._last_status = {
                "online": True,
                "players": list_response,
                "tps": tps_response,
            }

            logger.info("Minecraft status checked", user_id=interaction.user.id)

        except MCRconException as e:
            embed = discord.Embed(
                title="Minecraft Server Status",
                color=discord.Color.red(),
            )
            embed.add_field(name="Status", value="Offline / Unreachable")
            embed.add_field(name="Error", value=str(e)[:200])

            await interaction.followup.send(embed=embed)

            self._last_status = {"online": False, "error": str(e)}

            logger.warning(f"Minecraft RCON connection failed: {e}")

        except Exception as e:
            logger.error(f"Failed to get Minecraft status: {e}")
            await interaction.followup.send(f"Failed to get server status: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Players Command
    # -------------------------------------------------------------------------

    @mc.command(name="players", description="List online players")
    async def players(self, interaction: discord.Interaction) -> None:
        """List all online players."""
        await interaction.response.defer()

        try:
            response = await asyncio.to_thread(self._execute_rcon, "list")

            embed = discord.Embed(
                title="Online Players",
                description=response,
                color=discord.Color.blue(),
            )

            await interaction.followup.send(embed=embed)

        except MCRconException as e:
            await interaction.followup.send(
                f"Failed to connect to server: {e}",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to list players: {e}")
            await interaction.followup.send(f"Failed to list players: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Command Execution
    # -------------------------------------------------------------------------

    @mc.command(name="command", description="Execute a Minecraft command")
    @app_commands.describe(cmd="Command to execute (without /)")
    async def command(
        self,
        interaction: discord.Interaction,
        cmd: str,
    ) -> None:
        """Execute a command on the Minecraft server."""
        await interaction.response.defer(ephemeral=True)

        # Basic command sanitization - block dangerous commands
        dangerous_commands = ["stop", "restart", "shutdown", "op", "deop", "ban-ip"]
        cmd_lower = cmd.lower().strip()

        for dangerous in dangerous_commands:
            if cmd_lower.startswith(dangerous):
                await interaction.followup.send(
                    f"Command `{dangerous}` is not allowed via Discord.",
                    ephemeral=True,
                )
                return

        try:
            response = await asyncio.to_thread(self._execute_rcon, cmd)

            # Log command execution
            if self.bot.api:
                await self.bot.api.create_audit_log(
                    action="minecraft_command",
                    resource="rcon",
                    user_id=interaction.user.id,
                    guild_id=interaction.guild_id,
                    details={
                        "command": cmd,
                        "response": response[:500],
                    },
                )

            embed = discord.Embed(
                title="Command Executed",
                color=discord.Color.green(),
            )
            embed.add_field(name="Command", value=f"`{cmd}`", inline=False)

            # Truncate response if too long
            if len(response) > 1000:
                response = response[:1000] + "..."

            embed.add_field(
                name="Response",
                value=f"```{response or 'No output'}```",
                inline=False,
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(
                f"Minecraft command executed: {cmd}",
                user_id=interaction.user.id,
                command=cmd,
            )

        except MCRconException as e:
            await interaction.followup.send(
                f"Failed to execute command: {e}",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to execute Minecraft command: {e}")
            await interaction.followup.send(f"Failed to execute command: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Say Command
    # -------------------------------------------------------------------------

    @mc.command(name="say", description="Send a message to the Minecraft server")
    @app_commands.describe(message="Message to send")
    async def say(
        self,
        interaction: discord.Interaction,
        message: str,
    ) -> None:
        """Send a message to the Minecraft server chat."""
        await interaction.response.defer()

        # Sanitize message
        safe_message = message.replace("\\", "\\\\").replace('"', '\\"')

        try:
            # Use tellraw for better formatting
            cmd = f'say [Discord] {interaction.user.name}: {safe_message}'
            await asyncio.to_thread(self._execute_rcon, cmd)

            await interaction.followup.send("Message sent to Minecraft server.")

            logger.info(
                f"Message sent to Minecraft: {message[:50]}",
                user_id=interaction.user.id,
            )

        except MCRconException as e:
            await interaction.followup.send(
                f"Failed to send message: {e}",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Failed to send Minecraft message: {e}")
            await interaction.followup.send(f"Failed to send message: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Whitelist Commands
    # -------------------------------------------------------------------------

    @mc.command(name="whitelist-add", description="Add a player to the whitelist")
    @app_commands.describe(player="Player name to add")
    async def whitelist_add(
        self,
        interaction: discord.Interaction,
        player: str,
    ) -> None:
        """Add a player to the server whitelist."""
        await interaction.response.defer(ephemeral=True)

        try:
            response = await asyncio.to_thread(self._execute_rcon, f"whitelist add {player}")

            embed = discord.Embed(
                title="Whitelist Updated",
                color=discord.Color.green(),
            )
            embed.add_field(name="Action", value="Add")
            embed.add_field(name="Player", value=player)
            embed.add_field(name="Result", value=response, inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(f"Added {player} to whitelist", user_id=interaction.user.id)

        except MCRconException as e:
            await interaction.followup.send(f"Failed: {e}", ephemeral=True)

    @mc.command(name="whitelist-remove", description="Remove a player from the whitelist")
    @app_commands.describe(player="Player name to remove")
    async def whitelist_remove(
        self,
        interaction: discord.Interaction,
        player: str,
    ) -> None:
        """Remove a player from the server whitelist."""
        await interaction.response.defer(ephemeral=True)

        try:
            response = await asyncio.to_thread(self._execute_rcon, f"whitelist remove {player}")

            embed = discord.Embed(
                title="Whitelist Updated",
                color=discord.Color.orange(),
            )
            embed.add_field(name="Action", value="Remove")
            embed.add_field(name="Player", value=player)
            embed.add_field(name="Result", value=response, inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(f"Removed {player} from whitelist", user_id=interaction.user.id)

        except MCRconException as e:
            await interaction.followup.send(f"Failed: {e}", ephemeral=True)

    # -------------------------------------------------------------------------
    # Background Tasks
    # -------------------------------------------------------------------------

    @tasks.loop(minutes=5)
    async def status_checker(self) -> None:
        """Periodically check server status and report to API."""
        if not self.bot.is_ready():
            return

        try:
            list_response = await asyncio.to_thread(self._execute_rcon, "list")
            online = True
        except Exception:
            online = False
            list_response = ""

        # Report to API if available
        if self.bot.api:
            try:
                await self.bot.api.post(
                    "/minecraft/status/report",
                    data={
                        "online": online,
                        "players": list_response,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to report Minecraft status: {e}")

    @status_checker.before_loop
    async def before_status_checker(self) -> None:
        """Wait until bot is ready."""
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    """Setup function for loading the cog."""
    if settings.rcon_enabled:
        await bot.add_cog(Minecraft(bot))
        logger.info("Minecraft cog loaded (RCON enabled)")
    else:
        logger.info("Minecraft cog not loaded (RCON disabled)")
