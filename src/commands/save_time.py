"""
Save time command for the MKW Time Trial Bot.

This command allows users to submit their time for an active weekly trial.
It includes validation, duplicate checking, and improvement tracking.
"""

from typing import List, Optional, Dict, Any
import discord
from discord import app_commands, Interaction

from .base import AutocompleteCommand, CommandError
from ..utils.validators import InputValidator, ValidationError
from ..utils.time_parser import TimeParser, TimeFormatError
from ..utils.track_data import TrackManager, get_track_autocomplete_choices
from ..utils.formatters import EmbedFormatter
from ..utils.user_utils import get_display_name


class SaveTimeCommand(AutocompleteCommand):
    """
    Command to save/submit a time for an active weekly trial.
    
    This command handles:
    - Time format validation
    - Track name validation with autocomplete
    - Checking for active trials
    - Preventing slower time submissions
    - Tracking improvements
    - Medal achievement detection
    """
    
    async def execute(self, interaction: Interaction, track: str, time: str) -> None:
        """
        Execute the save time command.
        
        Args:
            interaction: Discord interaction object
            track: Track name (validated via autocomplete)
            time: Time string in MM:SS.mmm format
        """
        guild_id = self._validate_guild_interaction(interaction)
        user_id = self._validate_user_interaction(interaction)
        
        # Validate and parse the time input
        try:
            time_ms = InputValidator.validate_time_input(time)
        except ValidationError as e:
            raise ValidationError(f"Invalid time format: {e}")
        
        # Validate track name
        try:
            track_name = InputValidator.validate_track_name(track, TrackManager.get_all_tracks())
        except ValidationError as e:
            raise ValidationError(e)
        
        # Get active trial for this track
        trial_data = await self._get_active_trial_by_track(guild_id, track_name)
        if not trial_data:
            raise CommandError(
                f"No active trial found for **{track_name}**. "
                f"Use `/leaderboard {track_name}` to see if there's an inactive trial, "
                f"or ask an admin to create a new challenge."
            )
        
        trial_id = trial_data['id']
        
        # Check if user already has a time for this trial
        existing_time = await self._get_user_time_for_trial(trial_id, user_id)
        
        # Validate time submission
        is_improvement = False
        improvement_text = None
        
        if existing_time:
            existing_time_ms = existing_time['time_ms']
            
            # Check if new time is faster
            if time_ms >= existing_time_ms:
                existing_time_str = TimeParser.format_time(existing_time_ms)
                new_time_str = TimeParser.format_time(time_ms)
                raise CommandError(
                    f"Your new time (**{new_time_str}**) is not faster than your current best (**{existing_time_str}**). "
                    f"Only improvements are accepted!"
                )
            
            # Calculate improvement
            is_improvement = True
            improvement_text = TimeParser.get_time_improvement(existing_time_ms, time_ms)
        
        # Save the time to database
        await self._save_user_time(trial_id, user_id, time_ms, is_improvement)
        
        # Determine medal achievement
        medal_achieved = self._get_medal_for_time(time_ms, trial_data)
        
        # Create success response
        embed = EmbedFormatter.create_time_submission_embed(
            trial_data=trial_data,
            time_ms=time_ms,
            is_improvement=is_improvement,
            improvement_text=improvement_text,
            medal_achieved=medal_achieved
        )
        
        await self._send_response(interaction, embed=embed)
    
    async def _save_user_time(self, trial_id: int, user_id: int, time_ms: int, is_update: bool) -> None:
        """
        Save or update a user's time in the database.
        
        Args:
            trial_id: Trial ID
            user_id: Discord user ID
            time_ms: Time in milliseconds
            is_update: Whether this is updating an existing time
        """
        if is_update:
            # Update existing time
            query = """
                UPDATE player_times 
                SET time_ms = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE trial_id = %s 
                    AND user_id = %s
                RETURNING id
            """
            params = (time_ms, trial_id, user_id)
        else:
            # Insert new time
            query = """
                INSERT INTO player_times (trial_id, user_id, time_ms)
                VALUES (%s, %s, %s)
                RETURNING id
            """
            params = (trial_id, user_id, time_ms)
        
        results = self._execute_query(query, params, fetch=True)
        if not results:
            raise CommandError("Failed to save time. Please try again.")
    
    def _get_medal_for_time(self, time_ms: int, trial_data: Dict[str, Any]) -> Optional[str]:
        """
        Determine what medal a time achieves.
        
        Args:
            time_ms: Time in milliseconds
            trial_data: Trial information with goal times
            
        Returns:
            Medal level ('gold', 'silver', 'bronze') or None
        """
        gold_ms = trial_data['gold_time_ms']
        silver_ms = trial_data['silver_time_ms']
        bronze_ms = trial_data['bronze_time_ms']
        
        if time_ms <= gold_ms:
            return 'gold'
        elif time_ms <= silver_ms:
            return 'silver'
        elif time_ms <= bronze_ms:
            return 'bronze'
        else:
            return None
    
    async def autocomplete_callback(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """
        Provide autocomplete choices for track names.
        
        Only shows tracks that have active trials to prevent confusion.
        
        Args:
            interaction: Discord interaction object
            current: Current user input
            
        Returns:
            List of autocomplete choices for active tracks
        """
        try:
            guild_id = self._validate_guild_interaction(interaction)
            
            # Get tracks with active trials
            active_tracks = await self._get_active_track_names(guild_id)
            
            # Filter tracks based on user input
            if current:
                current_lower = current.lower()
                filtered_tracks = [
                    track for track in active_tracks
                    if current_lower in track.lower()
                ]
            else:
                filtered_tracks = active_tracks
            
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
    
    async def _get_active_track_names(self, guild_id: int) -> List[str]:
        """
        Get list of track names that have active trials.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            List of track names with active trials
        """
        query = """
            SELECT DISTINCT track_name
            FROM weekly_trials 
            WHERE guild_id = %s 
                AND status = 'active'
            ORDER BY track_name
        """
        
        try:
            results = self._execute_query(query, (guild_id,))
            return [row['track_name'] for row in results]
        except Exception:
            # Fallback to empty list if query fails
            return []


# Command setup function for the main bot file
def setup_save_command(tree: app_commands.CommandTree) -> None:
    """
    Set up the save command with the Discord command tree.
    
    Args:
        tree: Discord app commands tree
    """
    save_cmd = SaveTimeCommand()
    
    @tree.command(
        name="save",
        description="Submit your time for an active weekly trial"
    )
    @app_commands.describe(
        track="Select the track (only active trials shown)",
        time="Your time in MM:SS.mmm format (e.g., '2:23.640')"
    )
    async def save_time(interaction: Interaction, track: str, time: str):
        """
        Save/submit a time for an active weekly trial.
        
        Examples:
        /save track:Rainbow Road time:2:23.640
        /save track:Mario Circuit time:1:45.123
        """
        await save_cmd.handle_command(interaction, track=track, time=time)
    
    @save_time.autocomplete('track')
    async def track_autocomplete(interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for track parameter - shows only active trials."""
        return await save_cmd.autocomplete_callback(interaction, current)