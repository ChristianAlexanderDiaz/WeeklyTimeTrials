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
        
        # Get all active trials and post their leaderboards in the new channel
        active_trials = await self._get_active_trials(guild_id)
        posted_count = 0
        
        if active_trials:
            from ..utils.leaderboard_manager import create_live_leaderboard
            
            for trial_data in active_trials:
                try:
                    leaderboard_message = await create_live_leaderboard(trial_data, channel)
                    if leaderboard_message:
                        posted_count += 1
                        logger.info(f"Posted leaderboard for trial #{trial_data['trial_number']} in {channel.name}")
                    else:
                        logger.warning(f"Failed to post leaderboard for trial #{trial_data['trial_number']}")
                except Exception as e:
                    logger.error(f"Error posting leaderboard for trial #{trial_data['trial_number']}: {e}")
        
        # Create success response
        if posted_count > 0:
            details_text = (
                f"• **{posted_count} active leaderboard(s)** posted in {channel.mention}\n"
                f"• Live leaderboards will update automatically when users submit times\n"
                f"• Future trials will also post leaderboards in {channel.mention}\n"
                f"• You can change this setting anytime with `/setleaderboardchannel`"
            )
        else:
            details_text = (
                f"• Use `/set-challenge` to create trials - leaderboards will automatically appear in {channel.mention}\n"
                f"• Live leaderboards will update when users submit times\n"
                f"• You can change this setting anytime with `/setleaderboardchannel`"
            )
        
        embed = EmbedFormatter.create_success_embed(
            "Leaderboard Channel Set",
            f"All trial leaderboards will be posted in {channel.mention}.",
            details_text
        )
        
        await self._send_response(interaction, embed=embed, ephemeral=False)
    
    async def _get_active_trials(self, guild_id: int) -> list:
        """
        Get all active trials for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            List of active trial data
        """
        query = """
            SELECT 
                id,
                trial_number,
                track_name,
                gold_time_ms,
                silver_time_ms,
                bronze_time_ms,
                start_date,
                end_date,
                status,
                guild_id,
                leaderboard_channel_id,
                leaderboard_message_id
            FROM weekly_trials 
            WHERE guild_id = %s 
                AND status = 'active'
            ORDER BY trial_number ASC
        """
        
        try:
            return self._execute_query(query, (guild_id,))
        except Exception as e:
            logger.error(f"Failed to get active trials: {e}")
            return []


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