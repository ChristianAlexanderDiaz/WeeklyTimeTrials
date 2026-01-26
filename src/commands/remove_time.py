"""
Remove time command for the MKW Time Trial Bot.

This command allows users to remove their submitted time from a weekly trial.
This is useful if they made a mistake or want to start fresh.
"""

from typing import List, Dict
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
            track: Track name with category (format: "track|category")
        """
        guild_id = self._validate_guild_interaction(interaction)
        user_id = self._validate_user_interaction(interaction)

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

        # Get trial for this track and category (any status - user might want to remove from expired trials)
        trial_data = await self._get_trial_by_track_and_category(guild_id, track_name, category)
        if not trial_data:
            raise CommandError(
                f"No {category} trial found for **{track_name}**."
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
        
        # Update live leaderboard to reflect the removal
        from ..utils.leaderboard_manager import update_live_leaderboard
        
        try:
            await update_live_leaderboard(trial_id, interaction.guild)
        except Exception as e:
            # Don't fail the command if leaderboard update fails
            logger.error(f"Error updating live leaderboard after time removal: {e}")
        
        # Create success response
        category_display = f" ({category.title()})" if category else ""
        embed = EmbedFormatter.create_success_embed(
            "Time Removed",
            f"Your time of **{removed_time_str}** has been removed from "
            f"**Weekly Time Trial #{trial_number} - {track_name}{category_display}**.",
            "You can submit a new time using the `/weeklytimesave` command."
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
        Provide autocomplete choices for track names with categories.

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

            # Get trials where user has submitted times in active trials
            user_trials = await self._get_user_trials_with_category(guild_id, user_id)

            # Filter based on user input
            if current:
                current_lower = current.lower()
                filtered_trials = [
                    trial for trial in user_trials
                    if current_lower in trial['display'].lower()
                ]
            else:
                filtered_trials = user_trials

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
    
    async def _get_user_trials_with_category(self, guild_id: int, user_id: int) -> List[Dict[str, str]]:
        """
        Get list of trials where the user has submitted times in active trials.

        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID

        Returns:
            List of dicts with 'display' (formatted) and 'value' (pipe-separated) keys
        """
        query = """
            SELECT DISTINCT wt.track_name, wt.category
            FROM weekly_trials wt
            JOIN player_times pt ON wt.id = pt.trial_id
            WHERE wt.guild_id = %s
                AND pt.user_id = %s
                AND wt.status = 'active'
            ORDER BY wt.track_name, wt.category
        """

        try:
            results = self._execute_query(query, (guild_id, user_id))
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

    async def _get_trial_by_track_and_category(self, guild_id: int, track_name: str, category: str):
        """
        Get trial information for a specific track and category (any status).

        Args:
            guild_id: Discord guild ID
            track_name: Track name to search for
            category: Category to search for

        Returns:
            Most recent trial data for the track and category or None if not found
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
            ORDER BY created_at DESC
            LIMIT 1
        """

        results = self._execute_query(query, (guild_id, track_name, category))
        return results[0] if results else None


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
        a new time afterwards using the /weeklytimesave command.
        
        Examples:
        /remove-time track:Rainbow Road
        /remove-time track:Mario Circuit
        """
        await remove_cmd.handle_command(interaction, track=track)
    
    @remove_time.autocomplete('track')
    async def track_autocomplete(interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for track parameter - shows only tracks with user's submissions."""
        return await remove_cmd.autocomplete_callback(interaction, current)