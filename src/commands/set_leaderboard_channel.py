"""
Set leaderboard channel command for the MKW Time Trial Bot.

This command allows server admins to set a default channel where all
live leaderboard messages will be posted automatically.
"""

from typing import List
import logging
import discord
from discord import app_commands, Interaction

from .base import BaseCommand, CommandError
from ..utils.guild_settings import set_leaderboard_channel
from ..utils.formatters import EmbedFormatter

logger = logging.getLogger(__name__)


class SetLeaderboardChannelCommand(BaseCommand):
    """
    Command to set the default leaderboard channel for a server.
    
    This command handles:
    - Channel validation and permission checking
    - Storing the channel preference in the database
    - Providing clear feedback about the configuration
    """
    
    async def execute(self, interaction: Interaction, channel: discord.TextChannel) -> None:
        """
        Execute the set leaderboard channel command.
        
        Args:
            interaction: Discord interaction object
            channel: Target channel for leaderboard messages
        """
        guild_id = self._validate_guild_interaction(interaction)
        
        # Validate that the bot has necessary permissions in the target channel
        bot_member = interaction.guild.me
        permissions = channel.permissions_for(bot_member)
        
        missing_permissions = []
        if not permissions.send_messages:
            missing_permissions.append("Send Messages")
        if not permissions.embed_links:
            missing_permissions.append("Embed Links")
        if not permissions.read_message_history:
            missing_permissions.append("Read Message History")
        
        if missing_permissions:
            missing_perms_text = ", ".join(missing_permissions)
            raise CommandError(
                f"I don't have the required permissions in {channel.mention}. "
                f"Please grant me: **{missing_perms_text}**"
            )
        
        # Check if user has manage channels permission (admin check)
        if not interaction.user.guild_permissions.manage_channels:
            raise CommandError(
                "You need the **Manage Channels** permission to set the leaderboard channel."
            )
        
        # Save the channel preference
        success = await set_leaderboard_channel(guild_id, channel.id)
        
        if not success:
            raise CommandError(
                "Failed to save leaderboard channel setting. Please try again."
            )
        
        # Create success response
        embed = EmbedFormatter.create_success_embed(
            "Leaderboard Channel Set",
            f"All future trial leaderboards will be posted in {channel.mention}.",
            f"• Use `/set-challenge` to create trials - leaderboards will automatically appear in {channel.mention}\n"
            f"• Live leaderboards will update when users submit times\n"
            f"• You can change this setting anytime with `/setleaderboardchannel`"
        )
        
        await self._send_response(interaction, embed=embed, ephemeral=False)


# Command setup function for the main bot file
def setup_set_leaderboard_channel_command(tree: app_commands.CommandTree) -> None:
    """
    Set up the set leaderboard channel command with the Discord command tree.
    
    Args:
        tree: Discord app commands tree
    """
    set_channel_cmd = SetLeaderboardChannelCommand()
    
    @tree.command(
        name="setleaderboardchannel",
        description="Set the default channel for live leaderboard messages"
    )
    @app_commands.describe(
        channel="Channel where all leaderboard messages should be posted"
    )
    async def set_leaderboard_channel_cmd(interaction: Interaction, channel: discord.TextChannel):
        """
        Set the default channel for live leaderboard messages.
        
        This sets a server-wide preference for where live leaderboards
        should be posted. All future /set-challenge commands will
        automatically post their leaderboards in this channel.
        
        Requirements:
        - You must have "Manage Channels" permission
        - Bot must have "Send Messages" and "Embed Links" permissions in the target channel
        
        Examples:
        /setleaderboardchannel channel:#leaderboards
        /setleaderboardchannel channel:#time-trials
        
        Benefits:
        • Set once, works for all future trials
        • Clean separation of leaderboards from other content
        • No need to specify channel in every /set-challenge command
        """
        await set_channel_cmd.handle_command(interaction, channel=channel)