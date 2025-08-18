"""
Remove medal times command for the MKW Time Trial Bot.

This command allows users to remove medal time requirements
from existing active time trial challenges.
"""

from typing import List
import logging
import discord
from discord import app_commands, Interaction

from .base import AutocompleteCommand, CommandError
from ..utils.validators import InputValidator, ValidationError
from ..utils.track_data import TrackManager, get_track_autocomplete_choices
from ..utils.formatters import EmbedFormatter

logger = logging.getLogger(__name__)


class RemoveMedalTimesCommand(AutocompleteCommand):
    """
    Command to remove medal time requirements from an active time trial challenge.
    
    This command handles:
    - Track name validation with autocomplete
    - Removing medal requirements from active trials
    - Updating live leaderboard messages
    - Confirmation messaging
    """
    
    async def execute(self, interaction: Interaction, track: str) -> None:
        """
        Execute the remove medal times command.
        
        Args:
            interaction: Discord interaction object
            track: Track name (validated via autocomplete)
        """
        guild_id = self._validate_guild_interaction(interaction)
        user_id = self._validate_user_interaction(interaction)
        
        # Validate track name
        try:
            track_name = InputValidator.validate_track_name(track, TrackManager.get_all_tracks())
        except ValidationError as e:
            raise ValidationError(e)
        
        # Check if there's an active trial for this track
        trial_data = await self._get_active_trial_by_track(guild_id, track_name)
        if not trial_data:
            raise CommandError(
                f"No active trial found for **{track_name}**. "
                f"Use `/set-challenge` to create a new challenge first."
            )
        
        # Check if the trial currently has medal requirements
        has_medals = trial_data.get('gold_time_ms') is not None
        if not has_medals:
            raise CommandError(
                f"**{track_name}** trial (#{trial_data['trial_number']}) "
                f"doesn't currently have medal requirements."
            )
        
        # Store current medal times for the response
        current_gold = trial_data['gold_time_ms']
        current_silver = trial_data['silver_time_ms']
        current_bronze = trial_data['bronze_time_ms']
        
        # Remove medal times by setting them to NULL
        updated_trial_data = await self._remove_trial_medal_times(trial_data['id'])
        
        # Update live leaderboard if it exists
        from ..utils.leaderboard_manager import update_live_leaderboard
        try:
            await update_live_leaderboard(updated_trial_data)
            logger.info(f"Updated live leaderboard for trial #{trial_data['trial_number']} after removing medal times")
        except Exception as e:
            # Don't fail the command if leaderboard update fails
            logger.error(f"Error updating live leaderboard after removing medal times: {e}")
        
        # Create success response
        embed = self._create_medal_removal_embed(
            updated_trial_data,
            (current_gold, current_silver, current_bronze)
        )
        
        await self._send_response(interaction, embed=embed, ephemeral=False)
    
    async def _remove_trial_medal_times(self, trial_id: int) -> dict:
        """
        Remove medal times from a trial in the database.
        
        Args:
            trial_id: Trial ID to update
            
        Returns:
            Updated trial data
            
        Raises:
            CommandError: If update fails
        """
        query = """
            UPDATE weekly_trials 
            SET gold_time_ms = NULL, silver_time_ms = NULL, bronze_time_ms = NULL
            WHERE id = %s
            RETURNING id, trial_number, track_name, gold_time_ms, silver_time_ms, bronze_time_ms, 
                     start_date, end_date, status, guild_id, leaderboard_channel_id, leaderboard_message_id
        """
        
        params = (trial_id,)
        results = self._execute_query(query, params, fetch=True)
        
        if not results:
            raise CommandError("Failed to remove medal times. Please try again.")
        
        return results[0]
    
    def _create_medal_removal_embed(self, trial_data: dict, removed_times: tuple) -> discord.Embed:
        """
        Create an embed for successful medal time removal.
        
        Args:
            trial_data: Updated trial information
            removed_times: Previous medal times that were removed (gold_ms, silver_ms, bronze_ms)
            
        Returns:
            discord.Embed: Formatted medal removal embed
        """
        trial_number = trial_data['trial_number']
        track_name = trial_data['track_name']
        
        embed = discord.Embed(
            title="🏁 Medal Requirements Removed",
            description=f"**Weekly Time Trial #{trial_number} - {track_name}**\n\nThis challenge no longer has medal requirements.",
            color=EmbedFormatter.COLOR_WARNING
        )
        
        # Show what was removed
        from ..utils.time_parser import TimeParser
        gold_ms, silver_ms, bronze_ms = removed_times
        
        removed_text = f"🥇 **{TimeParser.format_time(gold_ms)}**  •  🥈 **{TimeParser.format_time(silver_ms)}**  •  🥉 **{TimeParser.format_time(bronze_ms)}**"
        
        embed.add_field(
            name="🗑️ Removed Medal Requirements",
            value=removed_text,
            inline=True
        )
        
        embed.add_field(
            name="📊 Effect",
            value="Live leaderboard updated - no more medal emojis will be shown for this challenge.",
            inline=False
        )
        
        embed.add_field(
            name="💡 Note",
            value="You can add medal requirements back anytime using `/set-medal-times`.",
            inline=False
        )
        
        embed.set_footer(text="Challenge continues as a pure time trial!")
        return embed
    
    async def autocomplete_callback(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """
        Provide autocomplete choices for track names.
        
        Shows only tracks with active trials that currently have medal requirements.
        
        Args:
            interaction: Discord interaction object
            current: Current user input
            
        Returns:
            List of autocomplete choices for tracks with active trials that have medals
        """
        try:
            guild_id = self._validate_guild_interaction(interaction)
            
            # Get tracks with active trials that have medal requirements
            trials_with_medals = await self._get_active_trials_with_medals(guild_id)
            track_names_with_medals = [trial['track_name'] for trial in trials_with_medals]
            
            # Filter based on user input
            if current:
                current_lower = current.lower()
                filtered_tracks = [
                    track for track in track_names_with_medals
                    if current_lower in track.lower()
                ]
            else:
                filtered_tracks = track_names_with_medals
            
            # Limit to 25 choices (Discord limit)
            filtered_tracks = filtered_tracks[:25]
            
            return [
                app_commands.Choice(name=track, value=track)
                for track in filtered_tracks
            ]
            
        except Exception as e:
            self.logger.error(f"Autocomplete error: {e}")
            # Fallback to all tracks
            return [
                app_commands.Choice(name=choice['name'], value=choice['value'])
                for choice in get_track_autocomplete_choices(current)[:25]
            ]
    
    async def _get_active_trials_with_medals(self, guild_id: int) -> List[dict]:
        """
        Get all active trials for a guild that currently have medal requirements.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            List of active trial data with medal requirements
        """
        query = """
            SELECT id, trial_number, track_name, gold_time_ms, silver_time_ms, bronze_time_ms,
                   start_date, end_date, status, guild_id, leaderboard_channel_id, leaderboard_message_id
            FROM weekly_trials 
            WHERE guild_id = %s 
                AND status = 'active'
                AND gold_time_ms IS NOT NULL
                AND silver_time_ms IS NOT NULL
                AND bronze_time_ms IS NOT NULL
            ORDER BY trial_number DESC
        """
        
        try:
            results = self._execute_query(query, (guild_id,))
            return results
        except Exception:
            return []


# Command setup function for the main bot file
def setup_remove_medal_times_command(tree: app_commands.CommandTree) -> None:
    """
    Set up the remove medal times command with the Discord command tree.
    
    Args:
        tree: Discord app commands tree
    """
    remove_medal_cmd = RemoveMedalTimesCommand()
    
    @tree.command(
        name="remove-medal-times",
        description="Remove medal time requirements from an active challenge"
    )
    @app_commands.describe(
        track="Select the track with an active challenge that has medal requirements"
    )
    async def remove_medal_times(interaction: Interaction, track: str):
        """
        Remove medal time requirements from an active challenge.
        
        Removes all medal requirements from a challenge, converting it to a pure time trial.
        The challenge will continue to accept time submissions but won't award medals.
        
        Examples:
        /remove-medal-times track:"Rainbow Road"
        
        Requirements:
        - Challenge must be currently active
        - Challenge must currently have medal requirements
        - Updates live leaderboard automatically
        """
        await remove_medal_cmd.handle_command(interaction, track=track)
    
    @remove_medal_times.autocomplete('track')
    async def track_autocomplete(interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for track parameter - shows only tracks with active trials that have medals."""
        return await remove_medal_cmd.autocomplete_callback(interaction, current)