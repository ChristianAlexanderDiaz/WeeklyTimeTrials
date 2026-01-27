"""
Save time command for the MKW Time Trial Bot.

This command allows users to submit their time for an active weekly trial.
It includes validation, duplicate checking, and improvement tracking.
"""

from typing import List, Optional, Dict, Any
import logging
import discord
from discord import app_commands, Interaction

from .base import AutocompleteCommand, CommandError
from ..utils.validators import InputValidator, ValidationError
from ..utils.time_parser import TimeParser, TimeFormatError
from ..utils.track_data import TrackManager, get_track_autocomplete_choices
from ..utils.formatters import EmbedFormatter

logger = logging.getLogger(__name__)
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
            track: Track name with category (format: "track|category")
            time: Time string in MM:SS.mmm format
        """
        guild_id = self._validate_guild_interaction(interaction)
        user_id = self._validate_user_interaction(interaction)

        # Validate and parse the time input
        try:
            time_ms = InputValidator.validate_time_input(time)
        except ValidationError as e:
            raise ValidationError(f"Invalid time format: {e}")

        # Parse track and category from pipe-separated value
        if '|' in track:
            track_name, category = track.split('|', 1)
        else:
            # Fallback for backwards compatibility or manual entry
            track_name = track
            category = 'shrooms'

        # Validate track name
        try:
            track_name = InputValidator.validate_track_name(track_name, TrackManager.get_all_tracks())
        except ValidationError as e:
            raise ValidationError(e)

        # Validate category
        try:
            category = InputValidator.validate_category(category)
        except ValidationError as e:
            raise ValidationError(e)

        # Get active trial for this track and category
        trial_data = await self._get_active_trial_by_track_and_category(guild_id, track_name, category)
        if not trial_data:
            raise CommandError(
                f"No active {category} trial found for **{track_name}**. "
                f"Use `/leaderboard` to see if there's an inactive trial, "
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
        
        # Update live leaderboard
        from ..utils.leaderboard_manager import update_live_leaderboard
        
        try:
            await update_live_leaderboard(trial_id, interaction.guild)
        except Exception as e:
            # Don't fail the command if leaderboard update fails
            logger.error(f"Error updating live leaderboard: {e}")
        
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
        gold_ms = trial_data.get('gold_time_ms')
        silver_ms = trial_data.get('silver_time_ms')
        bronze_ms = trial_data.get('bronze_time_ms')
        
        # If no medal times are set, no medals can be earned
        if gold_ms is None or silver_ms is None or bronze_ms is None:
            return None
        
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
        Provide autocomplete choices for track names with categories.

        Only shows tracks that have active trials to prevent confusion.

        Args:
            interaction: Discord interaction object
            current: Current user input

        Returns:
            List of autocomplete choices for active tracks with categories
        """
        try:
            guild_id = self._validate_guild_interaction(interaction)

            # Get tracks with active trials (including category)
            active_trials = await self._get_active_trials_with_category(guild_id)

            # Filter based on user input
            if current:
                current_lower = current.lower()
                filtered_trials = [
                    trial for trial in active_trials
                    if current_lower in trial['display'].lower()
                ]
            else:
                filtered_trials = active_trials

            # Limit to 25 choices (Discord limit)
            filtered_trials = filtered_trials[:25]

            return [
                app_commands.Choice(name=trial['display'], value=trial['value'])
                for trial in filtered_trials
            ]

        except Exception as e:
            self.logger.error(f"Autocomplete error: {e}")
            # Fallback to all tracks if database query fails
            return [
                app_commands.Choice(name=choice['name'], value=choice['value'])
                for choice in get_track_autocomplete_choices(current)[:25]
            ]
    
    async def _get_active_trials_with_category(self, guild_id: int) -> List[Dict[str, str]]:
        """
        Get list of active trials with track names and categories.

        Args:
            guild_id: Discord guild ID

        Returns:
            List of dicts with 'display' (formatted) and 'value' (pipe-separated) keys
        """
        query = """
            SELECT track_name, category
            FROM weekly_trials
            WHERE guild_id = %s
                AND status = 'active'
            ORDER BY track_name, category
        """

        try:
            results = self._execute_query(query, (guild_id,))
            return [
                {
                    'display': f"{row['track_name']} ({row['category'].title()})",
                    'value': f"{row['track_name']}|{row['category']}"
                }
                for row in results
            ]
        except Exception:
            # Fallback to empty list if query fails
            return []

    async def _get_active_trial_by_track_and_category(self, guild_id: int, track_name: str, category: str) -> Optional[Dict[str, Any]]:
        """
        Get active trial information for a specific track and category.

        Args:
            guild_id: Discord guild ID
            track_name: Track name to search for
            category: Category to search for

        Returns:
            Trial data dictionary or None if not found
        """
        query = """
            SELECT
                id,
                trial_number,
                track_name,
                category,
                gold_time_ms,
                silver_time_ms,
                bronze_time_ms,
                start_date,
                end_date,
                status
            FROM weekly_trials
            WHERE guild_id = %s
                AND track_name = %s
                AND category = %s
                AND status = 'active'
            LIMIT 1
        """

        results = self._execute_query(query, (guild_id, track_name, category))
        return results[0] if results else None


# Command setup function for the main bot file
def setup_save_command(tree: app_commands.CommandTree) -> None:
    """
    Set up the save command with the Discord command tree.
    
    Args:
        tree: Discord app commands tree
    """
    save_cmd = SaveTimeCommand()
    
    @tree.command(
        name="weeklytimesave",
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
        /weeklytimesave track:Rainbow Road time:2:23.640
        /weeklytimesave track:Mario Circuit time:1:45.123
        """
        await save_cmd.handle_command(interaction, track=track, time=time)
    
    @save_time.autocomplete('track')
    async def track_autocomplete(interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for track parameter - shows only active trials."""
        return await save_cmd.autocomplete_callback(interaction, current)