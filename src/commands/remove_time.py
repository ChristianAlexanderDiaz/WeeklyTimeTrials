"""
Remove time command for the MKW Time Trial Bot.

This command allows users to remove their submitted time from a weekly trial.
This is useful if they made a mistake or want to start fresh.
"""

from typing import List
import discord
from discord import app_commands, Interaction

from .base import AutocompleteCommand, CommandError
from ..utils.validators import InputValidator, ValidationError
from ..utils.track_data import TrackManager, get_track_autocomplete_choices
from ..utils.formatters import EmbedFormatter
from ..utils.time_parser import TimeParser


class RemoveTimeCommand(AutocompleteCommand):
    """
    Command to remove a user's submitted time from a weekly trial.
    
    This command handles:
    - Track name validation with autocomplete
    - Finding trials with user submissions
    - Verifying user has a submitted time
    - Removing the time from database
    - Confirmation feedback
    """
    
    async def execute(self, interaction: Interaction, track: str) -> None:
        """
        Execute the remove time command.
        
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
        
        # Get trial for this track (any status - user might want to remove from expired trials)
        trial_data = await self._get_trial_by_track(guild_id, track_name)
        if not trial_data:
            raise CommandError(
                f"No trial found for **{track_name}**."
            )
        
        trial_id = trial_data['id']
        trial_number = trial_data['trial_number']
        trial_status = trial_data['status']
        
        # Check if user has a time for this trial
        existing_time = await self._get_user_time_for_trial(trial_id, user_id)
        if not existing_time:
            raise CommandError(
                f"You don't have a submitted time for **Weekly Time Trial #{trial_number} - {track_name}**."
            )
        
        # Check if trial allows modifications (only active trials)
        if trial_status != 'active':
            raise CommandError(
                f"Cannot remove time from **{trial_status}** trial. "
                f"Times can only be removed from active trials."
            )
        
        # Get the time that will be removed (for confirmation message)
        removed_time_ms = existing_time['time_ms']
        removed_time_str = TimeParser.format_time(removed_time_ms)
        
        # Remove the time from database
        await self._remove_user_time(trial_id, user_id)
        
        # Create success response
        embed = EmbedFormatter.create_success_embed(
            "Time Removed",
            f"Your time of **{removed_time_str}** has been removed from "
            f"**Weekly Time Trial #{trial_number} - {track_name}**.",
            "You can submit a new time using the `/save` command."
        )
        
        await self._send_response(interaction, embed=embed, ephemeral=True)
    
    async def _remove_user_time(self, trial_id: int, user_id: int) -> None:
        """
        Remove a user's time from the database.
        
        Args:
            trial_id: Trial ID
            user_id: Discord user ID
            
        Raises:
            CommandError: If removal fails
        """
        query = """
            DELETE FROM player_times 
            WHERE trial_id = %s 
                AND user_id = %s
            RETURNING id, time_ms
        """
        
        results = self._execute_query(query, (trial_id, user_id), fetch=True)
        if not results:
            raise CommandError("Failed to remove time. Please try again.")
    
    async def autocomplete_callback(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """
        Provide autocomplete choices for track names.
        
        Only shows tracks where the user has submitted a time in an active trial.
        
        Args:
            interaction: Discord interaction object
            current: Current user input
            
        Returns:
            List of autocomplete choices for tracks with user submissions
        """
        try:
            guild_id = self._validate_guild_interaction(interaction)
            user_id = self._validate_user_interaction(interaction)
            
            # Get tracks where user has submitted times in active trials
            user_tracks = await self._get_user_trial_tracks(guild_id, user_id)
            
            # Filter tracks based on user input
            if current:
                current_lower = current.lower()
                filtered_tracks = [
                    track for track in user_tracks
                    if current_lower in track.lower()
                ]
            else:
                filtered_tracks = user_tracks
            
            # Limit to 25 choices (Discord limit)
            filtered_tracks = filtered_tracks[:25]
            
            return [
                app_commands.Choice(name=track, value=track)
                for track in filtered_tracks
            ]
            
        except Exception as e:
            self.logger.error(f"Autocomplete error: {e}")
            # Fallback to all tracks if database query fails
            return [
                app_commands.Choice(name=choice['name'], value=choice['value'])
                for choice in get_track_autocomplete_choices(current)[:25]
            ]
    
    async def _get_user_trial_tracks(self, guild_id: int, user_id: int) -> List[str]:
        """
        Get list of track names where the user has submitted times in active trials.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            
        Returns:
            List of track names where user has active submissions
        """
        query = """
            SELECT DISTINCT wt.track_name
            FROM weekly_trials wt
            JOIN player_times pt ON wt.id = pt.trial_id
            WHERE wt.guild_id = %s 
                AND pt.user_id = %s
                AND wt.status = 'active'
            ORDER BY wt.track_name
        """
        
        try:
            results = self._execute_query(query, (guild_id, user_id))
            return [row['track_name'] for row in results]
        except Exception:
            # Fallback to empty list if query fails
            return []


# Command setup function for the main bot file
def setup_remove_time_command(tree: app_commands.CommandTree) -> None:
    """
    Set up the remove time command with the Discord command tree.
    
    Args:
        tree: Discord app commands tree
    """
    remove_cmd = RemoveTimeCommand()
    
    @tree.command(
        name="remove-time",
        description="Remove your submitted time from an active weekly trial"
    )
    @app_commands.describe(
        track="Select the track to remove your time from (only tracks with your submissions shown)"
    )
    async def remove_time(interaction: Interaction, track: str):
        """
        Remove your submitted time from an active weekly trial.
        
        This permanently deletes your time submission. You can submit
        a new time afterwards using the /save command.
        
        Examples:
        /remove-time track:Rainbow Road
        /remove-time track:Mario Circuit
        """
        await remove_cmd.handle_command(interaction, track=track)
    
    @remove_time.autocomplete('track')
    async def track_autocomplete(interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for track parameter - shows only tracks with user's submissions."""
        return await remove_cmd.autocomplete_callback(interaction, current)